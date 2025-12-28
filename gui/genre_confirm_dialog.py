#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Genre Confirmation Dialog - Professional Edition v4

confidence가 "medium"인 태스크에 대해 사용자에게 장르 확인을 요청하는 다이얼로그입니다.
v4: 버튼 표시 오류 수정, 창 크기 최적화, 폰트 확대

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""
import customtkinter as ctk
from typing import Optional, List


# ============================================================================
# 스타일 상수
# ============================================================================
FONT_FAMILY = "Segoe UI"

# 폰트 크기 (확대)
FONT_SIZE_TITLE = 26        # 제목
FONT_SIZE_SUBTITLE = 16     # 부제목
FONT_SIZE_LABEL = 18        # 라벨
FONT_SIZE_GENRE = 22        # AI 추천 장르
FONT_SIZE_FILENAME = 14     # 파일명
FONT_SIZE_BUTTON = 16       # 버튼
FONT_SIZE_COMBO = 15        # 콤보박스

# 색상
COLOR_BG_MAIN = "#1e1e1e"
COLOR_BG_CARD = "#2a2a2a"
COLOR_BG_INFO = "#333333"
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#CCCCCC"
COLOR_ACCENT_ORANGE = "#FF9500"
COLOR_ACCENT_YELLOW = "#FFD60A"
COLOR_ACCENT_BLUE = "#4A90D9"
COLOR_ACCENT_BLUE_HOVER = "#5BA0E9"
COLOR_ACCENT_GREEN = "#34C759"
COLOR_ACCENT_GREEN_HOVER = "#4AD769"
COLOR_ACCENT_GRAY = "#555555"
COLOR_ACCENT_GRAY_HOVER = "#666666"

# 여백
PAD_OUTER = 25
PAD_INNER = 20
PAD_SECTION = 20

# 컨트롤 크기
BTN_HEIGHT = 50
BTN_WIDTH = 160
COMBO_HEIGHT = 45
COMBO_WIDTH = 350

# 다이얼로그 크기 (높이 충분히 확보)
DIALOG_WIDTH = 800
DIALOG_HEIGHT = 580


