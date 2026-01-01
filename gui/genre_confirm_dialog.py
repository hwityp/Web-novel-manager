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


# ... (Keep existing imports)

# ============================================================================
# 스타일 상수
# ============================================================================
FONT_FAMILY = "Segoe UI"

# 폰트 크기 (가독성 위해 대폭 확대 1.3배)
FONT_SIZE_TITLE = 34        # 제목 (26 -> 34)
FONT_SIZE_SUBTITLE = 20     # 부제목 (16 -> 20)
FONT_SIZE_LABEL = 24        # 라벨 (18 -> 24)
FONT_SIZE_GENRE = 30        # AI 추천 장르 (22 -> 30)
FONT_SIZE_FILENAME = 18     # 파일명 (14 -> 18)
FONT_SIZE_BUTTON = 24       # 버튼 (18 -> 24)
FONT_SIZE_COMBO = 20        # 콤보박스 (16 -> 20)

# 색상
COLOR_BG_MAIN = "#1e1e1e"
COLOR_BG_CARD = "#2a2a2a"
COLOR_BG_INFO = "#333333"
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#CCCCCC"
COLOR_ACCENT_ORANGE = "#FF9500"
COLOR_ACCENT_YELLOW = "#FFD60A"
COLOR_ACCENT_BLUE = "#3498DB"       # 요청 색상 (밝은 파랑)
COLOR_ACCENT_BLUE_HOVER = "#5DADE2"
COLOR_ACCENT_GREEN = "#2ECC71"      # 요청 색상 (밝은 초록)
COLOR_ACCENT_GREEN_HOVER = "#58D68D"
COLOR_ACCENT_GRAY = "#555555"
COLOR_ACCENT_GRAY_HOVER = "#666666"

# 여백
PAD_OUTER = 30      # 외곽 여백 증가
PAD_INNER = 25
PAD_SECTION = 30    # 섹션 간격 증가

# 컨트롤 크기
BTN_HEIGHT = 80     # 버튼 높이 대폭 증가 (시원한 클릭감)
BTN_WIDTH = 200     # 버튼 너비 증가
COMBO_HEIGHT = 60   # 콤보박스 높이 증가
COMBO_WIDTH = 450   # 콤보박스 너비 증가

