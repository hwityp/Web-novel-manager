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
                        self._move_file(task)
                    
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
    
    def _move_file(self, task: NovelTask):
        """
        파일 이동 (실제 파일 시스템 변경)
        
        Args:
            task: 이동할 NovelTask
        """
        if 'target_path' not in task.metadata:
            return
        
        target_path = Path(task.metadata['target_path'])
        source_path = task.current_path
        
        try:
            # 타겟 디렉토리 생성
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 파일 이동
            shutil.move(str(source_path), str(target_path))
            task.current_path = target_path
            
            self.logger.debug(f"파일 이동: {source_path} → {target_path}")
            
        except Exception as e:
            self.logger.error(f"파일 이동 실패: {source_path} → {target_path} - {e}")
            task.status = 'failed'
            task.error_message = f"파일 이동 실패: {str(e)}"
    
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
