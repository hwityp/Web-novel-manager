"""
Pipeline Orchestrator

파이프라인 전체를 조율하는 메인 컨트롤러입니다.
Stage 1(FolderOrganizer) → Stage 2(GenreClassifier) → Stage 3(FilenameNormalizer) 순서로 실행합니다.

핵심 기능:
- 단계별 실행 순서 보장 (Property 13)
- 결함 격리: 개별 파일 에러 시 해당 파일만 skip (Property 14)
- Dry-run 모드: 파일 시스템 변경 없이 미리보기 (Property 15)
- mapping.csv 생성 및 처리 요약 출력

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10
"""
import csv
import shutil
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from datetime import datetime

from core.novel_task import NovelTask
from core.pipeline_logger import PipelineLogger
from core.adapters import (
    FolderOrganizerAdapter,
    GenreClassifierAdapter,
    FilenameNormalizerAdapter
)
from config.pipeline_config import PipelineConfig


@dataclass
class PipelineResult:
    """파이프라인 실행 결과"""
    total_files: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    tasks: List[NovelTask] = field(default_factory=list)
    mapping_csv_path: Optional[Path] = None
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self):
        """결과를 딕셔너리로 변환"""
        return {
            'total_files': self.total_files,
            'processed': self.processed,
            'failed': self.failed,
            'skipped': self.skipped,
            'mapping_csv_path': str(self.mapping_csv_path) if self.mapping_csv_path else None,
            'errors': self.errors
        }


