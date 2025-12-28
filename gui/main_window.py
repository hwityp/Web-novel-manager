#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNAP GUI Main Window - Professional Edition v2

Web Novel Archive Pipeline의 메인 GUI 윈도우입니다.
customtkinter를 사용하여 프로페셔널한 UI를 제공합니다.

v2 변경사항:
- 로그 텍스트박스 제거, 파일 로깅으로 전환
- 고대비 테마 적용 (배경 #2b2b2b, 텍스트 #FFFFFF)
- Treeview 확장 레이아웃
- 더블클릭 폴더 열기
- 동적 프로그레스 바 색상
- 도움말 툴팁 시스템
- 윈도우 상태 저장/복원

Validates: Requirements 1, 2, 3, 4, 5, 6, 7
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

# 폰트 크기
FONT_SIZE_SMALL = 12
FONT_SIZE_BASE = 14
FONT_SIZE_MEDIUM = 16
FONT_SIZE_LARGE = 18
FONT_SIZE_XLARGE = 20
FONT_SIZE_DASHBOARD = 24

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
    "text_muted": "#A0A0A0",
    
    # 강조 색상
    "accent_blue": "#4A90D9",
    "accent_blue_hover": "#5BA0E9",
    "accent_green": "#4CAF50",
    "accent_green_hover": "#5CBF60",
    "accent_gray": "#606060",
    "accent_gray_hover": "#707070",
    
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
}