# ... (Keep constants)
# 다이얼로그 크기
DIALOG_WIDTH = 900
MIN_DIALOG_HEIGHT = 600 # 최소 높이만 지정


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
        # 고정 크기 제거 및 자동 크기 조정
        # self.minsize(DIALOG_WIDTH, MIN_DIALOG_HEIGHT) # 제거
        self.configure(fg_color=COLOR_BG_MAIN)
        
        # 모달 설정
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # 내용물에 맞춰 크기 조정 및 중앙 배치
        self.update_idletasks()
        
        req_width = self.winfo_reqwidth()
        req_height = self.winfo_reqheight()
        
        # 최소 너비는 보장
        if req_width < DIALOG_WIDTH:
            req_width = DIALOG_WIDTH
            
        # 부모 윈도우 중앙 계산
        x = parent.winfo_x() + (parent.winfo_width() - req_width) // 2
        y = parent.winfo_y() + (parent.winfo_height() - req_height) // 2
        
        # 화면 벗어남 방지
        if y < 0: y = 0
        
        self.geometry(f"{req_width}x{req_height}+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.focus_set()
    def _create_widgets(self):
        """UI 위젯 생성"""
        
        # 메인 카드
        main_card = ctk.CTkFrame(
            self, 
            fg_color=COLOR_BG_CARD, 
            corner_radius=20, # 모서리 조금 더 둥글게
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
            font=ctk.CTkFont(size=60), # 아이콘 확대 (48 -> 60)
            text_color=COLOR_ACCENT_YELLOW
        )
        icon_label.pack(side="left", padx=(0, 20))
        
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
        desc_label.pack(anchor="w", pady=(15, 0))
        
        # ========== 파일명 카드 ==========
        file_card = ctk.CTkFrame(
            main_card, 
            fg_color=COLOR_BG_INFO, 
            corner_radius=16
        )
        file_card.pack(fill="x", padx=PAD_INNER, pady=(0, PAD_SECTION))
        
        file_inner = ctk.CTkFrame(file_card, fg_color="transparent")
        file_inner.pack(fill="x", padx=25, pady=25) # 내부 패딩 확대
        
        file_label = ctk.CTkLabel(
            file_inner, 
            text="파일명:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LABEL, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        file_label.pack(anchor="w")
        
        # 파일명 줄바꿈 및 길이 처리
        filename_text = self.filename
        filename_value = ctk.CTkLabel(
            file_inner, 
            text=filename_text,
            font=ctk.CTkFont(family="Consolas", size=FONT_SIZE_FILENAME),
            text_color=COLOR_TEXT_SECONDARY,
            wraplength=700, # 긴 파일명 줄바꿈 허용 (650 -> 700)
            justify="left"
        )
        filename_value.pack(anchor="w", pady=(10, 0))
        
        # ========== AI 추천 장르 카드 ==========
        ai_card = ctk.CTkFrame(
            main_card, 
            fg_color=COLOR_BG_INFO, 
            corner_radius=16
        )
        ai_card.pack(fill="x", padx=PAD_INNER, pady=(0, PAD_SECTION))
        
        ai_inner = ctk.CTkFrame(ai_card, fg_color="transparent")
        ai_inner.pack(fill="x", padx=25, pady=25)
        
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
        genre_value.pack(anchor="w", pady=(10, 0))
        
        # ========== 장르 선택 ==========
        select_frame = ctk.CTkFrame(main_card, fg_color="transparent")
        select_frame.pack(fill="x", padx=PAD_INNER, pady=(0, PAD_SECTION + 15)) # 하단 여백 추가
        
        select_label = ctk.CTkLabel(
            select_frame, 
            text="장르 선택:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LABEL, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        select_label.pack(anchor="w", pady=(0, 15))
        
        self.genre_var = ctk.StringVar(value=self.suggested_genre)
        self.genre_combo = ctk.CTkComboBox(
            select_frame, 
            values=self.genre_list, 
            variable=self.genre_var,
            width=COMBO_WIDTH, 
            height=COMBO_HEIGHT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_COMBO),
            dropdown_font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_COMBO),
            corner_radius=12, 
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
        button_frame.pack(fill="x", padx=PAD_INNER, pady=(0, PAD_INNER + 20)) # 하단 패딩 대폭 추가 (버튼 잘림 방지)
        
        # 선택 확인 버튼 (Green Glow)
        confirm_btn = ctk.CTkButton(
            button_frame, 
            text="✓ 선택 확인",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BUTTON, weight="bold"),
            height=BTN_HEIGHT, 
            corner_radius=20, # 더 둥글게
            fg_color=COLOR_ACCENT_GREEN, 
            hover_color=COLOR_ACCENT_GREEN_HOVER,
            border_width=3, # 테두리 두껍게
            border_color="#82E0AA", # Glow
            command=self._on_confirm
        )
        confirm_btn.pack(side="left", padx=15, expand=True, fill="x")
        
        # AI 추천 사용 버튼 (Blue Glow)
        ai_btn = ctk.CTkButton(
            button_frame, 
            text="🤖 AI 추천 사용",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BUTTON, weight="bold"),
            height=BTN_HEIGHT, 
            corner_radius=20,
            fg_color=COLOR_ACCENT_BLUE, 
            hover_color=COLOR_ACCENT_BLUE_HOVER,
            border_width=3,
            border_color="#85C1E9", # Glow
            command=self._on_use_ai
        )
        ai_btn.pack(side="left", padx=15, expand=True, fill="x")
        
        # 건너뛰기 버튼 (Normal)
        skip_btn = ctk.CTkButton(
            button_frame, 
            text="건너뛰기",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BUTTON),
            height=BTN_HEIGHT, 
            corner_radius=20,
            fg_color=COLOR_ACCENT_GRAY, 
            hover_color=COLOR_ACCENT_GRAY_HOVER,
            border_width=2,
            border_color="#777777",
            command=self._on_skip
        )
        skip_btn.pack(side="left", padx=15, expand=True, fill="x")
    
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
