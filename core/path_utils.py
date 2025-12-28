#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Path Utilities for PyInstaller

PyInstaller로 패키징된 EXE 실행 시 경로 문제를 해결하는 유틸리티입니다.
sys._MEIPASS를 사용하여 번들된 리소스 경로를 올바르게 찾습니다.
"""
import sys
import os
from pathlib import Path


def get_base_path() -> Path:
    """
    애플리케이션 기본 경로 반환
    
    PyInstaller로 패키징된 경우 임시 폴더(_MEIPASS)를,
    일반 실행 시 현재 작업 디렉토리를 반환합니다.
    
    Returns:
        Path: 기본 경로
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller로 패키징된 경우
        return Path(sys._MEIPASS)
    else:
        # 일반 Python 실행
        return Path.cwd()


def get_resource_path(relative_path: str) -> Path:
    """
    리소스 파일의 절대 경로 반환
    
    Args:
        relative_path: 상대 경로 (예: "config/pipeline_config.json")
        
    Returns:
        Path: 절대 경로
    """
    base_path = get_base_path()
    return base_path / relative_path


def get_config_path() -> Path:
    """
    설정 파일 경로 반환
    
    EXE 실행 시에는 EXE와 같은 폴더에서 설정 파일을 찾습니다.
    개발 환경에서는 프로젝트 루트의 config 폴더를 사용합니다.
    
    Returns:
        Path: 설정 파일 경로
    """
    if getattr(sys, 'frozen', False):
        # EXE 실행 시: EXE와 같은 폴더
        exe_dir = Path(sys.executable).parent
        config_path = exe_dir / "config" / "pipeline_config.json"
        
        # 설정 폴더가 없으면 생성
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        return config_path
    else:
        # 개발 환경
        return Path("config/pipeline_config.json")


def get_log_path() -> Path:
    """
    로그 파일 경로 반환
    
    EXE 실행 시에는 EXE와 같은 폴더의 logs 폴더를 사용합니다.
    
    Returns:
        Path: 로그 폴더 경로
    """
    if getattr(sys, 'frozen', False):
        # EXE 실행 시: EXE와 같은 폴더
        exe_dir = Path(sys.executable).parent
        log_dir = exe_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "pipeline.log"
    else:
        # 개발 환경
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / "pipeline.log"


def is_frozen() -> bool:
    """
    PyInstaller로 패키징된 상태인지 확인
    
    Returns:
        bool: 패키징된 상태면 True
    """
    return getattr(sys, 'frozen', False)
