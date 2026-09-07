"""
Classifier Core Package

장르 분류기의 핵심 클래스들을 제공합니다.
"""
import sys

# Windows 콘솔 한글 깨짐 방지 (UTF-8 CP65001 강제 설정)
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    if hasattr(sys.stderr, 'reconfigure'):
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

from modules.classifier.src.core.keyword_manager import KeywordManager
from modules.classifier.src.core.genre_classifier import GenreClassifier
from modules.classifier.src.core.hybrid_classifier_v2 import HybridClassifier
from modules.classifier.src.core.naver_genre_extractor_v4 import NaverGenreExtractorV4

__all__ = [
    'GenreClassifier',
    'HybridClassifier',
    'KeywordManager',
    'NaverGenreExtractorV4',
]
