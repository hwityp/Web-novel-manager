"""
FolderOrganizer Adapter

기존 FolderOrganizer를 파이프라인에 맞게 래핑합니다.
process() 메서드로 폴더를 처리하고 List[NovelTask]를 반환합니다.

Validates: Requirements 2.1, 2.2, 2.3, 2.5
"""
import sys
from pathlib import Path
from typing import List, Optional

# 기존 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'modules' / 'organizer'))

from modules.organizer.folder_organizer import FolderOrganizer, find_unrar_near_executable
from core.novel_task import NovelTask
from core.pipeline_logger import PipelineLogger
from config.pipeline_config import PipelineConfig


class FolderOrganizerAdapter:
    """기존 FolderOrganizer를 파이프라인에 맞게 래핑"""
    
    def __init__(self, config: PipelineConfig, logger: Optional[PipelineLogger] = None):
        """
        Args:
            config: 파이프라인 설정
            logger: 파이프라인 로거 (없으면 기본 로거 생성)
        """
        self.config = config
        self.logger = logger or PipelineLogger()
        self._organizer: Optional[FolderOrganizer] = None
    
    def _get_organizer(self, source_folder: Path) -> FolderOrganizer:
        """FolderOrganizer 인스턴스 생성 또는 반환"""
        # unrar 자동 감지 설정
        find_unrar_near_executable()
        
        target_folder = self.config.target_folder or "정리완료"
        organizer = FolderOrganizer(str(source_folder), target_folder)
        
        # 보호 폴더 설정 적용
        if self.config.protected_folders:
            organizer.protected_folders = self.config.protected_folders.copy()
            # target_folder도 보호 폴더에 추가
            if target_folder not in organizer.protected_folders:
                organizer.protected_folders.append(target_folder)
        
        return organizer
    
    def process(self, source_folder: Path) -> List[NovelTask]:
        """
        폴더 정리 후 NovelTask 목록 반환
        
        Args:
            source_folder: 처리할 소스 폴더 경로
            
        Returns:
            생성된 NovelTask 목록
        """
        source_folder = Path(source_folder)
        
        if not source_folder.exists():
            self.logger.error(f"소스 폴더가 존재하지 않습니다: {source_folder}")
            return []
        
        self.logger.info(f"FolderOrganizer 처리 시작: {source_folder}")
        
        # 먼저 파일 목록 스캔 (scan_only와 동일한 방식)
        tasks = self.scan_only(source_folder)
        
        # 폴더 정리 실행 (압축 해제 등)
        organizer = self._get_organizer(source_folder)
        try:
            organizer.organize_folders()
        except Exception as e:
            self.logger.warning(f"폴더 정리 중 오류 발생 (계속 진행): {e}")
        
        self.logger.info(f"FolderOrganizer 처리 완료: {len(tasks)}개 파일 발견")
        return tasks
    
    def _collect_files(self, folder: Path) -> set:
        """폴더 내 모든 파일 경로 수집 (재귀)"""
        files = set()
        try:
            for item in folder.rglob('*'):
                if item.is_file():
                    files.add(item)
        except Exception as e:
            self.logger.warning(f"파일 수집 중 오류: {e}")
        return files
    
    def _create_task_from_file(self, file_path: Path) -> NovelTask:
        """파일에서 NovelTask 생성"""
        raw_name = file_path.stem  # 확장자 제외한 파일명
        
        return NovelTask(
            original_path=file_path,
            current_path=file_path,
            raw_name=raw_name,
            status="pending"
        )
    
    def is_protected_folder(self, folder_path: Path) -> bool:
        """보호된 폴더인지 확인"""
        folder_name = folder_path.name
        return self.config.is_protected_folder(folder_name)
    
    def get_processable_folders(self, source_folder: Path) -> List[Path]:
        """처리 가능한 서브폴더 목록 반환 (보호 폴더 제외)"""
        source_folder = Path(source_folder)
        
        if not source_folder.exists():
            return []
        
        folders = []
        for item in source_folder.iterdir():
            if item.is_dir() and not self.is_protected_folder(item):
                folders.append(item)
        
        return sorted(folders)
    
    def scan_only(self, source_folder: Path) -> List[NovelTask]:
        """
        파일 시스템 변경 없이 파일 목록만 스캔 (dry-run용)
        
        Args:
            source_folder: 스캔할 소스 폴더 경로
            
        Returns:
            발견된 파일들의 NovelTask 목록
        """
        source_folder = Path(source_folder)
        
        if not source_folder.exists():
            self.logger.error(f"소스 폴더가 존재하지 않습니다: {source_folder}")
            return []
        
        self.logger.info(f"파일 스캔 시작 (dry-run): {source_folder}")
        
        tasks = []
        supported_extensions = {'.txt', '.epub', '.zip', '.7z', '.rar', '.zipx'}
        
        # 1. 루트 폴더의 파일들 스캔
        for file_path in source_folder.iterdir():
            if file_path.is_file():
                if file_path.suffix.lower() in supported_extensions:
                    task = self._create_task_from_file(file_path)
                    tasks.append(task)
                    self.logger.debug(f"파일 발견 (루트): {task.raw_name}")
        
        # 2. 처리 가능한 서브폴더 내 파일들 스캔
        processable_folders = self.get_processable_folders(source_folder)
        
        for folder in processable_folders:
            # 폴더 내 모든 파일 스캔 (재귀)
            for file_path in folder.rglob('*'):
                if file_path.is_file():
                    if file_path.suffix.lower() in supported_extensions:
                        task = self._create_task_from_file(file_path)
                        tasks.append(task)
                        self.logger.debug(f"파일 발견 (서브폴더): {task.raw_name}")
        
        self.logger.info(f"파일 스캔 완료: {len(tasks)}개 파일 발견")
        return tasks