class PipelineOrchestrator:
    """파이프라인 전체를 조율하는 메인 컨트롤러"""
    
    # 파이프라인 단계 상수
    STAGE_FOLDER_ORGANIZER = 1
    STAGE_GENRE_CLASSIFIER = 2
    STAGE_FILENAME_NORMALIZER = 3
    
    # Progress callback 타입: (current_index, total_files, filename) -> None
    ProgressCallback = Optional[Callable[[int, int, str], None]]
    
    # Genre confirm callback 타입: (filename, suggested_genre, confidence) -> Optional[str]
    # 반환값: 사용자가 선택한 장르 (None이면 건너뛰기)
    GenreConfirmCallback = Optional[Callable[[str, str, str], Optional[str]]]
    
    def __init__(
        self, 
        config: PipelineConfig, 
        logger: Optional[PipelineLogger] = None,
        progress_callback: ProgressCallback = None,
        genre_confirm_callback: GenreConfirmCallback = None
    ):
        """
        Args:
            config: 파이프라인 설정
            logger: 파이프라인 로거 (없으면 기본 로거 생성)
            progress_callback: 진행 상황 콜백 함수 (current, total, filename)
            genre_confirm_callback: 장르 확인 콜백 함수 (filename, suggested_genre, confidence) -> selected_genre
        """
        self.config = config
        self.logger = logger or PipelineLogger(
            log_level=config.log_level,
            console_output=True
        )
        self.progress_callback = progress_callback
        self.genre_confirm_callback = genre_confirm_callback
        
        # 어댑터 초기화
        self.folder_organizer = FolderOrganizerAdapter(config, self.logger)
        self.genre_classifier = GenreClassifierAdapter(config, self.logger)
        self.filename_normalizer = FilenameNormalizerAdapter(config, self.logger)
        
        # 실행 추적
        self._current_stage = 0
        self._stage_history: List[int] = []
    
    def run(self, source_folder: Path, dry_run: bool = False) -> PipelineResult:
        """
        파이프라인 실행
        
        Args:
            source_folder: 소스 폴더 경로
            dry_run: True면 파일 시스템 변경 없이 미리보기만
            
        Returns:
            PipelineResult: 실행 결과
        """
        source_folder = Path(source_folder)
        result = PipelineResult()
        
        self.logger.info(f"Dry-run 모드: {'활성화' if dry_run else '비활성화'}")
        
        # 단계 히스토리 초기화
        self._stage_history = []
        
        try:
            # Stage 1: Folder Organizer
            self._record_stage(self.STAGE_FOLDER_ORGANIZER)
            tasks = self._run_stage1(source_folder, dry_run)
            result.total_files = len(tasks)
            
            # Stage 1 완료 후 파일 수를 알 수 있으므로 여기서 로그 시작
            self.logger.log_pipeline_start(str(source_folder), result.total_files)
            
            if not tasks:
                self.logger.warning("처리할 파일이 없습니다.")
                return result
            
            # Stage 2 & 3: 각 태스크 처리
            for idx, task in enumerate(tasks):
                # Progress callback 호출
                if self.progress_callback:
                    try:
                        self.progress_callback(idx + 1, result.total_files, task.raw_name)
                    except Exception:
                        pass  # 콜백 에러는 무시
                
                try:
                    # Stage 1.5: Title Extraction (New Step)
                    # 장르 추론 정확도를 높이기 위해 제목 정규화를 먼저 수행
                    task = self.filename_normalizer.parse_only(task)
                    
                    # Stage 2: Genre Classifier
                    self._record_stage(self.STAGE_GENRE_CLASSIFIER)
                    task = self._run_stage2(task)
                    
                    # confidence가 "medium"이면 사용자 확인 요청
                    if task.confidence == 'medium' and self.genre_confirm_callback:
                        try:
                            selected_genre = self.genre_confirm_callback(
                                task.raw_name, 
                                task.genre, 
                                task.confidence
                            )
                            if selected_genre:
                                task.genre = selected_genre
                                task.confidence = 'high'  # 사용자 확인 후 high로 변경
                                task.source = '사용자'    # 사용자가 확인/수정함
                                self.logger.info(f"사용자 장르 확인: {task.raw_name} → [{selected_genre}]")
                            else:
                                # 건너뛰기 선택
                                task.status = 'skipped'
                                self.logger.info(f"사용자 건너뛰기: {task.raw_name}")
                                result.skipped += 1
                                result.tasks.append(task)
                                continue
                        except Exception as e:
                            self.logger.warning(f"장르 확인 콜백 오류: {e}")
                    
                    # Stage 3: Filename Normalizer
                    self._record_stage(self.STAGE_FILENAME_NORMALIZER)
                    task = self._run_stage3(task, dry_run)
                    
                    # 실제 파일 이동 (dry_run이 아닐 때만)
                    if not dry_run and task.status == 'completed':
                        self._copy_file(task)
                    
                    # 결과 집계
                    if task.status == 'completed':
                        result.processed += 1
                    elif task.status == 'failed':
                        result.failed += 1
                        result.errors.append(f"{task.raw_name}: {task.error_message}")
                    elif task.status == 'skipped':
                        result.skipped += 1
                        
                except Exception as e:
                    # 결함 격리: 개별 파일 에러 시 해당 파일만 skip
                    task.status = 'failed'
                    task.error_message = str(e)
                    result.failed += 1
                    result.errors.append(f"{task.raw_name}: {str(e)}")
                    self.logger.error(f"태스크 처리 실패: {task.raw_name} - {e}")
                
                result.tasks.append(task)
            
            # mapping.csv 생성
            if not dry_run:
                result.mapping_csv_path = self._generate_mapping_csv(result.tasks, source_folder)
            else:
                # dry_run에서도 미리보기용 CSV 생성 (별도 경로)
                result.mapping_csv_path = self._generate_mapping_csv(
                    result.tasks, source_folder, preview=True
                )
            
        except Exception as e:
            self.logger.error(f"파이프라인 실행 중 치명적 오류: {e}")
            result.errors.append(f"Pipeline error: {str(e)}")
        
        # 결과 요약 출력
        self._print_summary(result, dry_run)
        self.logger.log_pipeline_complete(result.processed, result.failed, result.skipped)
        
        return result
    
    def run_stage1(self, source_folder: Path, dry_run: bool = False) -> List[NovelTask]:
        """Stage 1: 폴더 정리 (Scan or Organize)"""
        self._stage_history = []
        self._record_stage(self.STAGE_FOLDER_ORGANIZER)
        tasks = self._run_stage1(Path(source_folder), dry_run=dry_run)
        return tasks

    def run_stage1_5(self, tasks: List[NovelTask]) -> List[NovelTask]:
        """Stage 1.5: 제목 정규화 (Parse Only)"""
        processed_tasks = []
        for idx, task in enumerate(tasks):
            try:
                task = self.filename_normalizer.parse_only(task)
                
                # 정규화된 이름 미리보기 생성 (장르는 아직 모를 수 있음)
                # 장르가 없으면 '미분류' 상태로 미리보기
                preview_name = self.filename_normalizer.preview_normalized_name(task)
                task.metadata['normalized_name'] = preview_name
                
            except Exception as e:
                self.logger.warning(f"Stage 1.5 실패: {task.raw_name} - {e}")
            processed_tasks.append(task)
        return processed_tasks

    def apply_normalization_to_source(self, tasks: List[NovelTask]) -> List[NovelTask]:
        """[NEW] 소스 폴더의 원본 파일 이름을 정규화된 이름으로 즉시 교체"""
        processed_tasks = []
        for idx, task in enumerate(tasks):
            try:
                preview_name = task.metadata.get('normalized_name')
                if preview_name and task.current_path and task.current_path.exists():
                    new_path = task.current_path.with_name(preview_name)
                    if task.current_path != new_path:
                        try:
                            # 윈도우 파일 시스템 고려 (동일 이름 대소문자 등 방지용 임시 파일명 우회 필요 여부 검토)
                            os.rename(task.current_path, new_path)
                            task.current_path = new_path
                            task.metadata['target_path'] = str(new_path)
                            self.logger.info(f"소스 폴더 즉시 적용: {task.raw_name} -> {preview_name}")
                        except Exception as rename_err:
                            self.logger.error(f"소스 폴더 즉시 적용 실패: {task.raw_name} - {rename_err}")
                
            except Exception as e:
                self.logger.warning(f"소스 폴더 적용 실패: {task.raw_name} - {e}")
            processed_tasks.append(task)
        return processed_tasks

    def run_stage2(self, tasks: List[NovelTask]) -> List[NovelTask]:
        """Stage 2: 장르 추론 (Search Only)"""
        # 진행률 콜백에 task 객체 전달 기능 추가 (Real-time binding 지원)
        self._record_stage(self.STAGE_GENRE_CLASSIFIER)
        
        for idx, task in enumerate(tasks):
            try:
                # Progress Update with Task Object (for real-time GUI update)
                if self.progress_callback:
                    try:
                        # 콜백이 4개 인자(idx, total, name, task)를 받는지 확인하거나
                        # 기존 3개 인자 호환성 유지하며, GUI 쪽에서 **kwargs 등으로 처리해야 함.
                        # 여기서는 파이썬의 유연함을 이용해 task객체를 추가 인자로 보낼 수도 있으나,
                        # 안전하게 기존 시그니처(int, int, str)를 유지하되, 
                        # GUI가 task 객체 참조를 갖고 있으므로, task 객체 내부가 업데이트되면 GUI도 알 수 있음.
                        # 단, 리스트 뷰 갱신 트리거가 필요함.
                        # 따라서 콜백 호출 시점을 '처리 후'로 잡거나, 콜백에 task를 넘기는 게 확실함.
                        # 하지만 기존 인터페이스 변경은 위험하므로, task 내부 상태 업데이트 후 콜백 호출.
                        pass 
                    except: pass
                
                # Run Genre Classifier
                task = self._run_stage2(task)
                
                # Callback AFTER update
                if self.progress_callback:
                    # 확장된 콜백 지원: (current, total, filename, task_object)
                    try:
                        self.progress_callback(idx + 1, len(tasks), task.raw_name, task)
                    except TypeError:
                        # 기존 방식 (Fallback)
                        self.progress_callback(idx + 1, len(tasks), task.raw_name)

            except Exception as e:
                self.logger.warning(f"Stage 2 실패: {task.raw_name} - {e}")
                
        return tasks

    def run_stage3(self, tasks: List[NovelTask], source_folder: Path) -> PipelineResult:
        """Stage 3: 실행 및 이동 (Execute Only)"""
        result = PipelineResult()
        result.total_files = len(tasks)
        self._record_stage(self.STAGE_FILENAME_NORMALIZER)
        
        for idx, task in enumerate(tasks):
            # Skip check
            if task.status == 'skipped':
                result.skipped += 1
                result.tasks.append(task)
                # Skip된 것도 진행상황 업데이트 (UI 반영용)
                if self.progress_callback:
                    try: self.progress_callback(idx + 1, len(tasks), task.raw_name, task)
                    except: pass
                continue

            # Progress Update
            if self.progress_callback:
                try:
                    self.progress_callback(idx + 1, len(tasks), task.raw_name, task)
                except TypeError:
                     self.progress_callback(idx + 1, len(tasks), task.raw_name)

            try:
                # User Confirmation (if not already confirmed/skipped in Stage 2 logic or GUI)
                # In split workflow, searching (Stage 2) happens first.
                # Then GUI shows results. User clicks 'Execute'.
                # Confirmation is likely handled by GUI batch loop calling this, OR
                # we do final check here.
                # For v1.3.1, GUI handles the "Genre Confirm Dialog" during Stage 2 OR before Stage 3?
                # User wants: [Genre Inference] -> Show Table -> [Execute] -> [Confirm Popup?] -> Rename.
                # Actually Item 2 says: "2nd Click: Final confirmation popup -> Execute".
                # So Stage 3 just executes. Genre is already set in Stage 2.
                
                # Check mapping confidence
                if self.genre_confirm_callback and not task.genre:
                    # If genre missing (skipped search?), try one last time or just confirm?
                    # In this flow, we assume Stage 2 populated genres.
                    pass

                task = self._run_stage3(task, dry_run=False) # Rename Logic
                
                if task.status == 'completed':
                    # [Refactor] Explicit Copy Operation (v1.3.7)
                    # Method renamed from _move_file to _copy_file to reflect actual behavior
                    self._copy_file(task)
                    result.processed += 1
                elif task.status == 'failed':
                    result.failed += 1
                    result.errors.append(f"{task.raw_name}: {task.error_message}")
                elif task.status == 'skipped':
                    result.skipped += 1
            except Exception as e:
                task.status = 'failed'
                task.error_message = str(e)
                result.failed += 1
                result.errors.append(f"{task.raw_name}: {e}")
            
            result.tasks.append(task)
            
        # Generate CSV
        result.mapping_csv_path = self._generate_mapping_csv(result.tasks, source_folder, preview=False)
        self._print_summary(result, dry_run=False)
        return result

    def run_stage2_and_execute(self, tasks: List[NovelTask], source_folder: Path) -> PipelineResult:
        """Stage 2 & 3: 장르 추론 및 실행 (일괄 처리용)"""
        # 1. 장르 추론 (Stage 2)
        tasks = self.run_stage2(tasks)
        
        # 2. 장르 확인 (중간 단계) - 일괄 처리 시 필요한 로직
        # GUI에서 Batch 모드로 실행 시, 이 메서드 안에서 확인 로직이 돌아야 함. (기존 동작 유지)
        if self.genre_confirm_callback:
            for task in tasks:
                 if task.status != 'skipped': # 이미 스킵된거 제외
                    try:
                        # Smart Filter (Orchestrator 레벨에서도 지원하거나 콜백에 위임)
                        # 여기선 콜백 호출
                        selected_genre = self.genre_confirm_callback(
                            task.raw_name, 
                            task.genre, 
                            task.confidence
                        )
                        if selected_genre:
                            task.genre = selected_genre
                            task.confidence = 'high'
                            task.source = '사용자'
                        else:
                            task.status = 'skipped'
                    except Exception as e:
                        self.logger.warning(f"장르 확인 실패: {e}")

        # 3. 실행 및 이동 (Stage 3)
        # 이미 skipped 상태인 태스크는 run_stage3 내부에서 처리되거나 필터링됨
        # run_stage3는 status='skipped'인 경우 건너뜀 (위 구현 확인 필요)
        # 위 run_stage3 구현: for loop 돌면서 status check가 없음. 
        # 수정 필요: run_stage3가 skipped 상태를 존중하도록.
        
        return self.run_stage3(tasks, source_folder)

    # ... Restoring original run_stage2_and_execute as _legacy or keeping it ...
    # Wait, I can just ADD the new methods and keep the old one as is. 
    # The REPLACE block below will insert the new methods BEFORE the existing one or AFTER.
    pass

    def run_with_existing_tasks(self, tasks: List[NovelTask], source_folder: Path) -> PipelineResult:
        """Deprecated: Use run_stage2_and_execute instead"""
        return self.run_stage2_and_execute(tasks, source_folder)
    
    def _record_stage(self, stage: int):
        """단계 기록 (Property 13 검증용)"""
        self._current_stage = stage
        self._stage_history.append(stage)
    
    def get_stage_history(self) -> List[int]:
        """단계 실행 히스토리 반환 (테스트용)"""
        return self._stage_history.copy()
    
    def _run_stage1(self, source_folder: Path, dry_run: bool) -> List[NovelTask]:
        """
        Stage 1: Folder Organizer 실행
        
        Args:
            source_folder: 소스 폴더
            dry_run: dry-run 모드 여부
            
        Returns:
            생성된 NovelTask 목록
        """
        self.logger.info("Stage 1: 폴더 정리 시작")
        
        if dry_run:
            # dry_run 모드에서는 파일 목록만 스캔
            tasks = self.folder_organizer.scan_only(source_folder)
        else:
            tasks = self.folder_organizer.process(source_folder)
        
        self.logger.info(f"Stage 1 완료: {len(tasks)}개 파일 발견")
        return tasks
    
    def _run_stage2(self, task: NovelTask) -> NovelTask:
        """
        Stage 2: Genre Classifier 실행
        
        Args:
            task: 분류할 NovelTask
            
        Returns:
            장르가 분류된 NovelTask
        """
        self.logger.debug(f"Stage 2: 장르 분류 - {task.raw_name}")
        
        try:
            task = self.genre_classifier.classify(task)
        except Exception as e:
            self.logger.warning(f"장르 분류 실패: {task.raw_name} - {e}")
            task.genre = '미분류'
            task.confidence = 'low'
            task.status = 'processing'
        
        return task
    
    def _run_stage3(self, task: NovelTask, dry_run: bool) -> NovelTask:
        """
        Stage 3: Filename Normalizer 실행
        
        Args:
            task: 정규화할 NovelTask
            dry_run: dry-run 모드 여부
            
        Returns:
            정규화된 NovelTask
        """
        self.logger.debug(f"Stage 3: 파일명 정규화 - {task.raw_name}")
        
        try:
            if dry_run:
                # dry_run 모드에서는 미리보기만
                normalized_name = self.filename_normalizer.preview_normalized_name(task)
                task.metadata['normalized_name'] = normalized_name
                task.metadata['dry_run'] = True
                task.status = 'completed'
            else:
                task = self.filename_normalizer.normalize(task)
        except Exception as e:
            self.logger.warning(f"파일명 정규화 실패: {task.raw_name} - {e}")
            task.status = 'failed'
            task.error_message = str(e)
        
        return task
    
    def _copy_file(self, task: NovelTask):
        """
        파일 복사 (실제 파일 시스템 변경)
        
        Args:
            task: 복사할 NovelTask
        """
        if 'target_path' not in task.metadata:
            return
        
        # 단계 1: 파일 이동/복사
        target_path = Path(task.metadata.get('target_path', ''))
        source_path = task.current_path
        
        try:
            # 타겟 디렉토리 생성
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # [Fix] Windows Trailing Space/Dot Issue
            # 파일명 끝에 공백이나 점이 있는 경우 Windows API에서 파일을 찾지 못하는 문제 해결
            src_str = str(source_path)
            dst_str = str(target_path)
            
            if sys.platform == 'win32':
                # 절대 경로 변환
                if not os.path.isabs(src_str):
                    src_str = os.path.abspath(src_str)
                if not os.path.isabs(dst_str):
                    dst_str = os.path.abspath(dst_str)
                
                # UNC 접두사 추가 (경로 길이 제한 해제 및 특수문자/공백 처리 강화)
                if not src_str.startswith('\\\\?\\'):
                    src_str = f'\\\\?\\{src_str}'
                if not dst_str.startswith('\\\\?\\'):
                    dst_str = f'\\\\?\\{dst_str}'

            
            # 파일 복사 (원본 보존)
            shutil.copy2(src_str, dst_str)
            # task.current_path = target_path # 원본 위치는 유지 (필요하다면 로직에 따라 다름, 일단 복사만 수행)
            # 여기서는 복사된 파일로 후속 작업을 할지 원본으로 할지에 따라 다르지만, 
            # 일단 'move'를 대체하는 것이므로 복사본이 최종 결과물이 됨.
            task.current_path = target_path # 파이프라인 상에서는 타겟이 현재 위치가 됨
            
            self.logger.debug(f"파일 복사: {source_path} → {target_path}")
            
        except Exception as e:
            self.logger.error(f"파일 복사 실패: {source_path} → {target_path} - {e}")
            task.status = 'failed'
            task.error_message = f"파일 복사 실패: {str(e)}"
    
    def _generate_mapping_csv(
        self, 
        tasks: List[NovelTask], 
        source_folder: Path,
        preview: bool = False
    ) -> Path:
        """
        mapping.csv 생성
        
        Args:
            tasks: NovelTask 목록
            source_folder: 소스 폴더
            preview: True면 미리보기용 파일명 사용
            
        Returns:
            생성된 CSV 파일 경로
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mapping_preview_{timestamp}.csv" if preview else f"mapping_{timestamp}.csv"
        
        # [요청사항] CSV 파일은 메인 프로그램 루트 폴더에 저장
        try:
            from config.pipeline_config import get_base_path
            base_path = get_base_path()
            csv_path = base_path / filename
        except ImportError:
            # fallback
            csv_path = source_folder / filename
        
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 헤더
                writer.writerow([
                    'original_path',
                    'normalized_path', 
                    'genre',
                    'confidence',
                    'status',
                    'error_message'
                ])
                
                # 데이터
                for task in tasks:
                    normalized_path = task.metadata.get('target_path', '') or \
                                     task.metadata.get('normalized_name', '')
                    writer.writerow([
                        str(task.original_path),
                        normalized_path,
                        task.genre,
                        task.confidence,
                        task.status,
                        task.error_message
                    ])
            
            self.logger.info(f"매핑 CSV 생성: {csv_path}")
            return csv_path
            
        except Exception as e:
            self.logger.error(f"CSV 생성 실패: {e}")
            return None
    
    def _print_summary(self, result: PipelineResult, dry_run: bool):
        """
        실행 결과 요약 출력
        
        Args:
            result: 파이프라인 결과
            dry_run: dry-run 모드 여부
        """
        mode = "[미리보기]" if dry_run else "[실행완료]"
        
        print(f"\n{'='*50}")
        print(f"{mode} 파이프라인 실행 결과")
        print(f"{'='*50}")
        print(f"총 파일 수: {result.total_files}")
        print(f"처리 완료: {result.processed}")
        print(f"실패: {result.failed}")
        print(f"건너뜀: {result.skipped}")
        
        if result.mapping_csv_path:
            print(f"\n매핑 파일: {result.mapping_csv_path}")
        
        if result.errors:
            print(f"\n오류 목록 ({len(result.errors)}건):")
            for error in result.errors[:10]:  # 최대 10개만 표시
                print(f"  - {error}")
            if len(result.errors) > 10:
                print(f"  ... 외 {len(result.errors) - 10}건")
        
        print(f"{'='*50}\n")
    
    def process_with_retry(self, task: NovelTask, max_retries: int = None) -> NovelTask:
        """
        재시도 메커니즘이 포함된 태스크 처리
        
        Args:
            task: 처리할 NovelTask
            max_retries: 최대 재시도 횟수 (None이면 config 값 사용)
            
        Returns:
            처리된 NovelTask
        """
        max_retries = max_retries if max_retries is not None else self.config.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                # Stage 2: Genre Classification
                task = self._run_stage2(task)
                
                # Stage 3: Filename Normalization
                task = self._run_stage3(task, dry_run=False)
                
                return task
                
            except Exception as e:
                if attempt < max_retries:
                    self.logger.warning(
                        f"재시도 {attempt + 1}/{max_retries}: {task.raw_name}"
                    )
                    continue
                    
                task.status = 'failed'
                task.error_message = str(e)
                self.logger.error(f"최대 재시도 초과: {task.raw_name} - {e}")
        
        return task
