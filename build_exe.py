#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNAP EXE 빌드 스크립트

PyInstaller를 사용하여 WNAP를 단일 실행 파일로 패키징합니다.

사용법:
    python build_exe.py

옵션:
    --debug: 콘솔 창 표시 (디버깅용)
    --clean: 빌드 전 dist/build 폴더 정리
"""
import subprocess
import sys
import shutil
from pathlib import Path
import argparse

# 버전 정보
__version__ = "1.1.0"
__release_date__ = "2024-12-28"

def get_full_version():
    return f"WNAP v{__version__}"


def check_pyinstaller():
    """PyInstaller 설치 확인 및 설치"""
    try:
        import PyInstaller
        print(f"✅ PyInstaller {PyInstaller.__version__} 설치됨")
        return True
    except ImportError:
        print("⚠️ PyInstaller가 설치되어 있지 않습니다. 설치 중...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
            print("✅ PyInstaller 설치 완료")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ PyInstaller 설치 실패: {e}")
            return False


def clean_build_folders():
    """빌드 폴더 정리"""
    folders_to_clean = ['dist', 'build']
    for folder in folders_to_clean:
        folder_path = Path(folder)
        if folder_path.exists():
            print(f"🗑️ {folder} 폴더 삭제 중...")
            shutil.rmtree(folder_path)
    
    # .spec 파일 삭제
    for spec_file in Path('.').glob('*.spec'):
        print(f"🗑️ {spec_file} 삭제 중...")
        spec_file.unlink()


def build_exe(debug: bool = False):
    """
    PyInstaller로 EXE 빌드
    
    Args:
        debug: True면 콘솔 창 표시
    """
    print("=" * 60)
    print(f"🔨 WNAP EXE 빌드 시작 - v{__version__}")
    print("=" * 60)
    
    # PyInstaller 설치 확인
    if not check_pyinstaller():
        return False
    
    # EXE 파일명에 버전 포함
    exe_name = f"WNAP_Manager_v{__version__}"
    
    # PyInstaller 명령어 구성
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', exe_name,
        '--onefile',
        # CustomTkinter 전체 수집
        '--collect-all', 'customtkinter',
        # 데이터 폴더 포함 (Windows 경로 형식: source;destination)
        '--add-data', 'config;config',
        '--add-data', 'core;core',
        '--add-data', 'gui;gui',
        '--add-data', 'modules;modules',
        # 숨김 임포트
        '--hidden-import', 'customtkinter',
        '--hidden-import', 'tkinter',
        '--hidden-import', 'tkinter.ttk',
        '--hidden-import', 'config.pipeline_config',
        '--hidden-import', 'core.utils.genre_mapping',
        '--hidden-import', 'core.utils.genre_cache',
        '--hidden-import', 'core.utils.similarity',
        '--hidden-import', 'PIL._tkinter_finder',
        # 아이콘 (있으면)
        # '--icon', 'icon.ico',
    ]
    
    # 디버그 모드가 아니면 콘솔 숨김
    if not debug:
        cmd.append('--noconsole')
    
    # 메인 스크립트
    cmd.append('main_gui.py')
    
    print(f"📦 버전: {__version__} ({__release_date__})")
    print(f"📦 실행 명령어:")
    print(f"   {' '.join(cmd)}")
    print()
    
    # PyInstaller 실행
    try:
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 60)
        print("✅ 빌드 완료!")
        print("=" * 60)
        
        # 결과 확인
        exe_path = Path(f'dist/{exe_name}.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📁 EXE 위치: {exe_path.absolute()}")
            print(f"📊 파일 크기: {size_mb:.2f} MB")
            print(f"📌 버전: {get_full_version()}")
            
            # config 폴더 복사 (EXE와 같은 위치에 - 사용자 설정용)
            dist_config = Path('dist/config')
            if not dist_config.exists():
                dist_config.mkdir(parents=True)
            
            # 기본 설정 파일 복사
            config_files = [
                'config/pipeline_config.json',
                'config/genre_mapping.json',
                'config/genre_cache.json'
            ]
            for config_file in config_files:
                src = Path(config_file)
                if src.exists():
                    shutil.copy(src, dist_config / src.name)
                    print(f"📋 설정 파일 복사: {dist_config / src.name}")
            
            print()
            print("🚀 실행 방법:")
            print(f"   {exe_path.absolute()}")
        else:
            print("❌ EXE 파일이 생성되지 않았습니다.")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 빌드 실패: {e}")
        return False
    except FileNotFoundError:
        print("❌ PyInstaller가 설치되어 있지 않습니다.")
        print("   pip install pyinstaller 로 설치해주세요.")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description=f'WNAP EXE 빌드 스크립트 - v{__version__}'
    )
    parser.add_argument('--debug', action='store_true', help='콘솔 창 표시 (디버깅용)')
    parser.add_argument('--clean', action='store_true', help='빌드 전 dist/build 폴더 정리')
    parser.add_argument('--version', '-v', action='version', version=get_full_version())
    args = parser.parse_args()
    
    # 정리
    if args.clean:
        clean_build_folders()
    
    # 빌드
    success = build_exe(debug=args.debug)
    
    if success:
        print()
        print("=" * 60)
        print(f"📦 배포 준비 완료! - v{__version__}")
        print("=" * 60)
        print()
        print("배포 시 포함할 파일:")
        print(f"  - dist/WNAP_Manager_v{__version__}.exe")
        print("  - dist/config/ (선택 - 사용자 설정)")
        print()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
