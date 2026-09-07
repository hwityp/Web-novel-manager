#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
==============================================================================
파일: gui/main_window.py
역할 및 목적:
    WNAP Manager 애플리케이션의 메인 사용자 인터페이스(GUI).
    CustomTkinter 기반의 다크 테마 GUI로, 소스 폴더 선택, 옵션 설정(dry-run, 안전모드 등),
    파이프라인 실행 제어(시작/일시정지/취소), 실시간 진행률(Progress Bar) 표시,
    처리 결과 목록(Treeview) 시각화 및 수동 장르 확인 대화상자 인터랙션을 제공합니다.
주요 구성 요소:
    - MainWindow: 메인 윈도우 클래스
    - _run_pipeline_thread(): 백그라운드 스레드에서 PipelineOrchestrator 구동
    - _update_progress(), _update_treeview(): UI 스레드 안전 갱신
상호 연관 관계 및 의존성:
    - Caller: main.py
    - Callee: core.pipeline_orchestrator.PipelineOrchestrator, core.pipeline_logger.PipelineLogger,
              gui.genre_confirm_dialog.show_genre_confirm_dialog, gui.utils.*, config.pipeline_config
수정 시 주의사항:
    - 파이프라인 처리는 긴 I/O 작업이므로 반드시 백그라운드 워커 스레드에서 실행하고, UI 갱신은 큐 또는 `root.after()`를 통해야 스레드 경합(Freeze)이 발생하지 않습니다.
