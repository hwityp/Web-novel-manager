"""
==============================================================================
파일: conftest.py
역할 및 목적:
    pytest 테스트 프레임워크 전역 설정 파일.
    프로젝트 루트를 sys.path에 선제 등록하여 모든 단위/통합 테스트에서 절대 경로 모듈 import를 보장합니다.
주요 구성 요소:
    - _project_root 등록 로직
상호 연관 관계 및 의존성:
    - Caller: pytest 러너
    - Callee: sys.path
수정 시 주의사항:
    - 테스트 실행 환경이 어떤 디렉토리에서 시작되든 항상 올바른 루트가 등록되도록 유지해야 합니다.
==============================================================================
"""
import sys
import os

# 프로젝트 루트를 sys.path에 추가
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ==============================================================================
# Windows 콘솔 및 입출력 인코딩 UTF-8 강제화 (한글/CJK 깨짐 방지)
# ==============================================================================
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

if sys.platform == 'win32':
    try:
        import ctypes
        # Windows 콘솔 코드페이지를 65001 (UTF-8)로 전환
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

# ==============================================================================
# 테스트 실행 실시간 모니터링 훅 및 파일 기록
# ==============================================================================
from datetime import datetime
from pathlib import Path
import pytest

_TEST_LOG_PATH = Path(_project_root) / "logs" / "test_execution.log"


def _write_test_log(message: str):
    """테스트 실행 로그 파일(UTF-8)에 실시간 기록"""
    try:
        _TEST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_TEST_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def pytest_configure(config):
    """테스트 세션 시작 시 UTF-8 인코딩 확인 및 로그 파일 초기화"""
    _TEST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_TEST_LOG_PATH, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write(f"WNAP 테스트 실행 모니터링 로그 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"플랫폼: {sys.platform} | 파이썬: {sys.version.split()[0]} | 인코딩: UTF-8\n")
        f.write("=" * 80 + "\n\n")


def pytest_sessionstart(session):
    """테스트 세션 시작 시 terminalreporter 스트림을 UTF-8로 강제 재구성"""
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr and hasattr(tr, "_tw") and hasattr(tr._tw, "_file"):
        if hasattr(tr._tw._file, "reconfigure"):
            try:
                tr._tw._file.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def pytest_make_parametrize_id(config, val, argname):
    """파라미터화된 테스트 ID에서 한글/CJK가 유니코드 이스케이프(\\ud604...)되지 않고 온전히 한글로 표시되도록 지원"""
    if isinstance(val, str):
        clean_val = val.replace("\n", " ").strip()
        if len(clean_val) > 50:
            return clean_val[:47] + "..."
        return clean_val
    return None


def pytest_runtest_logstart(nodeid, location):
    """개별 테스트 시작 시 실시간 알림"""
    _write_test_log(f"[테스트 시작] {nodeid}")


def pytest_runtest_logreport(report):
    """개별 테스트 완료 시 결과 판정 및 실시간 모니터링 출력"""
    if report.when == "call":
        if report.passed:
            status_symbol = "✔ [PASS]"
            msg = f"{status_symbol} {report.nodeid} ({report.duration:.2f}s)"
        elif report.failed:
            status_symbol = "✘ [FAIL]"
            err_summary = str(report.longrepr).splitlines()[-1] if report.longrepr else "에러"
            msg = f"{status_symbol} {report.nodeid} ({report.duration:.2f}s) - {err_summary}"
        elif report.skipped:
            status_symbol = "⚠ [SKIP]"
            msg = f"{status_symbol} {report.nodeid} ({report.duration:.2f}s)"
        else:
            msg = f"  [{report.outcome.upper()}] {report.nodeid}"
        
        _write_test_log(msg)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """테스트 세션 종료 시 한글 종합 요약 출력"""
    passed = len(terminalreporter.stats.get('passed', []))
    failed = len(terminalreporter.stats.get('failed', []))
    skipped = len(terminalreporter.stats.get('skipped', []))
    total = passed + failed + skipped
    
    # 터미널에 한글 요약 출력 (write_sep, write_line으로 이스케이프 방지)
    terminalreporter.write_sep("=", "📊 [테스트 모니터링 종합 결과]")
    terminalreporter.write_line(f"  • 총 실행 테스트: {total}개")
    terminalreporter.write_line(f"  • 성공 (Passed) : {passed}개")
    terminalreporter.write_line(f"  • 실패 (Failed) : {failed}개")
    terminalreporter.write_line(f"  • 건너뜀(Skipped): {skipped}개")
    terminalreporter.write_line(f"  • 상세 로그 경로: {_TEST_LOG_PATH.absolute()}")
    terminalreporter.write_sep("=")
    
    summary_text = (
        f"\n{'='*70}\n"
        f"📊 [테스트 모니터링 종합 결과]\n"
        f"  • 총 실행 테스트: {total}개\n"
        f"  • 성공 (Passed) : {passed}개\n"
        f"  • 실패 (Failed) : {failed}개\n"
        f"  • 건너뜀(Skipped): {skipped}개\n"
        f"  • 상세 로그 경로: {_TEST_LOG_PATH.absolute()}\n"
        f"{'='*70}\n"
    )
    _write_test_log(summary_text)


