"""
WNAP 버전 정보

버전 관리 규칙: Semantic Versioning (https://semver.org/lang/ko/)
- MAJOR: 호환되지 않는 API 변경
- MINOR: 하위 호환성 있는 기능 추가
- PATCH: 하위 호환성 있는 버그 수정
"""

__version__ = "1.3.23"
RELEASE_DATE = "2026-02-24"

VERSION_INFO = (1, 3, 23)
__release_date__ = "2026-02-24"
__author__ = "WNAP Team"
__app_name__ = "WNAP - Web Novel Archive Pipeline"


def get_version() -> str:
    """버전 문자열 반환"""
    return __version__


def get_version_info() -> tuple:
    """버전 튜플 반환 (major, minor, patch)"""
    # 버전 문자열("1.3.13")에서 버전을 추출
    try:
        parts = __version__.split('.')
        return tuple(int(p) for p in parts[:3])
    except Exception:
        return (1, 0, 0)


def get_full_version() -> str:
    """전체 버전 정보 문자열 반환"""
    return f"{__app_name__} v{__version__} ({__release_date__})"
