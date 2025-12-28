#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyInstaller 빌드 스크립트
단독 실행 파일 생성
"""

import PyInstaller.__main__
import os

# 현재 디렉토리
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)  # 작업 디렉토리를 스크립트 위치로 변경

# PyInstaller 옵션
PyInstaller.__main__.run([
    'rename_normalize_gui.py',           # 메인 스크립트
    '--name=파일명정규화도구',              # 실행 파일 이름
    '--onefile',                          # 단일 파일로 생성
    '--windowed',                         # 콘솔 창 숨김 (GUI 전용)
    '--icon=NONE',                        # 아이콘 (없으면 기본)
    '--add-data=rename_normalize.py;.',   # 정규화 로직 포함
    '--clean',                            # 빌드 전 정리
    '--noconfirm',                        # 확인 없이 진행
    f'--distpath={current_dir}/dist',     # 출력 디렉토리
    f'--workpath={current_dir}/build',    # 작업 디렉토리
    f'--specpath={current_dir}',          # spec 파일 위치
])

print("\n" + "="*60)
print("빌드 완료!")
print("="*60)
print(f"실행 파일 위치: {current_dir}/dist/파일명정규화도구.exe")
print("="*60)
