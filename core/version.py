"""
==============================================================================
파일: core/version.py
역할 및 목적:
    프로젝트의 단일 진실 공급원(Single Source of Truth) 버전 정보 관리 모듈.
    Semantic Versioning 기반의 버전 문자열, 릴리스 일자, 애플리케이션 공식 명칭을 제공합니다.
주요 구성 요소:
    - __version__, RELEASE_DATE, VERSION_INFO
    - get_version(), get_full_version(): 버전 조회 함수
상호 연관 관계 및 의존성:
    - Caller: main.py, build_exe.py, gui.main_window, core.pipeline_logger
    - Callee: 없음 (독립 모듈)
수정 시 주의사항:
    - 빌드 배포 및 변경 사항 릴리스 시 반드시 이 파일의 버전과 RELEASE_DATE를 업데이트해야 합니다.
==============================================================================
"""

__version__ = "1.3.38"
RELEASE_DATE = "2026-09-07"

VERSION_INFO = (1, 3, 38)
__release_date__ = "2026-09-07"
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
