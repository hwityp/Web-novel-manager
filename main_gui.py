#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web Novel Archive Pipeline (WNAP) - GUI Entry Point

웹소설 아카이브 파일을 자동으로 정리하는 통합 파이프라인의 GUI 인터페이스입니다.

사용법:
    python main_gui.py

또는 EXE로 패키징된 경우:
    WNAP_Manager.exe

Validates: Requirements 8.2
"""
import sys
import os
from dotenv import load_dotenv

# 환경 변수 로드 (API 키 등)
load_dotenv(override=True)

# ============================================================================
# PyInstaller 경로 보정 로직 (EXE 실행 환경 지원)
# ============================================================================
def _setup_paths():
    """
    PyInstaller 패키징 환경과 일반 실행 환경 모두에서
    올바른 경로를 설정합니다.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 EXE 실행 중
        # sys._MEIPASS: 임시 디렉토리 (내부 리소스 위치)
        base_path = sys._MEIPASS
        application_path = os.path.dirname(sys.executable)
        
        # 작업 디렉토리를 EXE 위치로 변경
        os.chdir(application_path)
    else:
        # 일반 Python 실행
        base_path = os.path.dirname(os.path.abspath(__file__))
        application_path = base_path
    
    # 프로젝트 루트를 sys.path에 추가 (절대 import 지원)
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    
    return base_path, application_path

# 경로 설정 실행
_BASE_PATH, _APP_PATH = _setup_paths()


# ============================================================================
# CLI 인자 파싱
# ============================================================================
def get_parser():
    import argparse
    parser = argparse.ArgumentParser(description="WNAP GUI Launcher")
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    return parser

def main():
    """GUI 애플리케이션 실행"""
    from gui.main_window import WNAPMainWindow
    
    # Parse CLI Arguments
    parser = get_parser()
    args = parser.parse_args()
    
    app = WNAPMainWindow(log_level=args.log_level)
    app.mainloop()


if __name__ == '__main__':
    main()
