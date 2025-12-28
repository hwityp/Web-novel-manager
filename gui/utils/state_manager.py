#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Window State Manager

윈도우 위치와 크기를 저장하고 복원하는 관리자입니다.
config/gui_state.json 파일을 사용하여 상태를 유지합니다.

Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any
import customtkinter as ctk


class WindowStateManager:
    """윈도우 상태 저장/복원 관리자"""
    
    STATE_FILE = Path("config/gui_state.json")
    DEFAULT_WIDTH = 1400
    DEFAULT_HEIGHT = 1000
    MIN_VISIBLE_PIXELS = 100  # 최소 화면에 보여야 하는 픽셀
    
    @classmethod
    def load_state(cls) -> Dict[str, Any]:
        """
        저장된 윈도우 상태 로드 (위치만)
        
        Returns:
            dict: 저장된 상태 또는 빈 딕셔너리
        """
        try:
            if cls.STATE_FILE.exists():
                with open(cls.STATE_FILE, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    # 위치 키만 검증 (크기는 저장하지 않음)
                    if all(key in state for key in ['x', 'y']):
                        return state
        except (json.JSONDecodeError, IOError, KeyError):
            pass
        return {}
    
    @classmethod
    def save_state(cls, window: ctk.CTk) -> bool:
        """
        현재 윈도우 위치만 저장 (크기는 저장하지 않음)
        
        Args:
            window: CTk 윈도우 인스턴스
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            cls.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # 위치만 저장 (크기는 항상 기본값 사용)
            state = {
                "x": window.winfo_x(),
                "y": window.winfo_y()
            }
            
            with open(cls.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            return True
        except (IOError, OSError):
            return False
    
    @classmethod
    def restore_state(cls, window: ctk.CTk) -> bool:
        """
        윈도우 상태 복원 (항상 기본 크기, 위치만 복원)
        
        Args:
            window: CTk 윈도우 인스턴스
            
        Returns:
            bool: 복원 성공 여부 (기본값 사용 시 False)
        """
        # 화면 크기 가져오기
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # 기본 크기 설정 (화면 크기 초과 방지)
        width = min(cls.DEFAULT_WIDTH, screen_width - 100)
        height = min(cls.DEFAULT_HEIGHT, screen_height - 100)
        
        state = cls.load_state()
        
        if not state:
            # 기본 크기로 중앙 배치
            window.geometry(f"{width}x{height}")
            cls._center_window(window)
            return False
        
        # 저장된 위치 가져오기
        x = state.get("x", 0)
        y = state.get("y", 0)
        
        # 위치 검증 및 보정
        x, y = cls._validate_position(x, y, width, height, screen_width, screen_height)
        
        window.geometry(f"{width}x{height}+{x}+{y}")
        return True
    
    @classmethod
    def _validate_position(
        cls, x: int, y: int, width: int, height: int,
        screen_width: int, screen_height: int
    ) -> tuple:
        """
        윈도우 위치가 화면 범위 내에 있는지 검증하고 보정
        
        Returns:
            tuple: (x, y) 보정된 위치
        """
        # X 위치 보정: 최소 MIN_VISIBLE_PIXELS 픽셀은 화면에 보이도록
        if x < -width + cls.MIN_VISIBLE_PIXELS:
            x = 0
        elif x > screen_width - cls.MIN_VISIBLE_PIXELS:
            x = screen_width - width
        
        # Y 위치 보정: 최소 MIN_VISIBLE_PIXELS 픽셀은 화면에 보이도록
        if y < 0:
            y = 0
        elif y > screen_height - cls.MIN_VISIBLE_PIXELS:
            y = screen_height - height
        
        return x, y
    
    @classmethod
    def _validate_bounds(
        cls, x: int, y: int, width: int, height: int,
        screen_width: int, screen_height: int
    ) -> tuple:
        """
        윈도우 위치가 화면 범위 내에 있는지 검증하고 보정 (하위 호환성)
        
        Returns:
            tuple: (x, y, width, height) 보정된 값
        """
        x, y = cls._validate_position(x, y, width, height, screen_width, screen_height)
        return x, y, width, height
    
    @classmethod
    def _center_window(cls, window: ctk.CTk):
        """윈도우를 화면 중앙에 배치"""
        window.update_idletasks()
        
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        window.geometry(f"+{x}+{y}")
    
    @classmethod
    def is_position_valid(cls, x: int, y: int, screen_width: int, screen_height: int) -> bool:
        """
        주어진 위치가 화면 범위 내에 있는지 확인
        
        Args:
            x, y: 윈도우 위치
            screen_width, screen_height: 화면 크기
            
        Returns:
            bool: 유효한 위치인지 여부
        """
        return (
            x >= -cls.DEFAULT_WIDTH + cls.MIN_VISIBLE_PIXELS and
            x <= screen_width - cls.MIN_VISIBLE_PIXELS and
            y >= 0 and
            y <= screen_height - cls.MIN_VISIBLE_PIXELS
        )
