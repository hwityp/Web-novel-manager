"""
웹소설 장르 분류기 메인 실행 파일

실행 방법:
    python classifier_launcher.py
"""

import sys
import os

# 버전 정보 import
from version import __version__, __version_date__, __version_name__

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# GUI 실행
if __name__ == "__main__":
    try:
        # 버전 정보 출력
        print(f"웹소설 장르 분류기 v{__version__} ({__version_name__})")
        print(f"Last Updated: {__version_date__}")
        print("-" * 60)
        
        import tkinter as tk
        from genre_classifier_gui import GenreClassifierGUI
        
        # 메인 윈도우 생성
        root = tk.Tk()
        
        # GUI 인스턴스 생성
        app = GenreClassifierGUI(root)
        
        # 창 닫기 이벤트 핸들러 등록
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        
        # 메인 루프 실행
        root.mainloop()
        
    except ImportError as e:
        print(f"오류: 필요한 모듈을 찾을 수 없습니다.")
        print(f"상세: {str(e)}")
        print("\n다음 명령어로 필요한 패키지를 설치해주세요:")
        print("pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        print(f"예상치 못한 오류가 발생했습니다:")
        print(f"{type(e).__name__}: {str(e)}")
        
        import traceback
        print("\n상세 오류 정보:")
        traceback.print_exc()
        sys.exit(1)