class WNAPMainWindow(ctk.CTk):
    """WNAP 메인 윈도우 - 프로페셔널 에디션 v2"""
    
    def __init__(self):
        super().__init__()
        
        # 윈도우 설정
        self.title(f"WNAP - Web Novel Archive Pipeline v{__version__}")
        self.configure(fg_color=THEME["bg_main"])
        self.minsize(1100, 700)
        
        # 윈도우 상태 복원
        WindowStateManager.restore_state(self)
        
        # 설정 로드
        self.config = self._load_config()
        
        # 파일 로거 초기화 (GUI 모드: 콘솔 출력 비활성화)
        self.file_logger = PipelineLogger(
            log_level=self.config.log_level,
            log_dir=Path("logs"),
            log_filename="wnap.log",
            console_output=False
        )
        
        # 상태 변수
        self.is_running = False
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
        """UI 위젯 생성 - 로그 섹션 제거, Treeview 확장"""
        # 메인 컨테이너 설정 (로그 섹션 제거)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # 상단 카드 (고정)
        self.grid_rowconfigure(1, weight=0)  # 옵션 섹션 (고정)
        self.grid_rowconfigure(2, weight=5)  # 결과 테이블 + 프로그레스 (최대 확장)
        self.grid_rowconfigure(3, weight=0)  # 버튼 영역 (고정)
        
        # === 상단: 폴더 설정 + 대시보드 ===
        self._create_top_section()
        
        # === 옵션 섹션 ===
        self._create_options_section()
        
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
        
        self.source_btn = ctk.CTkButton(
            folder_card, 
            text="찾아보기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            width=BUTTON_WIDTH_SMALL,
            height=38,
            corner_radius=8,
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
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
            text_color=THEME["text_primary"]
        )
        self.target_entry.grid(row=2, column=1, padx=PADDING_SMALL, pady=(0, PADDING_LARGE), sticky="ew")
        
        self.target_btn = ctk.CTkButton(
            folder_card,
            text="찾아보기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            width=BUTTON_WIDTH_SMALL,
            height=38,
            corner_radius=8,
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
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

    def _create_options_section(self):
        """옵션 섹션 생성 - 툴팁 포함"""
        options_card = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["accent_blue"]
        )
        options_card.grid(row=1, column=0, padx=PADDING_LARGE, pady=PADDING_BASE, sticky="ew")
        options_card.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # 제목
        title_label = ctk.CTkLabel(
            options_card,
            text="⚙️ 실행 옵션",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LARGE, weight="bold"),
            text_color=THEME["text_primary"]
        )
        title_label.grid(row=0, column=0, columnspan=4, padx=PADDING_LARGE, pady=(PADDING_LARGE, PADDING_BASE), sticky="w")
        
        # Dry-run 토글 + 툴팁
        dryrun_frame = ctk.CTkFrame(options_card, fg_color="transparent")
        dryrun_frame.grid(row=1, column=0, padx=PADDING_LARGE, pady=PADDING_BASE, sticky="w")
        
        self.dry_run_var = ctk.BooleanVar(value=True)
        dry_run_switch = ctk.CTkSwitch(
            dryrun_frame,
            text="Dry-run 모드",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            text_color=THEME["text_secondary"],
            variable=self.dry_run_var,
            onvalue=True,
            offvalue=False,
            progress_color=THEME["accent_blue"]
        )
        dry_run_switch.pack(side="left")
        
        dryrun_help = ctk.CTkLabel(dryrun_frame, text=" (?)", text_color=THEME["accent_blue"],
                                   font=ctk.CTkFont(size=FONT_SIZE_SMALL))
        dryrun_help.pack(side="left")
        self.tooltips.append(create_tooltip(dryrun_help, TOOLTIP_TEXTS["dry_run"]))
        
        # 로그 레벨 + 툴팁
        log_frame = ctk.CTkFrame(options_card, fg_color="transparent")
        log_frame.grid(row=1, column=1, padx=PADDING_BASE, pady=PADDING_BASE, sticky="w")
        
        log_level_label = ctk.CTkLabel(
            log_frame, 
            text="로그 레벨:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            text_color=THEME["text_secondary"]
        )
        log_level_label.pack(side="left", padx=(0, PADDING_SMALL))
        
        self.log_level_var = ctk.StringVar(value="INFO")
        log_level_combo = ctk.CTkComboBox(
            log_frame,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            variable=self.log_level_var,
            width=100,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            corner_radius=8,
            fg_color=THEME["bg_input"],
            text_color=THEME["text_primary"]
        )
        log_level_combo.pack(side="left")
        
        log_help = ctk.CTkLabel(log_frame, text=" (?)", text_color=THEME["accent_blue"],
                                font=ctk.CTkFont(size=FONT_SIZE_SMALL))
        log_help.pack(side="left")
        self.tooltips.append(create_tooltip(log_help, TOOLTIP_TEXTS["log_level"]))
        
        # 실행 확인 체크박스 + 툴팁
        confirm_frame = ctk.CTkFrame(options_card, fg_color="transparent")
        confirm_frame.grid(row=1, column=2, padx=PADDING_BASE, pady=PADDING_BASE, sticky="w")
        
        self.confirm_var = ctk.BooleanVar(value=True)
        confirm_check = ctk.CTkCheckBox(
            confirm_frame,
            text="실행 전 확인",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            text_color=THEME["text_secondary"],
            variable=self.confirm_var,
            checkbox_width=22,
            checkbox_height=22,
            corner_radius=6,
            fg_color=THEME["accent_blue"]
        )
        confirm_check.pack(side="left")
        
        confirm_help = ctk.CTkLabel(confirm_frame, text=" (?)", text_color=THEME["accent_blue"],
                                    font=ctk.CTkFont(size=FONT_SIZE_SMALL))
        confirm_help.pack(side="left")
        self.tooltips.append(create_tooltip(confirm_help, TOOLTIP_TEXTS["confirm_dialog"]))
        
        # 설정 저장 버튼 + 툴팁
        save_frame = ctk.CTkFrame(options_card, fg_color="transparent")
        save_frame.grid(row=1, column=3, padx=(PADDING_BASE, PADDING_LARGE), pady=(PADDING_BASE, PADDING_LARGE), sticky="e")
        
        self.save_btn = ctk.CTkButton(
            save_frame,
            text="💾 설정 저장",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BASE),
            width=BUTTON_WIDTH_SMALL,
            height=36,
            corner_radius=8,
            fg_color=THEME["accent_gray"],
            hover_color=THEME["accent_gray_hover"],
            command=self._save_config
        )
        self.save_btn.pack(side="left")
        self.disable_on_run.append(self.save_btn)
        
        save_help = ctk.CTkLabel(save_frame, text=" (?)", text_color=THEME["accent_blue"],
                                 font=ctk.CTkFont(size=FONT_SIZE_SMALL))
        save_help.pack(side="left")
        self.tooltips.append(create_tooltip(save_help, TOOLTIP_TEXTS["save_settings"]))


    def _create_result_table_section(self):
        """결과 테이블 섹션 생성 - 확장 레이아웃, 프로그레스 바 포함"""
        table_card = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["accent_blue"]
        )
        table_card.grid(row=2, column=0, padx=PADDING_LARGE, pady=PADDING_BASE, sticky="nsew")
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
        self.open_csv_btn = ctk.CTkButton(
            header_frame,
            text="📄 CSV 열기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL),
            width=100,
            height=32,
            corner_radius=8,
            fg_color=THEME["accent_gray"],
            hover_color=THEME["accent_gray_hover"],
            state="disabled",
            command=self._open_mapping_csv
        )
        self.open_csv_btn.pack(side="right", padx=(PADDING_SMALL, 0))
        
        self.open_folder_btn = ctk.CTkButton(
            header_frame,
            text="📂 폴더 열기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL),
            width=100,
            height=32,
            corner_radius=8,
            fg_color=THEME["accent_gray"],
            hover_color=THEME["accent_gray_hover"],
            state="disabled",
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
        
        self.result_tree.column("original", width=280, minwidth=180)
        self.result_tree.column("normalized", width=350, minwidth=200)
        self.result_tree.column("genre", width=100, minwidth=80)
        self.result_tree.column("confidence", width=90, minwidth=70)
        self.result_tree.column("source", width=100, minwidth=80)
        
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
            rowheight=32,
            font=(FONT_FAMILY, FONT_SIZE_BASE),
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
    
    def _create_action_buttons(self):
        """실행 버튼 섹션 생성"""
        button_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["accent_blue"]
        )
        button_frame.grid(row=3, column=0, padx=PADDING_LARGE, pady=(PADDING_BASE, PADDING_LARGE), sticky="ew")
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # 미리보기 버튼 (청색)
        self.preview_btn = ctk.CTkButton(
            button_frame,
            text="🔍 미리보기 (Dry-run)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BUTTON_HEIGHT,
            corner_radius=BUTTON_CORNER_RADIUS,
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
            command=self._run_preview
        )
        self.preview_btn.grid(row=0, column=0, padx=PADDING_LARGE, pady=PADDING_LARGE, sticky="ew")
        
        # 실행 버튼 (녹색)
        self.run_btn = ctk.CTkButton(
            button_frame,
            text="▶️ 실행",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BUTTON_HEIGHT,
            corner_radius=BUTTON_CORNER_RADIUS,
            fg_color=THEME["accent_green"],
            hover_color=THEME["accent_green_hover"],
            command=self._run_pipeline
        )
        self.run_btn.grid(row=0, column=1, padx=PADDING_BASE, pady=PADDING_LARGE, sticky="ew")
        
        # 초기화 버튼 (회색)
        clear_btn = ctk.CTkButton(
            button_frame,
            text="🗑️ 초기화",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_MEDIUM, weight="bold"),
            height=BUTTON_HEIGHT,
            corner_radius=BUTTON_CORNER_RADIUS,
            fg_color=THEME["accent_gray"],
            hover_color=THEME["accent_gray_hover"],
            command=self._clear_all
        )
        clear_btn.grid(row=0, column=2, padx=(PADDING_BASE, PADDING_LARGE), pady=PADDING_LARGE, sticky="ew")


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
    
    def _browse_target_folder(self):
        """타겟 폴더 선택 다이얼로그"""
        folder = filedialog.askdirectory(title="타겟 폴더 선택")
        if folder:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, folder)
            self._log_to_file(f"타겟 폴더 선택: {folder}")
    
    def _load_config_to_ui(self):
        """설정을 UI에 반영"""
        if self.config.source_folder:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, self.config.source_folder)
        
        if self.config.target_folder:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, self.config.target_folder)
        
        self.dry_run_var.set(self.config.dry_run)
        self.log_level_var.set(self.config.log_level)
    
    def _update_config_from_ui(self):
        """UI 값을 설정에 반영"""
        self.config.source_folder = self.source_entry.get()
        self.config.target_folder = self.target_entry.get() or "정리완료"
        self.config.dry_run = self.dry_run_var.get()
        self.config.log_level = self.log_level_var.get()
    
    def _process_progress_queue(self):
        """진행 상황 큐 처리 (메인 스레드에서 실행)"""
        try:
            while True:
                current, total, filename = self.progress_queue.get_nowait()
                progress = current / total if total > 0 else 0
                self.progress_bar.set(progress)
                self.progress_label.configure(text=f"[{current}/{total}] {filename}")
                self.status_label.configure(
                    text=f"⏳ 처리 중 ({current}/{total})",
                    text_color=THEME["status_warning"]
                )
        except queue.Empty:
            pass
        
        self.after(50, self._process_progress_queue)
    
    def _on_progress(self, current: int, total: int, filename: str):
        """진행 상황 콜백 (백그라운드 스레드에서 호출됨)"""
        self.progress_queue.put((current, total, filename))
    
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
        self.genre_confirm_queue.put((filename, suggested_genre, confidence))
        try:
            selected_genre = self.genre_confirm_response.get(timeout=300)
            return selected_genre
        except queue.Empty:
            return None

    def _on_treeview_double_click(self, event):
        """Treeview 행 더블클릭 시 폴더 열기"""
        selection = self.result_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.result_tree.item(item, "values")
        
        if not values:
            return
        
        # 원본 파일명으로 태스크 찾기
        original_name = values[0].rstrip("...")  # 잘린 이름 처리
        file_path = self._find_file_path_by_name(original_name)
        
        if not file_path:
            messagebox.showwarning("경고", "파일 경로를 찾을 수 없습니다.")
            return
        
        folder_path = file_path.parent
        if not folder_path.exists():
            messagebox.showwarning("경고", f"폴더가 존재하지 않습니다:\n{folder_path}")
            return
        
        self._open_folder_and_select_file(folder_path, file_path)
    
    def _find_file_path_by_name(self, name: str) -> Optional[Path]:
        """파일명으로 태스크에서 경로 찾기"""
        for task in self.tasks_cache:
            if task.raw_name and task.raw_name.startswith(name):
                return task.original_path
            if task.original_path and str(task.original_path.name).startswith(name):
                return task.original_path
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
        self.open_csv_btn.configure(state="disabled")
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
            
            self.result_tree.insert("", "end", values=(
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

    def _open_mapping_csv(self):
        """매핑 CSV 파일 열기"""
        if self.last_mapping_csv and self.last_mapping_csv.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(self.last_mapping_csv))
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(self.last_mapping_csv)])
                else:
                    subprocess.run(["xdg-open", str(self.last_mapping_csv)])
                self._log_to_file(f"CSV 파일 열기: {self.last_mapping_csv}")
            except Exception as e:
                messagebox.showerror("오류", f"파일을 열 수 없습니다:\n{e}")
        else:
            messagebox.showwarning("경고", "매핑 CSV 파일이 없습니다.")
    
    def _open_target_folder(self):
        """타겟 폴더 열기"""
        folder = self.last_target_folder
        if not folder:
            source = self.source_entry.get()
            target = self.target_entry.get()
            if target:
                folder = Path(target)
            elif source:
                folder = Path(source) / "정리완료"
        
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
            messagebox.showwarning("경고", "타겟 폴더가 존재하지 않습니다.")
    
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
        
        if not Path(source).exists():
            messagebox.showerror("오류", f"소스 폴더가 존재하지 않습니다:\n{source}")
            return False
        
        if not Path(source).is_dir():
            messagebox.showerror("오류", f"지정된 경로가 폴더가 아닙니다:\n{source}")
            return False
        
        return True
    
    def _run_preview(self):
        """미리보기 실행 (Dry-run)"""
        self.dry_run_var.set(True)
        self._run_pipeline()
    
    def _run_pipeline(self):
        """파이프라인 실행"""
        if self.is_running:
            messagebox.showwarning("경고", "이미 실행 중입니다.")
            return
        
        if not self._validate_inputs():
            return
        
        dry_run = self.dry_run_var.get()
        
        # 확인 대화상자
        if self.confirm_var.get():
            mode = "미리보기" if dry_run else "실제 실행"
            if not messagebox.askyesno(
                "실행 확인",
                f"{mode} 모드로 파이프라인을 실행하시겠습니까?\n\n"
                f"소스: {self.source_entry.get()}\n"
                f"타겟: {self.target_entry.get() or '소스폴더/정리완료'}"
            ):
                return
        
        # 설정 업데이트
        self._update_config_from_ui()
        
        # 결과 테이블 초기화
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self._reset_summary()
        
        # 프로그레스 바 색상 변경
        self._update_progress_bar_color(dry_run)
        
        # 백그라운드 스레드에서 실행
        self.is_running = True
        self._set_ui_state(False)
        self.progress_bar.set(0)
        self.progress_label.configure(text="준비 중...")
        self.status_label.configure(text="⏳ 실행 중...", text_color=THEME["status_warning"])
        
        thread = threading.Thread(
            target=self._execute_pipeline,
            args=(dry_run,),
            daemon=True
        )
        thread.start()
    
    def _execute_pipeline(self, dry_run: bool):
        """파이프라인 실행 (백그라운드 스레드)"""
        try:
            source_folder = Path(self.source_entry.get())
            target_folder = self.target_entry.get() or str(source_folder / "정리완료")
            
            mode_str = "미리보기" if dry_run else "실행"
            self._log_to_file(f"{'='*60}")
            self._log_to_file(f"파이프라인 {mode_str} 시작")
            self._log_to_file(f"소스: {source_folder}")
            self._log_to_file(f"타겟: {target_folder}")
            self._log_to_file(f"{'='*60}")
            
            # 오케스트레이터 생성
            orchestrator = PipelineOrchestrator(
                self.config,
                progress_callback=self._on_progress,
                genre_confirm_callback=self._on_genre_confirm
            )
            
            # 실행
            result = orchestrator.run(source_folder, dry_run=dry_run)
            
            # 결과 저장
            self.last_result = result
            self.last_mapping_csv = result.mapping_csv_path
            self.last_target_folder = Path(target_folder)
            
            # 결과 표시 (메인 스레드에서)
            self.after(0, lambda: self._show_result(result, dry_run))
            
        except Exception as e:
            self._log_to_file(f"오류 발생: {e}")
            self.after(0, lambda: messagebox.showerror("오류", f"파이프라인 실행 중 오류:\n{e}"))
        
        finally:
            self.is_running = False
            self.after(0, lambda: self._set_ui_state(True))
            self.after(0, lambda: self.progress_bar.set(1))
            self.after(0, lambda: self.progress_label.configure(text="완료"))

    def _show_result(self, result: PipelineResult, dry_run: bool):
        """실행 결과 표시"""
        mode = "미리보기" if dry_run else "실행"
        
        # 요약 업데이트
        self._update_summary(result)
        
        # 결과 테이블 채우기
        self._populate_result_table(result.tasks)
        
        # 파일 열기 버튼 활성화
        if result.mapping_csv_path:
            self.open_csv_btn.configure(state="normal")
        if not dry_run:
            self.open_folder_btn.configure(state="normal")
        
        # 상태 업데이트
        if result.failed > 0:
            self.status_label.configure(text="⚠️ 완료 (일부 실패)", text_color=THEME["status_warning"])
        else:
            self.status_label.configure(text="✅ 완료", text_color=THEME["status_success"])
        
        # 파일 로그 출력
        self._log_to_file(f"{'='*60}")
        self._log_to_file(f"파이프라인 {mode} 완료")
        self._log_to_file(f"총 파일 수: {result.total_files}")
        self._log_to_file(f"성공: {result.processed}")
        self._log_to_file(f"실패: {result.failed}")
        self._log_to_file(f"건너뜀: {result.skipped}")
        
        if result.mapping_csv_path:
            self._log_to_file(f"매핑 파일: {result.mapping_csv_path}")
        
        if result.errors:
            self._log_to_file(f"오류 목록 ({len(result.errors)}건):")
            for error in result.errors[:10]:
                self._log_to_file(f"  - {error}")
            if len(result.errors) > 10:
                self._log_to_file(f"  ... 외 {len(result.errors) - 10}건")
        
        self._log_to_file(f"{'='*60}")
    
    def _set_ui_state(self, enabled: bool):
        """UI 활성화/비활성화 - 실행 중 오작동 방지"""
        state = "normal" if enabled else "disabled"
        
        # 실행 버튼
        self.preview_btn.configure(state=state)
        self.run_btn.configure(state=state)
        
        # 실행 중 비활성화할 위젯들
        for widget in self.disable_on_run:
            widget.configure(state=state)
    
    def get_config(self) -> PipelineConfig:
        """현재 UI 설정을 PipelineConfig로 반환"""
        self._update_config_from_ui()
        return self.config


def main():
    """GUI 애플리케이션 실행"""
    app = WNAPMainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
