"""
PipelineConfig 설정 관리 모듈

파이프라인 실행에 필요한 모든 설정을 관리합니다.
JSON 파일에서 로드하고, 잘못된 값은 기본값으로 대체합니다.

Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5
"""
import sys
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Set, List, Dict, Any, Optional
import json


def get_base_path() -> Path:
    """
    PyInstaller 패키징 환경과 일반 실행 환경 모두에서 
    올바른 기본 경로를 반환합니다.
    
    Returns:
        Path: 애플리케이션 기본 경로
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 EXE 실행 중
        # sys._MEIPASS는 임시 디렉토리 (내부 리소스)
        return Path(sys._MEIPASS)
    else:
        # 일반 Python 실행
        return Path(__file__).parent.parent


def get_config_path(filename: str = "pipeline_config.json") -> Path:
    """
    설정 파일 경로를 반환합니다.
    
    Args:
        filename: 설정 파일명
        
    Returns:
        Path: 설정 파일 전체 경로
    """
    base = get_base_path()
    return base / "config" / filename


def get_resource_path(relative_path: str) -> Path:
    """
    리소스 파일의 절대 경로를 반환합니다.
    PyInstaller 패키징 환경과 일반 실행 환경 모두 지원.
    
    Args:
        relative_path: 프로젝트 루트 기준 상대 경로
        
    Returns:
        Path: 리소스 파일 절대 경로
    """
    base = get_base_path()
    return base / relative_path


# 표준 장르 화이트리스트
GENRE_WHITELIST: Set[str] = {
    '소설', '판타지', '현대', '현판', '무협', '선협',
    '스포츠', '퓨판', '역사', '로판', 'SF', '겜판',
    '언정', '공포', '패러디', '미분류'
}

# 기본 보호 폴더 목록
DEFAULT_PROTECTED_FOLDERS: List[str] = ["Downloads", "Tempfile", "Temp", "정리완료"]

# 유효한 로그 레벨
VALID_LOG_LEVELS: Set[str] = {"DEBUG", "INFO", "WARNING", "ERROR"}


@dataclass
class PipelineConfig:
    """파이프라인 설정 데이터클래스"""
    
    source_folder: str = ""
    target_folder: str = ""
    protected_folders: List[str] = field(default_factory=lambda: DEFAULT_PROTECTED_FOLDERS.copy())
    genre_whitelist: List[str] = field(default_factory=lambda: sorted(GENRE_WHITELIST))
    log_level: str = "INFO"
    max_retries: int = 1
    dry_run: bool = False
    
    # 구글 검색 설정
    google_api_key: str = ""
    google_cse_id: str = ""
    
    def __post_init__(self):
        """초기화 후 유효성 검증 및 기본값 적용"""
        self._validate_and_fix()
    
    def _validate_and_fix(self):
        """잘못된 값을 기본값으로 대체"""
        # log_level 검증
        if self.log_level not in VALID_LOG_LEVELS:
            self.log_level = "INFO"
        
        # max_retries 검증 (0 이상의 정수)
        if not isinstance(self.max_retries, int) or self.max_retries < 0:
            self.max_retries = 1
        
        # protected_folders가 리스트인지 확인
        if not isinstance(self.protected_folders, list):
            self.protected_folders = DEFAULT_PROTECTED_FOLDERS.copy()
        else:
            # 설정 파일에서 로드된 리스트에 필수 보호 폴더(Temp 등)가 빠져있으면 강제 추가
            for default_folder in DEFAULT_PROTECTED_FOLDERS:
                if default_folder not in self.protected_folders:
                    self.protected_folders.append(default_folder)
        
        # genre_whitelist가 리스트인지 확인
        if not isinstance(self.genre_whitelist, list):
            self.genre_whitelist = sorted(GENRE_WHITELIST)
        
        # dry_run이 bool인지 확인
        if not isinstance(self.dry_run, bool):
            self.dry_run = False
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화를 위한 딕셔너리 변환"""
        return {
            'source_folder': self.source_folder,
            'target_folder': self.target_folder,
            'protected_folders': self.protected_folders,
            'genre_whitelist': self.genre_whitelist,
            'log_level': self.log_level,
            'max_retries': self.max_retries,
            'dry_run': self.dry_run,
            'google_api_key': self.google_api_key,
            'google_cse_id': self.google_cse_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PipelineConfig':
        """딕셔너리에서 PipelineConfig 복원 (안전한 기본값 적용)"""
        return cls(
            source_folder=data.get('source_folder', ''),
            target_folder=data.get('target_folder', ''),
            protected_folders=data.get('protected_folders', DEFAULT_PROTECTED_FOLDERS.copy()),
            genre_whitelist=data.get('genre_whitelist', sorted(GENRE_WHITELIST)),
            log_level=data.get('log_level', 'INFO'),
            max_retries=data.get('max_retries', 1),
            dry_run=data.get('dry_run', False),
            google_api_key=data.get('google_api_key', ""),
            google_cse_id=data.get('google_cse_id', "")
        )
    
    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열로 직렬화"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PipelineConfig':
        """JSON 문자열에서 PipelineConfig 복원"""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 기본 설정 반환
            return cls()
    
    def save(self, file_path: Path) -> None:
        """설정을 JSON 파일로 저장"""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def load(cls, file_path: Path) -> 'PipelineConfig':
        """JSON 파일에서 설정 로드 (파일 없으면 기본값)"""
        file_path = Path(file_path)
        if not file_path.exists():
            return cls()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return cls.from_json(f.read())
        except (IOError, json.JSONDecodeError):
            return cls()
    
    @property
    def source_path(self) -> Optional[Path]:
        """source_folder를 Path 객체로 반환"""
        return Path(self.source_folder) if self.source_folder else None
    
    @property
    def target_path(self) -> Optional[Path]:
        """target_folder를 Path 객체로 반환"""
        return Path(self.target_folder) if self.target_folder else None
    
    def get_genre_whitelist_set(self) -> Set[str]:
        """genre_whitelist를 Set으로 반환"""
        return set(self.genre_whitelist)
    
    def is_protected_folder(self, folder_name: str) -> bool:
        """폴더가 보호 폴더인지 확인"""
        return folder_name in self.protected_folders
