"""
웹소설 장르 분류기 버전 정보

버전은 core.version에서 중앙 관리됩니다.
이 파일에서 직접 버전을 수정하지 말고, core/version.py를 수정하세요.
"""

try:
    from core.version import __version__, RELEASE_DATE as __version_date__, get_version, get_version_info as _get_core_info, get_full_version
    __version_name__ = ""  # 모듈별 이름은 필요 시 직접 지정
except ImportError:
    try:
        import sys, os
        _root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from core.version import __version__, RELEASE_DATE as __version_date__, get_version, get_full_version
        __version_name__ = ""
    except ImportError:
        __version__ = "1.0.0"
        __version_date__ = "unknown"
        __version_name__ = ""

        def get_version():
            return __version__

        def get_full_version():
            return f"v{__version__}"

# 버전 히스토리는 CHANGELOG.md를 참조하세요

def get_version_info():
    """버전 정보 딕셔너리 반환"""
    return {
        'version': __version__,
        'date': __version_date__,
        'name': __version_name__
    }

def get_full_version_string():
    """전체 버전 문자열 반환"""
    if __version_name__:
        return f"v{__version__} ({__version_name__})"
    return f"v{__version__} ({__version_date__})"