class GenreConfirmDialog(ctk.CTkToplevel):
    """장르 확인 다이얼로그"""
    
    def __init__(self, parent, filename: str, suggested_genre: str,
                 confidence: str, genre_list: List[str]):
        super().__init__(parent)
        
        self.filename = filename
        self.suggested_genre = suggested_genre
        self.confidence = confidence
        self.genre_list = genre_list
        self.selected_genre: Optional[str] = None
        self.confirmed = False
        
        # 다이얼로그 설정
        self.title("장르 확인")
        self.geometry(f"{DIALOG_WIDTH}x{DIALOG_HEIGHT}")
        self.minsize(DIALOG_WIDTH, DIALOG_HEIGHT)
        self.configure(fg_color=COLOR_BG_MAIN)
        
        # 모달 설정
        self.transient(parent)
        self.grab_set()
        
        # 중앙 배치
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - DIALOG_WIDTH) // 2
        y = parent.winfo_y() + (parent.winfo_height() - DIALOG_HEIGHT) // 2
        self.geometry(f"{DIALOG_WIDTH}x{DIALOG_HEIGHT}+{x}+{y}")
        
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.focus_set()

    def _create_widgets(self):
        """UI 위젯 생성"""
        
        # 메인 카드
        main_card = ctk.CTkFrame(
            self, 
            fg_color=COLOR_BG_CARD, 
            corner_radius=16,
            border_width=2, 
            border_color=COLOR_ACCENT_ORANGE
        )
        main_card.pack(fill="both", expand=True, padx=PAD_OUTER, pady=PAD_OUTER)
        
        # ========== 제목 섹션 ==========
        title_frame = ctk.CTkFrame(main_card, fg_color="transparent")
        title_frame.pack(fill="x", padx=PAD_INNER, pady=(PAD_INNER, PAD_SECTION))
        
        # 경고 아이콘 + 제목
        header_row = ctk.CTkFrame(title_frame, fg_color="transparent")
        header_row.pack(fill="x")
        
        icon_label = ctk.CTkLabel(
            header_row, 
            text="⚠️", 
            font=ctk.CTkFont(size=48),
            text_color=COLOR_ACCENT_YELLOW
        )
        icon_label.pack(side="left", padx=(0, 15))
        
        title_label = ctk.CTkLabel(
            header_row, 
            text="장르 확인 필요",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_TITLE, weight="bold"),
            text_color=COLOR_ACCENT_YELLOW
        )
        title_label.pack(side="left", anchor="w")
        
        # 설명
        desc_label = ctk.CTkLabel(
            title_frame, 
            text=f"AI의 장르 분류 신뢰도가 '{self.confidence}'입니다.\n아래 파일의 장르를 확인해주세요.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SUBTITLE),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left"
        )
        desc_label.pack(anchor="w", pady=(10, 0))
        
        # ========== 파일명 카드 ==========
        file_card = ctk.CTkFrame(
            main_card, 
            fg_color=COLOR_BG_INFO, 
            corner_radius=12
        )
        file_card.pack(fill="x", padx=PAD_INNER, pady=(0, PAD_SECTION))
        
        file_inner = ctk.CTkFrame(file_card, fg_color="transparent")
        file_inner.pack(fill="x", padx=15, pady=15)
        
        file_label = ctk.CTkLabel(
            file_inner, 
            text="파일명:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LABEL, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        file_label.pack(anchor="w")
        
        filename_text = self.filename if len(self.filename) < 55 else self.filename[:52] + "..."
        filename_value = ctk.CTkLabel(
            file_inner, 
            text=filename_text,
            font=ctk.CTkFont(family="Consolas", size=FONT_SIZE_FILENAME),
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=600
        )
        filename_value.pack(anchor="w", pady=(8, 0))
        
        # ========== AI 추천 장르 카드 ==========
        ai_card = ctk.CTkFrame(
            main_card, 
            fg_color=COLOR_BG_INFO, 
            corner_radius=12
        )
        ai_card.pack(fill="x", padx=PAD_INNER, pady=(0, PAD_SECTION))
        
        ai_inner = ctk.CTkFrame(ai_card, fg_color="transparent")
        ai_inner.pack(fill="x", padx=15, pady=15)
        
        ai_label = ctk.CTkLabel(
            ai_inner, 
            text="AI 추천 장르:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LABEL, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        ai_label.pack(anchor="w")
        
        genre_value = ctk.CTkLabel(
            ai_inner, 
            text=f"[{self.suggested_genre}]",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_GENRE, weight="bold"),
            text_color=COLOR_ACCENT_ORANGE
        )
        genre_value.pack(anchor="w", pady=(8, 0))
        
        # ========== 장르 선택 ==========
        select_frame = ctk.CTkFrame(main_card, fg_color="transparent")
        select_frame.pack(fill="x", padx=PAD_INNER, pady=(0, PAD_SECTION))
        
        select_label = ctk.CTkLabel(
            select_frame, 
            text="장르 선택:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LABEL, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        select_label.pack(anchor="w", pady=(0, 10))
        
        self.genre_var = ctk.StringVar(value=self.suggested_genre)
        self.genre_combo = ctk.CTkComboBox(
            select_frame, 
            values=self.genre_list, 
            variable=self.genre_var,
            width=COMBO_WIDTH, 
            height=COMBO_HEIGHT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_COMBO),
            dropdown_font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_COMBO),
            corner_radius=10, 
            border_width=2, 
            border_color=COLOR_ACCENT_BLUE,
            fg_color=COLOR_BG_INFO,
            text_color=COLOR_TEXT_PRIMARY,
            button_color=COLOR_ACCENT_BLUE,
            button_hover_color=COLOR_ACCENT_BLUE_HOVER
        )
        self.genre_combo.pack(anchor="w")
        
        # ========== 버튼 영역 ==========
        button_frame = ctk.CTkFrame(main_card, fg_color="transparent")
        button_frame.pack(fill="x", padx=PAD_INNER, pady=(0, PAD_INNER))
        
        # 선택 확인 버튼
        confirm_btn = ctk.CTkButton(
            button_frame, 
            text="✓ 선택 확인",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BUTTON, weight="bold"),
            width=BTN_WIDTH, 
            height=BTN_HEIGHT, 
            corner_radius=12,
            fg_color=COLOR_ACCENT_GREEN, 
            hover_color=COLOR_ACCENT_GREEN_HOVER,
            command=self._on_confirm
        )
        confirm_btn.pack(side="left", padx=(0, 10))
        
        # AI 추천 사용 버튼
        ai_btn = ctk.CTkButton(
            button_frame, 
            text="🤖 AI 추천 사용",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BUTTON, weight="bold"),
            width=BTN_WIDTH + 20, 
            height=BTN_HEIGHT, 
            corner_radius=12,
            fg_color=COLOR_ACCENT_BLUE, 
            hover_color=COLOR_ACCENT_BLUE_HOVER,
            command=self._on_use_ai
        )
        ai_btn.pack(side="left", padx=(0, 10))
        
        # 건너뛰기 버튼
        skip_btn = ctk.CTkButton(
            button_frame, 
            text="건너뛰기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BUTTON),
            width=BTN_WIDTH - 30, 
            height=BTN_HEIGHT, 
            corner_radius=12,
            fg_color=COLOR_ACCENT_GRAY, 
            hover_color=COLOR_ACCENT_GRAY_HOVER,
            command=self._on_skip
        )
        skip_btn.pack(side="left")
    
    def _on_confirm(self):
        self.selected_genre = self.genre_var.get()
        self.confirmed = True
        self.destroy()
    
    def _on_use_ai(self):
        self.selected_genre = self.suggested_genre
        self.confirmed = True
        self.destroy()
    
    def _on_skip(self):
        self.selected_genre = None
        self.confirmed = False
        self.destroy()
    
    def _on_cancel(self):
        self.selected_genre = None
        self.confirmed = False
        self.destroy()
    
    def get_result(self) -> tuple:
        return self.confirmed, self.selected_genre


def show_genre_confirm_dialog(parent, filename: str, suggested_genre: str,
                               confidence: str, genre_list: List[str]) -> tuple:
    """장르 확인 다이얼로그 표시"""
    dialog = GenreConfirmDialog(parent, filename, suggested_genre, confidence, genre_list)
    dialog.wait_window()
    return dialog.get_result()
