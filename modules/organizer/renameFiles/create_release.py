#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
릴리스 패키지 생성 스크립트
실행 파일 + 문서를 포함한 배포 패키지 생성
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# 버전 정보
VERSION = "1.1.0"
RELEASE_NAME = f"파일명정규화도구_v{VERSION}"

# 경로 설정
current_dir = Path(__file__).parent
dist_dir = current_dir / "dist"
release_dir = current_dir / "release" / RELEASE_NAME
exe_file = dist_dir / "파일명정규화도구.exe"

def create_release_package():
    """릴리스 패키지 생성"""
    
    # 실행 파일 확인
    if not exe_file.exists():
        print("❌ 실행 파일이 없습니다. 먼저 빌드를 실행하세요:")
        print("   python build_exe.py")
        return False
    
    # 릴리스 디렉토리 생성
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)
    
    print(f"📦 릴리스 패키지 생성 중: {RELEASE_NAME}")
    print("="*60)
    
    # 파일 복사
    files_to_copy = [
        (exe_file, "파일명정규화도구.exe"),
        (current_dir / "README.md", "README.md"),
        (current_dir / "BUILD_GUIDE.md", "BUILD_GUIDE.md"),
    ]
    
    for src, dst_name in files_to_copy:
        if src.exists():
            dst = release_dir / dst_name
            shutil.copy2(src, dst)
            print(f"✅ {dst_name}")
        else:
            print(f"⚠️  {dst_name} (파일 없음)")
    
    # 버전 정보 파일 생성
    version_file = release_dir / "VERSION.txt"
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(f"파일명 정규화 도구\n")
        f.write(f"Version: {VERSION}\n")
        f.write(f"Build Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\n")
        f.write(f"실행 방법:\n")
        f.write(f"1. 파일명정규화도구.exe 더블클릭\n")
        f.write(f"2. 폴더 선택 버튼으로 정리할 폴더 선택\n")
        f.write(f"3. 미리보기 확인 후 '파일명 변경 실행' 클릭\n")
        f.write(f"\n")
        f.write(f"자세한 사용법은 README.md를 참조하세요.\n")
    print(f"✅ VERSION.txt")
    
    # ZIP 파일 생성
    print("\n📦 ZIP 파일 생성 중...")
    zip_path = current_dir / "release" / f"{RELEASE_NAME}"
    shutil.make_archive(zip_path, 'zip', release_dir.parent, RELEASE_NAME)
    print(f"✅ {RELEASE_NAME}.zip")
    
    # 완료
    print("\n" + "="*60)
    print("✨ 릴리스 패키지 생성 완료!")
    print("="*60)
    print(f"📁 폴더: {release_dir}")
    print(f"📦 ZIP: {zip_path}.zip")
    print("="*60)
    
    # 파일 크기 정보
    exe_size = exe_file.stat().st_size / (1024 * 1024)
    zip_size = Path(f"{zip_path}.zip").stat().st_size / (1024 * 1024)
    print(f"\n📊 파일 크기:")
    print(f"   실행 파일: {exe_size:.2f} MB")
    print(f"   ZIP 파일: {zip_size:.2f} MB")
    
    return True

if __name__ == '__main__':
    success = create_release_package()
    if success:
        print("\n🎉 배포 준비 완료!")
        print("\n다음 단계:")
        print("1. release 폴더의 ZIP 파일을 GitHub Releases에 업로드")
        print("2. 또는 사용자에게 직접 배포")
    else:
        print("\n❌ 릴리스 생성 실패")
