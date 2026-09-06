#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
==============================================================================
파일: gui/utils/state_manager.py
역할 및 목적:
    GUI 윈도우의 이전 위치, 크기, 상태를 로컬 JSON(`config/gui_state.json`)에 저장 및 복원하는 관리자.
    다중 모니터 분리 시 화면 밖으로 벗어나는 현상을 방지(오프스크린 보정)합니다.
주요 구성 요소:
    - WindowStateManager: 윈도우 상태 저장/복원 클래스
    - load_state(), save_state(): 상태 입출력 메서드
    - is_valid_position(): 가시 영역 내 위치 유효성 검사
상호 연관 관계 및 의존성:
    - Caller: gui.main_window.MainWindow
    - Callee: config/gui_state.json
수정 시 주의사항:
    - 사용자가 듀얼 모니터를 사용하다가 단일 모니터로 변경했을 때 창이 화면 밖에 뜨지 않도록 경계 검사를 유지해야 합니다.
==============================================================================
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
