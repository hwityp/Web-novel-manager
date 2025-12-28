#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tooltip Manager

비차단(Non-blocking) 툴팁 시스템을 제공합니다.
마우스 호버 시 지연 후 툴팁을 표시하고, 마우스가 떠나면 숨깁니다.

Validates: Requirements 6.2, 6.3, 6.5
"""
import tkinter as tk
from typing import Optional


# 툴팁 스타일 상수
TOOLTIP_BG = "#1e1e1e"
TOOLTIP_FG = "#FFFFFF"
TOOLTIP_BORDER = "#4A90D9"
TOOLTIP_FONT = ("Segoe UI", 11)
TOOLTIP_DELAY = 500  # ms
TOOLTIP_WRAP_LENGTH = 300


class TooltipManager:
    """비차단 툴팁 관리자"""
    
    def __init__(
        self,
        widget,
        text: str,
        delay: int = TOOLTIP_DELAY,
        wrap_length: int = TOOLTIP_WRAP_LENGTH
    ):
        """
        TooltipManager 초기화
        
        Args:
            widget: 툴팁을 연결할 위젯
            text: 툴팁에 표시할 텍스트
            delay: 툴팁 표시 지연 시간 (ms)
            wrap_length: 텍스트 줄바꿈 너비 (px)
        """
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wrap_length = wrap_length
        self.tooltip_window: Optional[tk.Toplevel] = None
        self.scheduled_id: Optional[str] = None
        
        # 이벤트 바인딩
        widget.bind("<Enter>", self._schedule_show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
    
    def _schedule_show(self, event=None):
        """지연 후 툴팁 표시 예약"""
        self._cancel_scheduled()
        self.scheduled_id = self.widget.after(self.delay, self._show)
    
    def _cancel_scheduled(self):
        """예약된 툴팁 표시 취소"""
        if self.scheduled_id:
            self.widget.after_cancel(self.scheduled_id)
            self.scheduled_id = None
    
    def _show(self):
        """툴팁 표시"""
        if self.tooltip_window:
            return
        
        # 위젯 위치 계산
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        except tk.TclError:
            return
        
        # 툴팁 윈도우 생성
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        # 툴팁이 항상 최상위에 표시되도록
        self.tooltip_window.wm_attributes("-topmost", True)
        
        # 프레임 (테두리 효과)
        frame = tk.Frame(
            self.tooltip_window,
            background=TOOLTIP_BG,
            borderwidth=1,
            relief="solid",
            highlightbackground=TOOLTIP_BORDER,
            highlightthickness=1
        )
        frame.pack()
        
        # 텍스트 레이블
        label = tk.Label(
            frame,
            text=self.text,
            background=TOOLTIP_BG,
            foreground=TOOLTIP_FG,
            font=TOOLTIP_FONT,
            padx=10,
            pady=6,
            wraplength=self.wrap_length,
            justify="left"
        )
        label.pack()
        
        # 화면 범위 체크 및 위치 조정
        self._adjust_position()
    
    def _adjust_position(self):
        """툴팁이 화면 밖으로 나가지 않도록 위치 조정"""
        if not self.tooltip_window:
            return
        
        try:
            self.tooltip_window.update_idletasks()
            
            # 현재 위치 및 크기
            tooltip_width = self.tooltip_window.winfo_width()
            tooltip_height = self.tooltip_window.winfo_height()
            tooltip_x = self.tooltip_window.winfo_x()
            tooltip_y = self.tooltip_window.winfo_y()
            
            # 화면 크기
            screen_width = self.tooltip_window.winfo_screenwidth()
            screen_height = self.tooltip_window.winfo_screenheight()
            
            # X 위치 조정
            if tooltip_x + tooltip_width > screen_width:
                tooltip_x = screen_width - tooltip_width - 10
            
            # Y 위치 조정 (아래로 넘어가면 위로 표시)
            if tooltip_y + tooltip_height > screen_height:
                tooltip_y = self.widget.winfo_rooty() - tooltip_height - 5
            
            self.tooltip_window.wm_geometry(f"+{tooltip_x}+{tooltip_y}")
        except tk.TclError:
            pass
    
    def _hide(self, event=None):
        """툴팁 숨기기"""
        self._cancel_scheduled()
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except tk.TclError:
                pass
            self.tooltip_window = None
    
    def update_text(self, new_text: str):
        """툴팁 텍스트 업데이트"""
        self.text = new_text
        # 현재 표시 중이면 다시 표시
        if self.tooltip_window:
            self._hide()
            self._show()
    
    def destroy(self):
        """툴팁 매니저 정리"""
        self._hide()
        try:
            self.widget.unbind("<Enter>")
            self.widget.unbind("<Leave>")
            self.widget.unbind("<ButtonPress>")
        except tk.TclError:
            pass


def create_tooltip(widget, text: str, delay: int = TOOLTIP_DELAY) -> TooltipManager:
    """
    위젯에 툴팁을 추가하는 헬퍼 함수
    
    Args:
        widget: 툴팁을 연결할 위젯
        text: 툴팁 텍스트
        delay: 표시 지연 시간 (ms)
        
    Returns:
        TooltipManager: 생성된 툴팁 매니저
    """
    return TooltipManager(widget, text, delay)
