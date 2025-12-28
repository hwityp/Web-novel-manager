#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXE 빌드 스크립트

파일명 정규화 도구를 단독 실행 파일(EXE)로 빌드합니다.
"""

import subprocess
import sys
from pathlib import Path

# 버전 정보 가져오기
try:
    from version import __version__ as VERSION
except ImportError:
    VERSION = "1.0"

APP_NAME = "파일명정규화"

def build_exe():
    """EXE 파일 빌드"""
    print(f"=== {APP_NAME} v{VERSION} 빌드 시작 ===\n")
    
    # 버전이 포함된 출력 파일명
    output_name = f"{APP_NAME}_{VERSION}"
    
    # PyInstaller 명령어
    cmd = [
        "pyinstaller",
        "--onefile",                    # 단일 파일로 생성
        "--windowed",                   # 콘솔 창 숨김
        f"--name={output_name}",        # 출력 파일명 (버전 포함)
        "--icon=NONE",                  # 아이콘 (없음)
        "rename_normalize_gui.py"       # 소스 파일
    ]
    
    print(f"실행 명령어: {' '.join(cmd)}\n")
    
    try:
        # PyInstaller 실행
        result = subprocess.run(cmd, check=True)
        
        print(f"\n=== 빌드 완료 ===")
        print(f"출력 파일: dist\\{output_name}.exe")
        print(f"버전: {VERSION}")
        
        # 빌드 파일 자동 정리
        print("\n빌드 파일 정리 중...")
        cleanup_success = True
        
        # build 폴더 삭제
        build_dir = Path("build")
        if build_dir.exists():
            try:
                import shutil
                shutil.rmtree(build_dir)
                print(f"✓ build 폴더 삭제 완료")
            except Exception as e:
                print(f"✗ build 폴더 삭제 실패: {e}")
                cleanup_success = False
        
        # .spec 파일 삭제
        spec_file = Path(f"{output_name}.spec")
        if spec_file.exists():
            try:
                spec_file.unlink()
                print(f"✓ {output_name}.spec 파일 삭제 완료")
            except Exception as e:
                print(f"✗ {output_name}.spec 파일 삭제 실패: {e}")
                cleanup_success = False
        
        if cleanup_success:
            print("\n✅ 빌드 및 정리 완료!")
        else:
            print("\n⚠️ 빌드는 완료되었으나 일부 파일 정리 실패")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 빌드 실패: {e}")
        return 1
    except FileNotFoundError:
        print("\n❌ PyInstaller를 찾을 수 없습니다.")
        print("설치: pip install pyinstaller")
        return 1

if __name__ == "__main__":
    sys.exit(build_exe())
