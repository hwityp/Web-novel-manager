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

# 프로젝트 루트를 sys.path에 추가 (절대 import 지원)
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# PyInstaller 패키징 시 경로 설정
if getattr(sys, 'frozen', False):
    # EXE로 실행 중
    application_path = os.path.dirname(sys.executable)
    os.chdir(application_path)
else:
    # 일반 Python 실행
    application_path = os.path.dirname(os.path.abspath(__file__))


def main():
    """GUI 애플리케이션 실행"""
    from gui.main_window import WNAPMainWindow
    
    app = WNAPMainWindow()
    app.mainloop()


if __name__ == '__main__':
    main()