==============================================================================
"""
import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
import threading
import queue
import os
import subprocess
import sys
from datetime import datetime
import json

from config.pipeline_config import PipelineConfig, GENRE_WHITELIST
from core.pipeline_orchestrator import PipelineOrchestrator, PipelineResult
from core.pipeline_logger import PipelineLogger
from core.novel_task import NovelTask
from core.path_utils import get_config_path
from core.version import __version__, get_full_version
from gui.genre_confirm_dialog import show_genre_confirm_dialog
from gui.utils.state_manager import WindowStateManager
from gui.utils.tooltip_manager import TooltipManager, create_tooltip


# ============================================================================
# 테마 및 스타일 상수 정의 (고대비 테마)
# ============================================================================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# 폰트 설정
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

# 폰트 크기 (시인성 향상)
FONT_SIZE_SMALL = 14
FONT_SIZE_BASE = 16
FONT_SIZE_MEDIUM = 18
FONT_SIZE_LARGE = 20
FONT_SIZE_XLARGE = 22
FONT_SIZE_DASHBOARD = 28

# 고대비 테마 딕셔너리
THEME = {
    # 배경색 (밝은 다크 그레이)
    "bg_main": "#2b2b2b",
    "bg_card": "#363636",
    "bg_card_hover": "#404040",
    "bg_input": "#1e1e1e",
    "bg_highlight": "#4a4a4a",
    
    # 텍스트 색상 (고대비)
    "text_primary": "#FFFFFF",
    "text_secondary": "#E0E0E0",
    "text_muted": "#B0B0B0",
    
    # 버튼 텍스트 색상 (최대 시인성)
    "button_text": "#FFFFFF",
    "button_text_disabled": "#808080",
    
    # 강조 색상 (더 밝게 조정)
    "accent_blue": "#5A9FE9",
    "accent_blue_hover": "#6BB0FA",
    "accent_green": "#5DBF60",
    "accent_green_hover": "#6ED071",
    "accent_gray": "#707070",
    "accent_gray_hover": "#808080",
    
    # 상태 색상
    "status_success": "#4ade80",
    "status_error": "#f87171",
    "status_warning": "#fbbf24",
    "status_skipped": "#94a3b8",
    
    # 프로그레스 바 색상
    "progress_dryrun": "#87CEEB",    # 하늘색
    "progress_execute": "#4ade80",   # 초록색
    
    # 테이블 색상
    "table_bg": "#2b2b2b",
    "table_header": "#404040",
    "table_row_odd": "#2b2b2b",
    "table_row_even": "#333333",
    "table_selected": "#4A90D9",
    "table_border": "#505050",
}

# 패딩 및 여백
PADDING_SMALL = 8
PADDING_BASE = 12
PADDING_LARGE = 15
PADDING_XLARGE = 20

# 버튼 크기
BUTTON_HEIGHT = 45
BUTTON_WIDTH_SMALL = 110
BUTTON_WIDTH_MEDIUM = 140
BUTTON_CORNER_RADIUS = 10

# 툴팁 텍스트
TOOLTIP_TEXTS = {
    "dry_run": "Dry-run 모드: 실제 파일을 이동하지 않고\n미리보기만 수행합니다.\n결과를 확인한 후 실제 실행을 진행하세요.",
    "log_level": "로그 레벨: 기록할 로그의 상세 수준을 설정합니다.\n• DEBUG: 모든 상세 정보\n• INFO: 일반 정보\n• WARNING: 경고만\n• ERROR: 오류만",
    "confirm_dialog": "실행 전 확인: 파이프라인 실행 전에\n확인 대화상자를 표시합니다.\n실수로 인한 파일 이동을 방지합니다.",
    "save_settings": "현재 설정을 저장합니다.\n다음 실행 시 자동으로 불러옵니다.",
    "source_folder": "정리할 웹소설 파일들이 있는 폴더를 선택하세요.",
    "target_folder": "정리된 파일들이 저장될 폴더입니다.\n비워두면 소스폴더/정리완료 에 저장됩니다.",
    "manage_dict": "장르 사전 관리: 중국 웹소설 음독 패턴 및 통합 장르 키워드 사전을 최적화/동기화합니다.",
}


class EditNameDialog(ctk.CTkToplevel):
    """파일명/장르 편집 다이얼로그 (초기값 지원)"""
    def __init__(self, parent, title: str, initial_value: str = ""):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        
        # 모달 설정
        self.transient(parent)
        self.grab_set()
        
        # 중앙 배치
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 90
        self.geometry(f"+{x}+{y}")
        
        self.result = None
        
        # UI 구성
        self.configure(fg_color=THEME["bg_card"])
        
        # title에 '장르' 포함 시 안내문 변경
        prompt_text = "새로운 장르를 입력하세요:" if "장르" in title else "새로운 파일명을 입력하세요:"
        label = ctk.CTkLabel(
            self, text=prompt_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            text_color=THEME["text_primary"]
        )
        label.pack(pady=(20, 10))
        
        self.entry = ctk.CTkEntry(
            self, width=300,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            fg_color=THEME["bg_input"], text_color=THEME["text_primary"]
        )
        self.entry.pack(pady=10)
        self.entry.insert(0, initial_value)
        self.entry.focus_set()
        self.entry.bind("<Return>", self._on_ok)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ok_btn = ctk.CTkButton(
            btn_frame, text="확인", width=100,
            fg_color=THEME["accent_blue"], hover_color=THEME["accent_blue_hover"],
            command=self._on_ok
        )
        ok_btn.pack(side="left", padx=10)
        
        cancel_btn = ctk.CTkButton(
            btn_frame, text="취소", width=100,
            fg_color=THEME["accent_gray"], hover_color=THEME["accent_gray_hover"],
            command=self.destroy
        )
        cancel_btn.pack(side="left", padx=10)
        
        self.wait_window()

    def _on_ok(self, event=None):
        self.result = self.entry.get()
        self.destroy()
    
    def get_input(self):
        return self.result


class WNAPMainWindow(ctk.CTk):
    """WNAP 메인 윈도우 - 프로페셔널 에디션 v2"""
    
    def __init__(self, log_level: str = "INFO"):
        super().__init__()
        
        # 윈도우 설정
        self.title(f"WNAP - Web Novel Archive Pipeline v{__version__}")
        self.configure(fg_color=THEME["bg_main"])
        self.minsize(1100, 700)
        
        # 윈도우 상태 복원
        WindowStateManager.restore_state(self)
        
        # 설정 로드
        self.config = self._load_config()
        self.config.log_level = log_level # CLI 인자 우선 적용
        
        # 파일 로거 초기화 (GUI 모드: 콘솔 출력 비활성화 - CLI에서 제어함)
        # 단, CLI --log-level이 있으면 그것을 따름
        self.file_logger = PipelineLogger(
            log_level=self.config.log_level,
            log_dir=Path("logs"),
            console_output=True # CLI에서 제어함
        )
        
        # 상태 변수
        self.is_running = False
        self.step_folder_done = False
        self.step_normalize_done = False
        self.step_genre_done = False
        self.progress_queue = queue.Queue()
        self.genre_confirm_queue = queue.Queue()
        self.genre_confirm_response = queue.Queue()
        self.last_result: Optional[PipelineResult] = None
        self.last_mapping_csv: Optional[Path] = None
        self.last_target_folder: Optional[Path] = None
        self.tasks_cache: List[NovelTask] = []  # 더블클릭용 태스크 캐시
        
        # 비활성화할 위젯 목록 (실행 중)
        self.disable_on_run: List[ctk.CTkBaseClass] = []
        
        # 툴팁 매니저 목록
        self.tooltips: List[TooltipManager] = []
        
        # UI 구성
        self._create_widgets()
        self._load_config_to_ui()
        
        # 타이머 설정
        self.after(50, self._process_progress_queue)
        self.after(100, self._process_genre_confirm_queue)
        
        # 윈도우 종료 시 상태 저장
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _on_closing(self):
        """윈도우 종료 시 상태 저장"""
        try:
            # 1. 마지막 설정 저장 (폴더 경로 등)
            config_path = get_config_path()
            self._update_config_from_ui()
            self.config.save(config_path)
        except Exception as e:
            # 종료 중 오류는 무시하거나 콘솔에만 출력
            print(f"설정 저장 실패: {e}")
            
        # 2. 윈도우 상태 저장
        WindowStateManager.save_state(self)
        self.file_logger.close()
        self.destroy()
    
    def _load_config(self) -> PipelineConfig:
        """설정 파일 로드"""
        config_path = get_config_path()
        if config_path.exists():
            return PipelineConfig.load(config_path)
        return PipelineConfig()
    
    def _save_config(self):
        """현재 설정을 파일에 저장"""
        config_path = get_config_path()
        self._update_config_from_ui()
        self.config.save(config_path)
        self._log_to_file("설정이 저장되었습니다.")
        messagebox.showinfo("알림", "설정이 저장되었습니다.")
    
    def _log_to_file(self, message: str):
        """파일에 로그 기록"""
        self.file_logger.info(message)
    
    def _create_widgets(self):
        """UI 위젯 생성 - 옵션 섹션 제거 및 테이블 확장 (v1.3.2)"""
        # 메인 컨테이너 설정
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=10) # 결과 테이블 (최대 확장)
        self.grid_rowconfigure(2, weight=0)  # 버튼 영역 (고정)

        
        # === 상단: 폴더 설정 + 대시보드 ===
        self._create_top_section()
        
        # === 옵션 섹션 (삭제) ===
        # self._create_options_section()
        
        # === 결과 테이블 + 프로그레스 바 ===
        self._create_result_table_section()
        
        # === 실행 버튼 ===
        self._create_action_buttons()

    def _create_top_section(self):
        """상단 섹션: 폴더 설정 카드 + 대시보드 위젯"""
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=PADDING_LARGE, pady=(PADDING_LARGE, PADDING_BASE), sticky="ew")
        top_frame.grid_columnconfigure(0, weight=2)
        top_frame.grid_columnconfigure(1, weight=1)
        
        self._create_folder_card(top_frame)
        self._create_dashboard_widget(top_frame)
    
    def _create_folder_card(self, parent):
        """폴더 설정 카드 생성"""
        folder_card = ctk.CTkFrame(
            parent, 
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["accent_blue"]
        )
        folder_card.grid(row=0, column=0, padx=(0, PADDING_BASE), pady=0, sticky="nsew")
        folder_card.grid_columnconfigure(1, weight=1)
        
        # 카드 제목
        title_frame = ctk.CTkFrame(folder_card, fg_color="transparent")
        title_frame.grid(row=0, column=0, columnspan=3, padx=PADDING_LARGE, pady=(PADDING_LARGE, PADDING_BASE), sticky="w")
        
        title_label = ctk.CTkLabel(
            title_frame, 
            text="📁 폴더 설정",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LARGE, weight="bold"),
            text_color=THEME["text_primary"]
        )
        title_label.pack(side="left")
        
        # 소스 폴더
        source_frame = ctk.CTkFrame(folder_card, fg_color="transparent")
        source_frame.grid(row=1, column=0, padx=(PADDING_LARGE, PADDING_BASE), pady=PADDING_BASE, sticky="w")
        
        source_label = ctk.CTkLabel(
            source_frame, 
            text="소스 폴더:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            text_color=THEME["text_secondary"]
        )
        source_label.pack(side="left")
        
        source_help = ctk.CTkLabel(source_frame, text=" (?)", text_color=THEME["accent_blue"],
                                   font=ctk.CTkFont(size=FONT_SIZE_SMALL))
        source_help.pack(side="left")
        self.tooltips.append(create_tooltip(source_help, TOOLTIP_TEXTS["source_folder"]))
        
        self.source_entry = ctk.CTkEntry(
            folder_card, 
            placeholder_text="정리할 폴더 경로를 선택하세요",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            height=38,
            corner_radius=8,
            fg_color=THEME["bg_input"],
            text_color=THEME["text_primary"]
        )
        self.source_entry.grid(row=1, column=1, padx=PADDING_SMALL, pady=PADDING_BASE, sticky="ew")
        # 입력 변경 시 실행 버튼 비활성화 (재분석 유도)
        self.source_entry.bind("<KeyRelease>", lambda e: self._on_input_changed())
        
        self.source_btn = ctk.CTkButton(
            folder_card, 
            text="찾아보기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE, weight="bold"),
            width=BUTTON_WIDTH_SMALL,
            height=38,
            corner_radius=8,
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
            text_color=THEME["button_text"],
            text_color_disabled=THEME["button_text_disabled"],
            command=self._browse_source_folder
        )
        self.source_btn.grid(row=1, column=2, padx=(PADDING_SMALL, PADDING_LARGE), pady=PADDING_BASE)
        self.disable_on_run.append(self.source_btn)
        
        # 타겟 폴더
        target_frame = ctk.CTkFrame(folder_card, fg_color="transparent")
        target_frame.grid(row=2, column=0, padx=(PADDING_LARGE, PADDING_BASE), pady=(0, PADDING_LARGE), sticky="w")
        
        target_label = ctk.CTkLabel(
            target_frame, 
            text="타겟 폴더:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            text_color=THEME["text_secondary"]
        )
        target_label.pack(side="left")
        
        target_help = ctk.CTkLabel(target_frame, text=" (?)", text_color=THEME["accent_blue"],
                                   font=ctk.CTkFont(size=FONT_SIZE_SMALL))
        target_help.pack(side="left")
        self.tooltips.append(create_tooltip(target_help, TOOLTIP_TEXTS["target_folder"]))
        
        self.target_entry = ctk.CTkEntry(
            folder_card, 
            placeholder_text="결과물이 저장될 폴더 (기본: 소스폴더/정리완료)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            height=38,
            corner_radius=8,
            fg_color=THEME["bg_input"],
            text_color=THEME["text_primary"],
            textvariable=ctk.StringVar()
        )
        self.target_entry.grid(row=2, column=1, padx=PADDING_SMALL, pady=(0, PADDING_LARGE), sticky="ew")
        # 입력 변경 시 실행 버튼 비활성화 (재분석 유도)
        self.target_entry.bind("<KeyRelease>", lambda e: self._on_input_changed())
        
        self.target_btn = ctk.CTkButton(
            folder_card,
            text="찾아보기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE, weight="bold"),
            width=BUTTON_WIDTH_SMALL,
            height=38,
            corner_radius=8,
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
            text_color=THEME["button_text"],
            text_color_disabled=THEME["button_text_disabled"],
            command=self._browse_target_folder
        )
        self.target_btn.grid(row=2, column=2, padx=(PADDING_SMALL, PADDING_LARGE), pady=(0, PADDING_LARGE))
        self.disable_on_run.append(self.target_btn)

    
    def _create_dashboard_widget(self, parent):
        """대시보드 위젯 생성 - 실행 결과 요약"""
        dashboard_card = ctk.CTkFrame(
            parent,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["accent_blue"]
        )
        dashboard_card.grid(row=0, column=1, padx=0, pady=0, sticky="nsew")
        
        # 제목
        title_label = ctk.CTkLabel(
            dashboard_card,
            text="📊 실행 결과",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LARGE, weight="bold"),
            text_color=THEME["text_primary"]
        )
        title_label.pack(anchor="w", padx=PADDING_LARGE, pady=(PADDING_LARGE, PADDING_BASE))
        
        # 통계 그리드
        stats_frame = ctk.CTkFrame(dashboard_card, fg_color="transparent")
        stats_frame.pack(fill="x", padx=PADDING_LARGE, pady=(0, PADDING_BASE))
        stats_frame.grid_columnconfigure((0, 1), weight=1)
        
        self._create_stat_item(stats_frame, 0, 0, "총 파일", "-", THEME["text_primary"], "total")
        self._create_stat_item(stats_frame, 0, 1, "✓ 성공", "-", THEME["status_success"], "success")
        self._create_stat_item(stats_frame, 1, 0, "✗ 실패", "-", THEME["status_error"], "failed")
        self._create_stat_item(stats_frame, 1, 1, "⊘ 건너뜀", "-", THEME["status_skipped"], "skipped")
        
        # 상태 표시
        self.status_label = ctk.CTkLabel(
            dashboard_card,
            text="⏸ 대기 중",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            text_color=THEME["text_muted"]
        )
        self.status_label.pack(anchor="w", padx=PADDING_LARGE, pady=(0, PADDING_LARGE))
    
    def _create_stat_item(self, parent, row, col, label_text, value, color, attr_name):
        """통계 아이템 생성"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=col, padx=PADDING_SMALL, pady=PADDING_SMALL, sticky="w")
        
        label = ctk.CTkLabel(
            frame,
            text=label_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL),
            text_color=THEME["text_muted"]
        )
        label.pack(anchor="w")
        
        value_label = ctk.CTkLabel(
            frame,
            text=value,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_DASHBOARD, weight="bold"),
            text_color=color
        )
        value_label.pack(anchor="w")
        
        setattr(self, f"stat_{attr_name}_label", value_label)

    # def _create_options_section(self): # REMOVED
    def _create_result_table_section(self):
        """결과 테이블 섹션 생성 - 확장 레이아웃, 프로그레스 바 포함"""
        table_card = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["accent_blue"]
        )
        table_card.grid(row=1, column=0, padx=PADDING_LARGE, pady=PADDING_BASE, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(1, weight=1)
        
        # 헤더
        header_frame = ctk.CTkFrame(table_card, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=PADDING_LARGE, pady=(PADDING_LARGE, PADDING_BASE), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="📋 처리 결과 테이블 (더블클릭: 폴더 열기)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LARGE, weight="bold"),
            text_color=THEME["text_primary"]
        )
        title_label.pack(side="left")
        
        # 버튼들
        self.manage_dict_btn = ctk.CTkButton(
            header_frame,
            text="📚 사전 관리",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL, weight="bold"),
            width=105,
            height=32,
            corner_radius=8,
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
            text_color=THEME["button_text"],
            text_color_disabled=THEME["button_text_disabled"],
            state="normal",
            command=self._open_genre_dictionary_dialog
        )
        self.manage_dict_btn.pack(side="right", padx=(PADDING_SMALL, 0))
        self.tooltips.append(create_tooltip(self.manage_dict_btn, TOOLTIP_TEXTS["manage_dict"]))
        self.disable_on_run.append(self.manage_dict_btn)
        
        self.save_csv_btn = ctk.CTkButton(
            header_frame,
            text="💾 CSV 저장", # Renamed
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL, weight="bold"),
            width=100,
            height=32,
            corner_radius=8,
            fg_color=THEME["accent_gray"],
            hover_color=THEME["accent_gray_hover"],
            text_color=THEME["button_text"],
            text_color_disabled=THEME["button_text_disabled"],
            state="disabled",
            command=self._save_to_csv # Changed handler
        )
        self.save_csv_btn.pack(side="right", padx=(PADDING_SMALL, 0))
        
        self.open_folder_btn = ctk.CTkButton(
            header_frame,
            text="📂 폴더 열기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL, weight="bold"),
            width=100,
            height=32,
            corner_radius=8,
            fg_color=THEME["accent_gray"],
            hover_color=THEME["accent_gray_hover"],
            text_color=THEME["button_text"],
            text_color_disabled=THEME["button_text_disabled"],
            state="normal", # Always normal, manages internal logic
            command=self._open_target_folder
        )
        self.open_folder_btn.pack(side="right", padx=(PADDING_SMALL, 0))
        
        # Treeview 스타일 설정 (고대비)
        self._configure_treeview_style()
        
        # Treeview 컨테이너
        tree_container = ctk.CTkFrame(table_card, fg_color=THEME["table_bg"], corner_radius=8)
        tree_container.grid(row=1, column=0, padx=PADDING_LARGE, pady=(0, PADDING_BASE), sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)
        
        # Treeview
        columns = ("original", "normalized", "genre", "confidence", "source")
        self.result_tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            selectmode="browse",
            style="Custom.Treeview"
        )
        
        # 컬럼 설정 (클릭 시 소트)
        self.result_tree.heading("original", text="원본 파일명", command=lambda: self._sort_treeview("original", False))
        self.result_tree.heading("normalized", text="정규화 파일명", command=lambda: self._sort_treeview("normalized", False))
        self.result_tree.heading("genre", text="장르", command=lambda: self._sort_treeview("genre", False))
        self.result_tree.heading("confidence", text="신뢰도", command=lambda: self._sort_treeview("confidence", False))
        self.result_tree.heading("source", text="판단근거", command=lambda: self._sort_treeview("source", False))
        
        self.result_tree.column("original", width=200, minwidth=150)
        self.result_tree.column("normalized", width=500, minwidth=300) # 가용 공간 최대 활용
        self.result_tree.column("genre", width=360, minwidth=360, stretch=False)
        self.result_tree.column("confidence", width=120, minwidth=120, stretch=False)
        self.result_tree.column("source", width=150, minwidth=150, stretch=False)
        
        # 상태별 태그 스타일 (Row Coloring)
        self.result_tree.tag_configure("completed", background="#1E3A2A", foreground="#FFFFFF")
        self.result_tree.tag_configure("skipped", background="#404040", foreground="#AAAAAA")
        self.result_tree.tag_configure("failed", background="#4A1E1E", foreground="#FF9999")
        
        # 더블클릭 이벤트 바인딩
        self.result_tree.bind("<Double-1>", self._on_treeview_double_click)
        
        # 스크롤바
        y_scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.result_tree.yview)
        x_scrollbar = ttk.Scrollbar(tree_container, orient="horizontal", command=self.result_tree.xview)
        self.result_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # 배치
        self.result_tree.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # 프로그레스 프레임 (로그 섹션 대신 여기에 배치)
        progress_frame = ctk.CTkFrame(table_card, fg_color="transparent")
        progress_frame.grid(row=2, column=0, padx=PADDING_LARGE, pady=(PADDING_BASE, PADDING_LARGE), sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)
        
        # 프로그레스 바
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=14,
            corner_radius=7,
            progress_color=THEME["progress_dryrun"]  # 기본: 하늘색 (dry-run)
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, PADDING_SMALL))
        self.progress_bar.set(0)
        
        # 진행 상황 레이블
        self.progress_label = ctk.CTkLabel(
            progress_frame, 
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL),
            text_color=THEME["text_muted"]
        )
        self.progress_label.grid(row=1, column=0, sticky="w")
    
    def _configure_treeview_style(self):
        """Treeview 고대비 스타일 설정"""
        style = ttk.Style()
        style.theme_use("clam")
        
        # 기본 Treeview 스타일
        style.configure(
            "Custom.Treeview",
            background=THEME["table_bg"],
            foreground=THEME["text_primary"],
            fieldbackground=THEME["table_bg"],
            rowheight=38, # 높이 증가
            font=(FONT_FAMILY, int(FONT_SIZE_BASE * 1.2)), # 폰트 1.2배
            borderwidth=0
        )
        
        # 헤더 스타일
        style.configure(
            "Custom.Treeview.Heading",
            background=THEME["table_header"],
            foreground=THEME["text_primary"],
            font=(FONT_FAMILY, FONT_SIZE_BASE, 'bold'),
            padding=(10, 8),
            borderwidth=1,
            relief="solid"
        )
        
        # 선택 상태
        style.map(
            "Custom.Treeview",
            background=[("selected", THEME["table_selected"])],
            foreground=[("selected", THEME["text_primary"])]
        )
        
        # 선택 상태
        style.map(
            "Custom.Treeview",
            background=[("selected", THEME["table_selected"])],
            foreground=[("selected", THEME["text_primary"])]
        )
    
    def _create_action_buttons(self):
        """실행 버튼 섹션 생성 - 5단계 버튼 (WNAP v1.3.0)"""
        button_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["accent_blue"]
        )
        button_frame.grid(row=2, column=0, padx=PADDING_LARGE, pady=(PADDING_BASE, PADDING_LARGE), sticky="ew")
        for i in range(6):
            button_frame.grid_columnconfigure(i, weight=1)
            
        # 버튼 높이 1.5배 (약 68px)
        BTN_H = int(BUTTON_HEIGHT * 1.5)
        
        # 1. 폴더 정리
        self.btn_folder = ctk.CTkButton(
            button_frame, text="1. 폴더 정리",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BTN_H, corner_radius=BUTTON_CORNER_RADIUS,
            fg_color=THEME["accent_gray"], hover_color=THEME["accent_gray_hover"],
            command=self._on_btn_folder_click
        )
        self.btn_folder.grid(row=0, column=0, padx=(PADDING_LARGE, PADDING_SMALL), pady=PADDING_LARGE, sticky="ew")
        
        # 2. 파일명 정규화
        self.btn_normalize = ctk.CTkButton(
            button_frame, text="2. 파일명 정규화",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BTN_H, corner_radius=BUTTON_CORNER_RADIUS,
            fg_color=THEME["accent_gray"], hover_color=THEME["accent_gray_hover"],
            text_color_disabled="#D0D0D0",
            state="disabled",
            command=self._on_btn_normalize_click
        )
        self.btn_normalize.grid(row=0, column=1, padx=PADDING_SMALL, pady=PADDING_LARGE, sticky="ew")
        
        # [NEW] 소스 폴더 즉시 적용 버튼 (동일 라인 배치)
        self.btn_apply_source = ctk.CTkButton(
            button_frame, text="소스 폴더에 저장",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BTN_H, corner_radius=BUTTON_CORNER_RADIUS,
            fg_color=THEME["accent_green"], hover_color="#2ECC71",
            text_color="#FFFFFF",
            text_color_disabled="#D0D0D0",
            state="disabled",
            command=self._on_btn_apply_source_click
        )
        self.btn_apply_source.grid(row=0, column=2, padx=PADDING_SMALL, pady=PADDING_LARGE, sticky="ew")
        
        # 비활성화 목록에 버튼 추가
        self.disable_on_run.append(self.btn_apply_source)
        
        # 3. 장르 추론 및 실행 (Glow Effect)
        self.btn_genre = ctk.CTkButton(
            button_frame, text="3. 장르 추론/실행",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BTN_H, corner_radius=BUTTON_CORNER_RADIUS,
            fg_color=THEME["accent_blue"], hover_color=THEME["accent_blue_hover"],
            border_width=2, border_color="#89CFF0",
            text_color="#FFFFFF",
            text_color_disabled="#D0D0D0",
            state="disabled",
            command=self._on_btn_genre_click
        )
        self.btn_genre.grid(row=0, column=3, padx=PADDING_SMALL, pady=PADDING_LARGE, sticky="ew")
        
        # 4. 일괄 처리 (Blue Color)
        self.btn_batch = ctk.CTkButton(
            button_frame, text="⚡ 일괄 처리",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BTN_H, corner_radius=BUTTON_CORNER_RADIUS,
            fg_color="#2980B9", hover_color="#3498DB",
            text_color="#FFFFFF",
            text_color_disabled="#D0D0D0",
            border_width=0,
            command=self._on_btn_batch_click
        )
        self.btn_batch.grid(row=0, column=4, padx=PADDING_SMALL, pady=PADDING_LARGE, sticky="ew")
        
        # 5. 초기화
        self.btn_reset = ctk.CTkButton(
            button_frame, text="↺ 초기화",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BTN_H, corner_radius=BUTTON_CORNER_RADIUS,
            fg_color=THEME["status_error"], hover_color="#FCA5A5",
            command=self._on_btn_reset_click
        )
        self.btn_reset.grid(row=0, column=5, padx=(PADDING_SMALL, PADDING_LARGE), pady=PADDING_LARGE, sticky="ew")

        # 실행 중 비활성화할 버튼 목록 업데이트
        self.disable_on_run.extend([
            self.btn_folder, self.btn_normalize, self.btn_genre, self.btn_batch, self.btn_reset
        ])

    def _on_input_changed(self):
        """입력 변경 시 실행 버튼 비활성화 (재분석 유도)"""
        if hasattr(self, 'run_btn'):
            self.run_btn.configure(state="disabled")

    # ========================================================================
    # 이벤트 핸들러
    # ========================================================================
    
    def _browse_source_folder(self):
        """소스 폴더 선택 다이얼로그"""
        folder = filedialog.askdirectory(title="소스 폴더 선택")
        if folder:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, folder)
            self._log_to_file(f"소스 폴더 선택: {folder}")
            self._on_input_changed() # 경로 변경 시 상태 초기화
    
    def _browse_target_folder(self):
        """타겟 폴더 선택 다이얼로그"""
        folder = filedialog.askdirectory(title="타겟 폴더 선택")
        if folder:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, folder)
            self._log_to_file(f"타겟 폴더 선택: {folder}")
            self._on_input_changed() # 경로 변경 시 상태 초기화
    
    def _load_config_to_ui(self):
        """설정을 UI에 반영"""
        if self.config.source_folder:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, self.config.source_folder)
        
        if self.config.target_folder:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, self.config.target_folder)
        

        # self.log_level_var.set(self.config.log_level) # Removed
    
    def _update_config_from_ui(self):
        """UI 값을 설정에 반영"""
        self.config.source_folder = self.source_entry.get()
        self.config.target_folder = self.target_entry.get() or "정리완료"
        # dry_run은 실행 시 결정됨
        # self.config.log_level = self.log_level_var.get() # Removed
    
    def _process_progress_queue(self):
        """진행 상황 큐 처리 (메인 스레드에서 실행)"""
        try:
            while True:
                data = self.progress_queue.get_nowait()
                # data format: (current, total, filename) or (current, total, filename, task)
                current, total, filename = data[0], data[1], data[2]
                task = data[3] if len(data) > 3 else None
                
                progress = current / total if total > 0 else 0
                self.progress_bar.set(progress)
                self.progress_label.configure(text=f"[{current}/{total}] {filename}")
                self.status_label.configure(
                    text=f"⏳ 처리 중 ({current}/{total})",
                    text_color=THEME["status_warning"]
                )
                
                # Real-time Treeview Update
                if task and self.result_tree.exists(str(current - 1)):
                    # current is 1-based index, treeview iid is 0-based index
                    item_id = str(current - 1)
                    
                    # Update values (Genre, Confidence)
                    # Get existing values
                    values = list(self.result_tree.item(item_id, "values"))
                    # (Original, Normalized, Genre, Confidence, Source)
                    # Update Genre, Conf, Source
                    genre = task.genre or "-"
                    confidence = task.confidence or "-"
                    source = task.source or "-"
                    
                    values[2] = genre
                    values[3] = confidence
                    values[4] = source
                    
                    self.result_tree.item(item_id, values=values)
                    
                    # Row Coloring based on status
                    if task.status == 'completed':
                        self.result_tree.item(item_id, tags=('completed',))
                    elif task.status == 'skipped':
                        self.result_tree.item(item_id, tags=('skipped',))
                    elif task.status == 'failed':
                        self.result_tree.item(item_id, tags=('failed',))
                        
                    self.result_tree.see(item_id) # Scroll to item
                    
        except queue.Empty:
            pass
        
        self.after(50, self._process_progress_queue)
    
    def _on_progress(self, *args):
        """진행 상황 콜백 (백그라운드 스레드에서 호출됨)"""
        # args: (current, total, filename, [task])
        self.progress_queue.put(args)
    
    def _process_genre_confirm_queue(self):
        """장르 확인 요청 큐 처리 (메인 스레드에서 실행)"""
        try:
            while True:
                filename, suggested_genre, confidence = self.genre_confirm_queue.get_nowait()
                genre_list = sorted(GENRE_WHITELIST)
                confirmed, selected_genre = show_genre_confirm_dialog(
                    self, filename, suggested_genre, confidence, genre_list
                )
                if confirmed and selected_genre:
                    self.genre_confirm_response.put(selected_genre)
                else:
                    self.genre_confirm_response.put(None)
        except queue.Empty:
            pass
        
        self.after(100, self._process_genre_confirm_queue)
    
    def _on_genre_confirm(self, filename: str, suggested_genre: str, confidence: str) -> Optional[str]:
        """장르 확인 콜백 (백그라운드 스레드에서 호출됨)"""
        # Smart Filter: High confidence -> Auto accept
        # 배치 처리 시 혹은 일반 실행 시에도 피로도를 줄이기 위해 High는 자동 통과
        if confidence and confidence.lower() == 'high':
            # self._log_to_file(f"자동 확정 (High Confidence): {filename} -> {suggested_genre}")
            return suggested_genre

        self.genre_confirm_queue.put((filename, suggested_genre, confidence))
        try:
            selected_genre = self.genre_confirm_response.get(timeout=300)
            return selected_genre
        except queue.Empty:
            return None
    
    def _open_folder_and_select_file(self, folder: Path, file: Path):
        """OS별 폴더 열기 및 파일 선택"""
        try:
            if sys.platform == "win32":
                # Windows: explorer /select,"파일경로"
                subprocess.run(["explorer", "/select,", str(file)])
            elif sys.platform == "darwin":
                # macOS: open -R "파일경로"
                subprocess.run(["open", "-R", str(file)])
            else:
                # Linux: xdg-open (파일 선택 미지원, 폴더만 열기)
                subprocess.run(["xdg-open", str(folder)])
            self._log_to_file(f"폴더 열기: {folder}")
        except Exception as e:
            messagebox.showerror("오류", f"폴더를 열 수 없습니다:\n{e}")

    def _clear_all(self):
        """결과 테이블 초기화"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self._reset_summary()
        self.progress_bar.set(0)
        self.progress_label.configure(text="")
        self.status_label.configure(text="⏸ 대기 중", text_color=THEME["text_muted"])
        self.open_folder_btn.configure(state="disabled")
        self.last_result = None
        self.last_mapping_csv = None
        self.last_target_folder = None
        self.tasks_cache = []
    
    def _reset_summary(self):
        """요약 레이블 초기화"""
        self.stat_total_label.configure(text="-")
        self.stat_success_label.configure(text="-")
        self.stat_failed_label.configure(text="-")
        self.stat_skipped_label.configure(text="-")
    
    def _update_summary(self, result: PipelineResult):
        """요약 레이블 업데이트"""
        self.stat_total_label.configure(text=str(result.total_files))
        self.stat_success_label.configure(text=str(result.processed))
        self.stat_failed_label.configure(text=str(result.failed))
        self.stat_skipped_label.configure(text=str(result.skipped))
    
    def _update_progress_bar_color(self, dry_run: bool):
        """실행 모드에 따른 프로그레스 바 색상 변경"""
        if dry_run:
            color = THEME["progress_dryrun"]  # 하늘색
        else:
            color = THEME["progress_execute"]  # 초록색
        self.progress_bar.configure(progress_color=color)

    
    def _populate_result_table(self, tasks: List[NovelTask]):
        """결과 테이블에 데이터 채우기 (홀수/짝수 행 색상 구분)"""
        # 기존 데이터 삭제
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        # 태스크 캐시 저장 (더블클릭용)
        self.tasks_cache = tasks
        
        # 새 데이터 추가
        for idx, task in enumerate(tasks):
            original = task.raw_name or str(task.original_path.name) if task.original_path else "-"
            normalized = task.metadata.get('normalized_name', '') or \
                        task.metadata.get('target_path', '') or "-"
            if isinstance(normalized, Path):
                normalized = normalized.name
            elif normalized and '/' in str(normalized):
                normalized = Path(normalized).name
            elif normalized and '\\' in str(normalized):
                normalized = Path(normalized).name
            
            # [미분류] 태그 제거 (for UI v1.3.1)
            normalized = str(normalized).replace("[미분류] ", "").strip()
            
            genre = task.genre or "-"
            confidence = task.confidence or "-"
            source = task.source or "-"
            
            # 상태에 따른 태그 + 홀수/짝수 행
            tags = []
            if task.status == "completed":
                tags.append("success")
            elif task.status == "failed":
                tags.append("failed")
            elif task.status == "skipped":
                tags.append("skipped")
            
            # 홀수/짝수 행 색상
            if idx % 2 == 0:
                tags.append("evenrow")
            else:
                tags.append("oddrow")
            
            # iid를 인덱스로 설정하여 더블클릭 시 쉽게 매핑
            self.result_tree.insert("", "end", iid=str(idx), values=(
                original[:50] + "..." if len(original) > 50 else original,
                normalized[:60] + "..." if len(str(normalized)) > 60 else normalized,
                genre,
                confidence,
                source
            ), tags=tuple(tags))
        
        # 태그 색상 설정
        self.result_tree.tag_configure("success", foreground=THEME["status_success"])
        self.result_tree.tag_configure("failed", foreground=THEME["status_error"])
        self.result_tree.tag_configure("skipped", foreground=THEME["status_skipped"])
        self.result_tree.tag_configure("evenrow", background=THEME["table_row_even"])
        self.result_tree.tag_configure("oddrow", background=THEME["table_row_odd"])

    def _save_to_csv(self):
        """[NEW] 현재 목록을 CSV로 저장"""
        if not self.tasks_cache:
            messagebox.showwarning("경고", "저장할 데이터가 없습니다.")
            return

        try:
            # 기본 파일명 생성
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"wnap_list_{timestamp}.csv"
            
            filepath = filedialog.asksaveasfilename(
                title="CSV 저장",
                initialfile=default_name,
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
            )
            
            if not filepath:
                return
                
            # CSV 저장
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["Original", "Normalized", "Genre", "Status", "Confidence", "Source"])
                
                for task in self.tasks_cache:
                    original = task.raw_name or (task.original_path.name if task.original_path else "")
                    normalized = task.metadata.get('normalized_name', '')
                    genre = task.genre or ""
                    status = task.status
                    conf = task.confidence or ""
                    src = task.source or ""
                    writer.writerow([original, normalized, genre, status, conf, src])
                    
            messagebox.showinfo("완료", f"파일이 저장되었습니다:\n{filepath}")
            self._log_to_file(f"CSV 저장 완료: {filepath}")
            
        except Exception as e:
            self._log_to_file(f"CSV 저장 실패: {e}")
            messagebox.showerror("오류", f"CSV 저장 중 오류 발생:\n{e}")

    def _open_target_folder(self):
        """타겟/소스 폴더 열기 (Smart Fallback)"""
        # 1. 실행 결과 타겟 폴더
        folder = self.last_target_folder
        
        # 2. UI 입력값 (Target)
        if not folder or not folder.exists():
            target_input = self.target_entry.get()
            if target_input:
                folder = Path(target_input)
        
        # 3. UI 입력값 (Source) / 정리완료
        if not folder or not folder.exists():
             source_input = self.source_entry.get()
             if source_input:
                 # Check if '정리완료' exists
                 candidate = Path(source_input) / "정리완료"
                 if candidate.exists():
                     folder = candidate
                 else:
                     # Fallback to Source itself (better than nothing)
                     folder = Path(source_input)

        if folder and folder.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(folder))
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(folder)])
                else:
                    subprocess.run(["xdg-open", str(folder)])
                self._log_to_file(f"폴더 열기: {folder}")
            except Exception as e:
                messagebox.showerror("오류", f"폴더를 열 수 없습니다:\n{e}")
        else:
            messagebox.showwarning("경고", "열 수 있는 폴더를 찾지 못했습니다.\n소스 또는 타겟 폴더를 설정해주세요.")
    
    def _open_genre_dictionary_dialog(self):
        """장르 사전 관리 및 최적화 다이얼로그 오픈"""
        from gui.genre_dictionary_dialog import show_genre_dictionary_dialog
        show_genre_dictionary_dialog(self)
    
    def _sort_treeview(self, col: str, reverse: bool):
        """
        Treeview 컬럼 클릭 시 소트
        
        Args:
            col: 소트할 컬럼 이름
            reverse: 역순 여부
        """
        # 현재 데이터 가져오기
        data = [(self.result_tree.set(item, col), item) for item in self.result_tree.get_children('')]
        
        # 소트 (대소문자 무시)
        data.sort(key=lambda x: x[0].lower() if isinstance(x[0], str) else x[0], reverse=reverse)
        
        # 재배치
        for idx, (val, item) in enumerate(data):
            self.result_tree.move(item, '', idx)
            
            # 홀수/짝수 행 색상 재적용
            current_tags = list(self.result_tree.item(item, 'tags'))
            # 기존 행 색상 태그 제거
            current_tags = [t for t in current_tags if t not in ('evenrow', 'oddrow')]
            # 새 행 색상 태그 추가
            if idx % 2 == 0:
                current_tags.append('evenrow')
            else:
                current_tags.append('oddrow')
            self.result_tree.item(item, tags=tuple(current_tags))
        
        # 다음 클릭 시 역순으로 소트
        self.result_tree.heading(col, command=lambda: self._sort_treeview(col, not reverse))
    
    def _validate_inputs(self) -> bool:
        """입력값 검증"""
        source = self.source_entry.get()
        if not source:
            messagebox.showerror("오류", "소스 폴더를 선택해주세요.")
            return False
        
        path = Path(source)
        if not path.exists():
            messagebox.showerror("오류", f"소스 폴더가 존재하지 않습니다:\n{source}")
            return False
        
        if not path.is_dir():
            messagebox.showerror("오류", f"지정된 경로가 폴더가 아닙니다:\n{source}")
            return False
        
        return True

    def _update_button_states(self):
        """단계별 버튼 활성화/비활성화 상태 업데이트"""
        # 버튼이 생성되지 않았거나 앱 종료 시점이면 패스
        if not hasattr(self, 'btn_normalize'): 
            return

        # 1단계 완료 -> 2단계 활성화
        if self.step_folder_done:
            self.btn_normalize.configure(state="normal")
        else:
            self.btn_normalize.configure(state="disabled")
            
        # 2단계 완료 -> 정규화 즉시 적용 활성화, 3단계 활성화
        if self.step_normalize_done:
            self.btn_apply_source.configure(state="normal")
            self.btn_genre.configure(state="normal")
            
            # 장르 추론 완료 여부에 따른 버튼 상태 변경 (One Button Two Actions)
            # 장르 추론 완료 여부에 따른 버튼 상태 변경 (One Button Two Actions)
            if self.step_genre_done:
                self.btn_genre.configure(
                    text="▶️ 실행 (Rename)", 
                    fg_color="#27AE60", # Green
                    hover_color="#2ECC71",
                    text_color="#FFFFFF",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold")
                )
            else:
                self.btn_genre.configure(
                    text="3. 장르 추론",
                    fg_color=THEME["accent_blue"],
                    hover_color=THEME["accent_blue_hover"],
                    text_color="#FFFFFF"
                )
        else:
            self.btn_genre.configure(state="disabled")
            if hasattr(self, 'btn_apply_source'):
                self.btn_apply_source.configure(state="disabled")

    # ========================================================================
    # 새 버튼 핸들러 (WNAP v1.3.0)
    # ========================================================================

    def _on_btn_folder_click(self):
        """1. 폴더 정리 버튼 클릭"""
        if not self._validate_inputs(): return
        self._run_async_task(self._execute_stage1, "Stage 1: 폴더 스캔")

    def _on_btn_normalize_click(self):
        """2. 파일명 정규화 버튼 클릭"""
        if not self.step_folder_done: 
            messagebox.showwarning("순서 오류", "먼저 [1. 폴더 정리]를 실행해주세요.")
            return
        self._run_async_task(self._execute_stage1_5, "Stage 1.5: 제목 정규화")

    def _on_btn_apply_source_click(self):
        """정규화 결과 내보내기 버튼 클릭"""
        if not getattr(self, "step_normalize_done", False):
            return
            
        if not messagebox.askyesno("저장 확인", f"현재 미리보기 중인 {len(self.tasks_cache)}개의 정규화된 이름을 원본 소스 폴더의 실제 파일에 그대로 적용하시겠습니까?"):
            return
            
        self._run_async_task(self._execute_apply_source, "파일 이름 변경 (In-place)")

    def _on_btn_genre_click(self):
        """3. 장르 추론/실행 버튼 클릭"""
        if not self.step_normalize_done:
            messagebox.showwarning("순서 오류", "먼저 [2. 파일명 정규화]를 실행해주세요.")
            return

        # [상태 분기]
        # State 1: 아직 추론 안함 -> [추론] 실행
        if not self.step_genre_done:
            self._run_async_task(self._execute_stage2, "Stage 2: 장르 추론 (검색)")
            return

        # State 2: 추론 완료 -> [실행] (Rename)
        if not messagebox.askyesno("실행 확인", f"총 {len(self.tasks_cache)}개의 파일 이름을 실제로 변경하시겠습니까?"):
            return
            
        self._run_async_task(self._execute_stage3, "Stage 3: 파일명 변경 및 이동")

    def _on_btn_batch_click(self):
        """일괄 처리 버튼 클릭"""
        if not self._validate_inputs(): return
        
        if not messagebox.askyesno("일괄 처리", "폴더 스캔부터 실행까지 모든 단계를 자동으로 진행하시겠습니까?"):
            return
            
        self._run_async_task(self._execute_batch, "일괄 처리 (All Stages)")


    def _on_btn_reset_click(self):
        """초기화 버튼 클릭"""
        # 데이터 초기화
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        self.last_result = None
        self.last_mapping_csv = None
        self.last_target_folder = None
        self.tasks_cache = []
        
        # 상태 리셋
        self.step_folder_done = False
        self.step_normalize_done = False
        self._update_button_states()
        
        self._reset_summary()
        self.progress_bar.set(0)
        self.progress_label.configure(text="")
        self.status_label.configure(text="⏸ 대기 중", text_color=THEME["text_muted"])
        self.open_folder_btn.configure(state="disabled")
        self._log_to_file("UI 및 상태 초기화 완료")


    def _run_async_task(self, target_func, description: str):
        """비동기 작업 실행 공통 래퍼"""
        if self.is_running: return
        
        # 설정 업데이트
        self._update_config_from_ui()
        
        self.is_running = True
        self._set_ui_state(False)
        self.progress_bar.set(0)
        self.progress_label.configure(text=f"{description} 준비 중...")
        self.status_label.configure(text=f"⏳ {description} 중...", text_color=THEME["status_warning"])
        
        thread = threading.Thread(target=target_func, daemon=True)
        thread.start()

    # ========================================================================
    # 실제 실행 로직 (백그라운드)
    # ========================================================================

    def _execute_stage1(self):
        """Stage 1 실행 로직"""
        try:
            source_folder = Path(self.config.source_folder)
            orchestrator = PipelineOrchestrator(self.config, progress_callback=self._on_progress)
            
            # Run Stage 1 (Scan)
            tasks = orchestrator.run_stage1(source_folder)
            
            # 결과 저장
            result = PipelineResult(total_files=len(tasks), tasks=tasks)
            self.last_result = result
            self.tasks_cache = tasks
            
            self.step_folder_done = True
            
            # UI 업데이트
            self.after(0, lambda: self._show_stage_result(result, "Stage 1 완료"))
            
        except Exception as e:
            self._handle_error(e)
        finally:
            self._finish_task()

    def _execute_stage1_5(self):
        """Stage 1.5 실행 로직"""
        try:
            # 이전 단계 결과 사용
            current_tasks = self.tasks_cache
            orchestrator = PipelineOrchestrator(
                self.config, 
                progress_callback=self._on_progress
            )
            
            # Run Stage 1.5 (Parse Only)
            tasks = orchestrator.run_stage1_5(current_tasks)
            
            # 결과 갱신
            self.tasks_cache = tasks
            self.step_normalize_done = True
            
            # 임시 결과 객체
            result = PipelineResult(total_files=len(tasks), tasks=tasks)
            self.last_result = result

            self.after(0, lambda: self._show_stage_result(result, "Stage 1.5 완료"))
            
        except Exception as e:
            self._handle_error(e)
        finally:
            self._finish_task()

    def _execute_apply_source(self):
        """소스 폴더 즉시 적용 실행 로직"""
        try:
            current_tasks = self.tasks_cache
            orchestrator = PipelineOrchestrator(
                self.config, 
                progress_callback=self._on_progress
            )
            
            # Run apply_normalization_to_source
            tasks = orchestrator.apply_normalization_to_source(current_tasks)
            
            # 결과 갱신
            self.tasks_cache = tasks
            
            result = PipelineResult(total_files=len(tasks), tasks=tasks)
            self.last_result = result
            
            self.after(0, lambda: self._show_stage_result(result, "소스 변경 완료"))
            self.after(0, lambda: messagebox.showinfo("완료", "정규화된 파일명이 소스 폴더에 즉시 변경(저장)되었습니다."))
            
        except Exception as e:
            self._handle_error(e)
        finally:
            self._finish_task()

    def _execute_stage2(self):
        """Stage 2 실행 로직 (장르 추론 - Search Only)"""
        try:
            current_tasks = self.tasks_cache
            orchestrator = PipelineOrchestrator(
                self.config, 
                progress_callback=self._on_progress,
                genre_confirm_callback=self._on_genre_confirm # Smart Filter 사용 시 동작
            )
            
            # Run Stage 2 (Search)
            tasks = orchestrator.run_stage2(current_tasks)
            
            # 결과 갱신
            self.tasks_cache = tasks
            self.step_genre_done = True
            
            # 임시 결과 객체
            result = PipelineResult(total_files=len(tasks), tasks=tasks)
            self.last_result = result
            
            self.after(0, lambda: self._show_stage_result(result, "Stage 2 완료"))
            
            # 버튼 텍스트 변경 (Main Thread에서 실행해야 함, after 사용)
            self.after(0, lambda: self.btn_genre.configure(
                text="▶️ 실행 (Rename)", 
                fg_color=THEME["status_success"],
                hover_color=THEME["status_success"]
            ))
            
        except Exception as e:
            self._handle_error(e)
        finally:
            self._finish_task()

    def _execute_stage3(self):
        """Stage 3 실행 로직 (실행 및 이동 - Execute Only)"""
        try:
            current_tasks = self.tasks_cache
            source_folder = Path(self.config.source_folder)
            orchestrator = PipelineOrchestrator(
                self.config, 
                progress_callback=self._on_progress
            )
            
            # Run Stage 3 (Execute)
            result = orchestrator.run_stage3(current_tasks, source_folder)
            
            self.last_result = result
            self.last_mapping_csv = result.mapping_csv_path
            
            target_folder = self.target_entry.get() or str(source_folder / "정리완료")
            self.last_target_folder = Path(target_folder)

            self.after(0, lambda: self._show_final_result(result))
            
        except Exception as e:
            self._handle_error(e)
        finally:
            self._finish_task()

    def _execute_batch(self):
        """일괄 처리 로직 (Stage 1 -> 1.5 -> 2 -> Popup -> 3)"""
        try:
            source_folder = Path(self.config.source_folder)
            
            # Orchestrator 인스턴스 생성 (로컬)
            orchestrator = PipelineOrchestrator(
                self.config, 
                progress_callback=self._on_progress
            )
            
            # --- Stage 1: Folder Organizer ---
            self._log_to_file("=== [일괄 처리] Stage 1 시작 ===")
            tasks = orchestrator.run_stage1(source_folder)
            if not tasks:
                self.after(0, lambda: messagebox.showinfo("완료", "처리할 파일이 없습니다."))
                return

            self.tasks_cache = tasks # Update Cache
            self._populate_result_table(tasks) # Initial Table
            
            # --- Stage 1.5: Normalize ---
            self._log_to_file("=== [일괄 처리] Stage 1.5 시작 ===")
            tasks = orchestrator.run_stage1_5(tasks)
            self.tasks_cache = tasks
            self._populate_result_table(tasks) # Update Table
            
            # --- Stage 1.5 (Apply to Source): 정규화 결과 즉시 소스에 저장 적용 ---
            self._log_to_file("=== [일괄 처리] 정규화 결과 소스 폴더에 즉시 저장 ===")
            tasks = orchestrator.apply_normalization_to_source(tasks)
            self.tasks_cache = tasks
            self._populate_result_table(tasks)
            
            # --- Stage 2: Genre Search ---
            self._log_to_file("=== [일괄 처리] Stage 2 시작 ===")
            tasks = orchestrator.run_stage2(tasks)
            self.tasks_cache = tasks
            
            # --- Safety Popup (Main Thread) ---
            # Using queue or direct invoke if thread-safe enough (CTK/Tkinter usually requires main thread)
            # But since we are in a thread, we must block here.
            # We can use a trick: `self.after` with a threading.Event?
            # Or simplified: use messagebox directly. On Windows it usually works from threads but risking freeze.
            # Safer: split function? No, complex.
            # Let's try direct messagebox, heavily used in python-tkinter apps, often works if simple.
            # If not, we'd need a queue-based confirmation. 
            # Given constraints, and "tkinter not thread safe", strict way is to pause thread via Event.
            
            confirm_event = threading.Event()
            confirm_result = {}
            
            def show_confirm():
                confirm_result['ok'] = messagebox.askyesno(
                    "최종 실행 확인", 
                    f"총 {len(tasks)}개의 파일 변경을 진행하시겠습니까?\n(취소 시 여기서 중단됩니다)"
                )
                confirm_event.set()
                
            self.after(0, show_confirm)
            confirm_event.wait()
            
            if not confirm_result.get('ok'):
                self._log_to_file("사용자가 일괄 처리를 중단하였습니다.")
                return

            # --- Stage 3: Execution ---
            self._log_to_file("=== [일괄 처리] Stage 3 시작 ===")
            result = orchestrator.run_stage3(tasks, source_folder)
            
            # Finalize
            self.last_result = result
            self.tasks_cache = result.tasks
            
            target_folder = self.target_entry.get() or str(source_folder / "정리완료")
            self.last_target_folder = Path(target_folder)
            
            self.step_folder_done = True
            self.step_normalize_done = True
            
            self.after(0, lambda: self._show_final_result(result))
            
        except Exception as e:
            self._handle_error(e)
        finally:
            self._finish_task()

    def _handle_error(self, e):
        """에러 처리"""
        self._log_to_file(f"오류 발생: {e}")
        self.after(0, lambda: messagebox.showerror("오류", f"작업 중 오류 발생:\n{e}"))

    def _finish_task(self):
        """작업 종료 공통 처리"""
        self.is_running = False
        self.after(0, lambda: self._set_ui_state(True))
        self.after(0, lambda: self.progress_bar.set(1))
        self.after(0, self._update_button_states)

    def _show_stage_result(self, result: PipelineResult, msg: str):
        """중간 단계 결과 표시"""
        self._populate_result_table(result.tasks)
        self.status_label.configure(text=f"✅ {msg}", text_color=THEME["status_success"])
        self.progress_label.configure(text=f"{msg} ({result.total_files}개 파일)")
        self._update_summary(result)

    def _show_final_result(self, result: PipelineResult):
        """최종 실행 결과 표시"""
        self._show_stage_result(result, "최종 실행 완료")
        self.open_folder_btn.configure(state="normal")
        
        # 자동 폴더 열기 (편의성)
        self._open_target_folder()

    def _set_ui_state(self, enabled: bool):
        """UI 활성화/비활성화"""
        state = "normal" if enabled else "disabled"
        for widget in self.disable_on_run:
            widget.configure(state=state)
        # 상태에 따른 버튼 재조정은 _finish_task에서 _update_button_states 호출로 처리

    def get_config(self) -> PipelineConfig:
        self._update_config_from_ui()
        return self.config

    def _on_treeview_double_click(self, event):
        """Treeview 더블클릭 -> 정규화 이름 편집"""
        region = self.result_tree.identify("region", event.x, event.y)
        if region != "cell": return
        
        item = self.result_tree.focus()
        if not item: return
        
        col = self.result_tree.identify_column(event.x)
        
        # 'normalized' 컬럼 (#2) 인 경우에만 편집 허용
        if col == "#2":
            # 현재 값 가져오기
            values = self.result_tree.item(item, "values")
            current_val = values[1] # normalized
            
            # 커스텀 입력 대화상자 사용 (초기값 지원)
            dialog = EditNameDialog(self, title="파일명 편집", initial_value=current_val)
            new_val = dialog.get_input()
            
            if new_val and new_val != current_val:
                # 1. 내부 데이터(tasks_cache) 업데이트
                try:
                    task_idx = int(item) # iid를 인덱스로 사용
                    if 0 <= task_idx < len(self.tasks_cache):
                        task = self.tasks_cache[task_idx]
                        task.metadata['normalized_name'] = new_val
                        task.metadata['user_edited'] = True  # 수동 편집 플래그
                        # 로그 기록
                        self._log_to_file(f"파일명 수동 변경: {current_val} -> {new_val}")
                        
                        # 2. Treeview 업데이트
                        new_values = list(values)
                        new_values[1] = new_val
                        self.result_tree.item(item, values=new_values)
                except (ValueError, IndexError):
                    self._log_to_file("태스크 매핑 실패 (정렬됨?)")
                    messagebox.showwarning("오류", "데이터를 업데이트할 수 없습니다. (목록이 정렬되었을 수 있음)")

        # [NEW] 'genre' 컬럼 (#3) 편집 허용
        elif col == "#3":
            values = self.result_tree.item(item, "values")
            current_genre = values[2] # genre
            current_normalized = values[1] # normalized name
            
            dialog = EditNameDialog(self, title="장르 편집", initial_value=current_genre)
            new_genre = dialog.get_input()
            
            if new_genre is not None and new_genre != current_genre:
                try:
                    task_idx = int(item)
                    if 0 <= task_idx < len(self.tasks_cache):
                        task = self.tasks_cache[task_idx]
                        old_genre_tag = f"[{current_genre}]" if current_genre else ""
                        new_genre_tag = f"[{new_genre}]" if new_genre else ""
                        
                        # 1. 태스크 장르 업데이트
                        task.genre = new_genre
                        task.metadata['genre'] = new_genre
                        
                        # 2. 정규화된 파일명 업데이트 (장르 태그 교체)
                        new_normalized = current_normalized
                        if old_genre_tag and old_genre_tag in current_normalized:
                             new_normalized = current_normalized.replace(old_genre_tag, new_genre_tag, 1)
                        elif new_genre_tag:
                             # 기존 장르가 없었다면 맨 앞에 추가
                             new_normalized = f"{new_genre_tag} {current_normalized}"
                        
                        # 공백 정리 (혹시 모를 이중 공백)
                        new_normalized = new_normalized.strip()
                        task.metadata['normalized_name'] = new_normalized
                        task.metadata['user_edited'] = True  # 수동 편집 플래그
                        
                        self._log_to_file(f"장르 수동 변경: {current_genre} -> {new_genre}")
                        
                        # 3. Treeview 업데이트
                        new_values = list(values)
                        new_values[1] = new_normalized
                        new_values[2] = new_genre
                        self.result_tree.item(item, values=new_values)
                        
                except (ValueError, IndexError):
                     pass

        # 원본 파일명(#1) 클릭 시 폴더 열기 (기존 기능 유지)
        elif col == "#1":
            try:
                task_idx = int(item)
                if 0 <= task_idx < len(self.tasks_cache):
                    task = self.tasks_cache[task_idx]
                    if task.original_path and task.original_path.exists():
                        self._open_folder_and_select_file(task.original_path.parent, task.original_path)
            except (ValueError, IndexError):
                 pass

def main():
    """GUI 애플리케이션 실행"""
    app = WNAPMainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()
