"""
==============================================================================
파일: sitecustomize.py
역할 및 목적:
    Python 인터프리터 기동 시 자동 로드(site module hook)되어 Windows 환경의 콘솔 코드페이지(CP65001) 및
    표준 입출력(stdout, stderr, stdin)의 UTF-8 인코딩을 전역 강제 설정.
    테스트 창(pytest), 터미널 콘솔, 하위 프로세스 전반의 한글 및 CJK 문자 깨짐 현상을 원천 방지합니다.
==============================================================================
"""
import sys
import os

# UTF-8 환경변수 설정
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

if sys.platform == 'win32':
    try:
        import ctypes
        # Windows 콘솔 출력/입력 코드페이지를 65001(UTF-8)로 전환
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    # 표준 입출력 스트림을 UTF-8(errors='replace')로 재구성
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

    if hasattr(sys.stdin, 'reconfigure'):
        try:
            sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
