"""
WNAP Pipeline Adapters

기존 독립 모듈들을 파이프라인에 맞게 래핑하는 어댑터 모듈입니다.
"""
from core.adapters.folder_organizer_adapter import FolderOrganizerAdapter
from core.adapters.genre_classifier_adapter import GenreClassifierAdapter
from core.adapters.filename_normalizer_adapter import FilenameNormalizerAdapter

__all__ = ['FolderOrganizerAdapter', 'GenreClassifierAdapter', 'FilenameNormalizerAdapter']
