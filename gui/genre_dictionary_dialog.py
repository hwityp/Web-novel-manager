"""
==============================================================================
파일: gui/genre_dictionary_dialog.py
역할 및 목적:
    통합 장르 키워드 사전(`genre_keywords.json`)의 조회, 검색, 추가, 수정, 삭제(CRUD) 및
    캐시 데이터(`config/genre_cache.json`) 마이닝/원자적 동기화,
    특성/팬덤/중국 음독 패턴 레퍼런스를 총괄 관리하는 고성능 GUI 대화상자.
주요 구성 요소:
    - AddKeywordDialog: 신규 키워드 등록 모달
    - EditWeightDialog: 키워드 가중치 수정 모달
    - GenreDictionaryDialog: 종합 사전 관리 모달 다이얼로그 (3개 탭 뷰)
    - show_genre_dictionary_dialog(): 모달 호출 헬퍼 함수
==============================================================================
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from core.utils.genre_cache_miner import GenreCacheMiner, GenreCandidate
from core.utils.keyword_syncer import KeywordSyncer, SyncResult
from core.utils.novel_trait_extractor import PARODY_FANDOM_MAP, TRAIT_PATTERNS
from core.utils.chinese_phonetic_analyzer import ChinesePhoneticAnalyzer

# 스타일 상수 정의 (메인 윈도우 THEME 일관성 준수)
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

THEME = {
    "bg_main": "#2b2b2b",
    "bg_card": "#363636",
    "bg_card_hover": "#404040",
    "bg_input": "#1e1e1e",
    "text_primary": "#FFFFFF",
    "text_secondary": "#E0E0E0",
    "text_muted": "#B0B0B0",
    "button_text": "#FFFFFF",
    "accent_blue": "#5A9FE9",
    "accent_blue_hover": "#6BB0FA",
    "accent_green": "#5DBF60",
    "accent_green_hover": "#6ED071",
    "accent_orange": "#FF9500",
    "accent_red": "#EF4444",
    "accent_red_hover": "#F87171",
    "accent_gray": "#707070",
    "accent_gray_hover": "#808080",
    "status_success": "#4ade80",
    "status_error": "#f87171",
    "table_bg": "#2b2b2b",
    "table_header": "#404040",
    "table_selected": "#4A90D9",
}

GENRE_LIST = [
    "무협", "현판", "퓨판", "판타지", "선협", "로판", "언정",
    "패러디", "겜판", "역사", "스포츠", "SF", "밀리터리", "공포", "현대"
]


class AddKeywordDialog(ctk.CTkToplevel):
    """신규 키워드 추가 팝업 모달"""

    def __init__(self, parent, syncer: KeywordSyncer, on_success):
        super().__init__(parent)
        self.parent = parent
        self.syncer = syncer
        self.on_success = on_success

        self.title("➕ 신규 장르 키워드 등록")
        self.geometry("440x330")
        self.minsize(400, 310)
        self.configure(fg_color=THEME["bg_main"])

        self.transient(parent)
        self.grab_set()

        # 화면 중앙 배치
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 220
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 165
        self.geometry(f"+{max(50, x)}+{max(50, y)}")

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color=THEME["bg_card"], corner_radius=10)
        container.pack(fill="both", expand=True, padx=15, pady=15)

        title_lbl = ctk.CTkLabel(
            container,
            text="➕ 사전 키워드 신규 등록",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=THEME["text_primary"]
        )
        title_lbl.pack(anchor="w", padx=15, pady=(15, 12))

        # 1. 키워드 입력
        kw_frame = ctk.CTkFrame(container, fg_color="transparent")
        kw_frame.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(
            kw_frame, text="키워드/단어:", width=90, anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=THEME["text_secondary"]
        ).pack(side="left")
        self.entry_kw = ctk.CTkEntry(
            kw_frame, placeholder_text="예: 탄서성공, 귀호, 붕괴",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=THEME["bg_input"], text_color=THEME["text_primary"]
        )
        self.entry_kw.pack(side="left", fill="x", expand=True)

        # 2. 장르 선택
        genre_frame = ctk.CTkFrame(container, fg_color="transparent")
        genre_frame.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(
            genre_frame, text="소속 장르:", width=90, anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=THEME["text_secondary"]
        ).pack(side="left")
        self.opt_genre = ctk.CTkOptionMenu(
            genre_frame,
            values=GENRE_LIST,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=THEME["bg_input"],
            button_color=THEME["accent_blue"],
            text_color=THEME["text_primary"]
        )
        self.opt_genre.set("현판")
        self.opt_genre.pack(side="left", fill="x", expand=True)

        # 3. 가중치 선택 (1 ~ 10)
        weight_frame = ctk.CTkFrame(container, fg_color="transparent")
        weight_frame.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(
            weight_frame, text="가중치 (1~10):", width=90, anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=THEME["text_secondary"]
        ).pack(side="left")
        self.opt_weight = ctk.CTkOptionMenu(
            weight_frame,
            values=[str(i) for i in range(10, 0, -1)],
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=THEME["bg_input"],
            button_color=THEME["accent_blue"],
            text_color=THEME["text_primary"]
        )
        self.opt_weight.set("8")
        self.opt_weight.pack(side="left", fill="x", expand=True)

        # 4. 하단 버튼
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(15, 10))

        btn_cancel = ctk.CTkButton(
            btn_frame, text="취소", width=90, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["accent_gray"], hover_color=THEME["accent_gray_hover"],
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_submit = ctk.CTkButton(
            btn_frame, text="등록", width=90, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"],
            command=self._on_submit
        )
        btn_submit.pack(side="right")

    def _on_submit(self):
        kw = self.entry_kw.get().strip()
        genre = self.opt_genre.get().strip()
        weight = int(self.opt_weight.get())

        if not kw:
            messagebox.showwarning("입력 오류", "등록할 키워드를 입력하세요.", parent=self)
            return

        result = self.syncer.add_or_update_keyword(kw, genre, weight, run_regression_test=False)
        if result.success:
            self.on_success(f"키워드 등록 완료: [{genre}] '{kw}' (가중치: {weight})")
            self.destroy()
        else:
            messagebox.showerror("등록 실패", result.error_message or "알 수 없는 오류", parent=self)


class EditWeightDialog(ctk.CTkToplevel):
    """키워드 가중치 수정 팝업 모달"""

    def __init__(self, parent, syncer: KeywordSyncer, keyword: str, genre: str, current_weight: int, on_success):
        super().__init__(parent)
        self.parent = parent
        self.syncer = syncer
        self.keyword = keyword
        self.genre = genre
        self.current_weight = current_weight
        self.on_success = on_success

        self.title("✏️ 키워드 가중치 수정")
        self.geometry("380x270")
        self.minsize(360, 250)
        self.configure(fg_color=THEME["bg_main"])

        self.transient(parent)
        self.grab_set()

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 190
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 135
        self.geometry(f"+{max(50, x)}+{max(50, y)}")

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color=THEME["bg_card"], corner_radius=10)
        container.pack(fill="both", expand=True, padx=15, pady=15)

        title_lbl = ctk.CTkLabel(
            container,
            text=f"✏️ [{self.genre}] {self.keyword}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=THEME["text_primary"]
        )
        title_lbl.pack(anchor="w", padx=15, pady=(15, 12))

        weight_frame = ctk.CTkFrame(container, fg_color="transparent")
        weight_frame.pack(fill="x", padx=15, pady=8)
        ctk.CTkLabel(
            weight_frame, text="가중치 (1~10):", width=100, anchor="w",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=THEME["text_secondary"]
        ).pack(side="left")

        self.opt_weight = ctk.CTkOptionMenu(
            weight_frame,
            values=[str(i) for i in range(10, 0, -1)],
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=THEME["bg_input"],
            button_color=THEME["accent_blue"],
            text_color=THEME["text_primary"]
        )
        self.opt_weight.set(str(self.current_weight))
        self.opt_weight.pack(side="left", fill="x", expand=True)

        desc_lbl = ctk.CTkLabel(
            container,
            text="10점: 결정적 핵심 키워드 / 7~9점: 주요 키워드 / 1~6점: 보조 키워드",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=THEME["text_muted"]
        )
        desc_lbl.pack(anchor="w", padx=15, pady=(5, 10))

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(10, 10))

        btn_cancel = ctk.CTkButton(
            btn_frame, text="취소", width=80, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["accent_gray"], hover_color=THEME["accent_gray_hover"],
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_submit = ctk.CTkButton(
            btn_frame, text="적용", width=80, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["accent_blue"], hover_color=THEME["accent_blue_hover"],
            command=self._on_submit
        )
        btn_submit.pack(side="right")

    def _on_submit(self):
        new_weight = int(self.opt_weight.get())
        result = self.syncer.add_or_update_keyword(self.keyword, self.genre, new_weight, run_regression_test=False)
        if result.success:
            self.on_success(f"가중치 변경 완료: [{self.genre}] '{self.keyword}' ({self.current_weight} -> {new_weight})")
            self.destroy()
        else:
            messagebox.showerror("수정 실패", result.error_message or "알 수 없는 오류", parent=self)


class GenreDictionaryDialog(ctk.CTkToplevel):
    """통합 장르 키워드 사전 관리 센터 모달 다이얼로그"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("📚 통합 장르 키워드 사전 관리 센터")
        self.geometry("1060x780")
        self.minsize(980, 680)
        self.configure(fg_color=THEME["bg_main"])

        # 모달 설정
        self.transient(parent)
        self.grab_set()

        # 화면 중앙 배치
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 530
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 390
        self.geometry(f"+{max(40, x)}+{max(30, y)}")

        # 서비스 인스턴스
        self.miner = GenreCacheMiner()
        self.syncer = KeywordSyncer()
        self.candidates: List[GenreCandidate] = []
        self.candidate_checked: List[bool] = []
        self.current_keywords: List[Dict[str, Any]] = []

        # 위젯 생성 및 초기화
        self._create_widgets()
        self._refresh_stats()
        self._reload_keywords_table()

    def _create_widgets(self):
        """다이얼로그 내부 전체 위젯 트리 구성"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # 탭 뷰 영역 확장

        # 1. 헤더 섹션
        self._create_header_section()

        # 2. 통계 요약 카드 섹션 (4종)
        self._create_stats_cards()

        # 3. 탭뷰 (키워드 관리 / 캐시 마이닝 / 특성 및 음독 레퍼런스)
        self._create_tabview_section()

        # 4. 하단 실시간 콘솔 로그 및 닫기 버튼
        self._create_bottom_section()

    def _create_header_section(self):
        """헤더 영역"""
        header_frame = ctk.CTkFrame(self, fg_color=THEME["bg_card"], corner_radius=10)
        header_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")

        title_label = ctk.CTkLabel(
            header_frame,
            text="📚 통합 장르 키워드 사전 관리 센터",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=THEME["text_primary"]
        )
        title_label.pack(anchor="w", padx=15, pady=(12, 4))

        sub_label = ctk.CTkLabel(
            header_frame,
            text="장르별 키워드 조회/검색/추가/수정/삭제(CRUD), 캐시 데이터 자동 마이닝 및 원자적 이중 파일 동기화를 안전하게 수행합니다.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"]
        )
        sub_label.pack(anchor="w", padx=15, pady=(0, 12))

    def _create_stats_cards(self):
        """상단 4대 통계 요약 카드"""
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")
        for i in range(4):
            stats_frame.grid_columnconfigure(i, weight=1)

        self.card_total_kw = self._build_stat_card(stats_frame, 0, "총 등록 키워드", "-", THEME["accent_blue"])
        self.card_version = self._build_stat_card(stats_frame, 1, "사전 버전 / 갱신일", "-", THEME["text_primary"])
        self.card_genres = self._build_stat_card(stats_frame, 2, "지원 장르 수", "-", THEME["accent_green"])
        self.card_cache = self._build_stat_card(stats_frame, 3, "축적 캐시 / 후보", "-", THEME["accent_orange"])

    def _build_stat_card(self, parent, col: int, label: str, value: str, color: str) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent, fg_color=THEME["bg_card"], corner_radius=10)
        card.grid(row=0, column=col, padx=5, sticky="ew")

        lbl = ctk.CTkLabel(
            card, text=label,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"]
        )
        lbl.pack(anchor="w", padx=12, pady=(8, 2))

        val_lbl = ctk.CTkLabel(
            card, text=value,
            font=ctk.CTkFont(family=FONT_FAMILY, size=17, weight="bold"),
            text_color=color
        )
        val_lbl.pack(anchor="w", padx=12, pady=(0, 8))
        return val_lbl

    def _create_tabview_section(self):
        """3개 탭 구성 (등록 키워드 관리 / 캐시 마이닝 / 레퍼런스 사전)"""
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=THEME["bg_card"],
            segmented_button_fg_color=THEME["bg_input"],
            segmented_button_selected_color=THEME["accent_blue"],
            segmented_button_selected_hover_color=THEME["accent_blue_hover"],
            segmented_button_unselected_color=THEME["bg_card"],
            text_color=THEME["text_primary"]
        )
        self.tabview.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="nsew")

        # 탭 3개 생성
        self.tab_keywords = self.tabview.add("📖 등록 키워드 관리 (조회/편집)")
        self.tab_mining = self.tabview.add("⚡ 캐시 마이닝 & 자동 최적화")
        self.tab_reference = self.tabview.add("🏷️ 특성/팬덤 & 음독 패턴 레퍼런스")

        # 탭별 UI 빌드
        self._build_tab_keywords(self.tab_keywords)
        self._build_tab_mining(self.tab_mining)
        self._build_tab_reference(self.tab_reference)

    # --------------------------------------------------------------------------
    # 탭 1: 등록 키워드 관리 (CRUD)
    # --------------------------------------------------------------------------
    def _build_tab_keywords(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # 툴바: 필터 + 검색 + CRUD 액션
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=10, pady=(10, 8), sticky="ew")

        # 장르 필터
        ctk.CTkLabel(
            toolbar, text="장르:", font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=THEME["text_secondary"]
        ).pack(side="left", padx=(0, 5))

        self.filter_genre = ctk.CTkOptionMenu(
            toolbar,
            values=["전체"] + GENRE_LIST,
            width=110, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["bg_input"],
            button_color=THEME["accent_blue"],
            command=lambda _: self._reload_keywords_table()
        )
        self.filter_genre.set("전체")
        self.filter_genre.pack(side="left", padx=(0, 10))

        # 검색 입력창
        self.search_entry = ctk.CTkEntry(
            toolbar,
            placeholder_text="키워드 검색 (Enter)...",
            width=200, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["bg_input"],
            text_color=THEME["text_primary"]
        )
        self.search_entry.pack(side="left", padx=(0, 6))
        self.search_entry.bind("<Return>", lambda _: self._reload_keywords_table())

        btn_search = ctk.CTkButton(
            toolbar, text="검색", width=60, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["accent_blue"], hover_color=THEME["accent_blue_hover"],
            command=self._reload_keywords_table
        )
        btn_search.pack(side="left", padx=(0, 6))

        btn_reset = ctk.CTkButton(
            toolbar, text="초기화", width=60, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["accent_gray"], hover_color=THEME["accent_gray_hover"],
            command=self._reset_keyword_search
        )
        btn_reset.pack(side="left", padx=(0, 15))

        # 카운트 라벨
        self.lbl_kw_count = ctk.CTkLabel(
            toolbar, text="조회: 0건",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"]
        )
        self.lbl_kw_count.pack(side="left", padx=(0, 10))

        # 우측 액션 버튼들 (추가 / 수정 / 삭제)
        btn_delete = ctk.CTkButton(
            toolbar, text="🗑️ 선택 삭제", width=95, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["accent_red"], hover_color=THEME["accent_red_hover"],
            command=self._on_delete_keywords_clicked
        )
        btn_delete.pack(side="right", padx=(6, 0))

        btn_edit = ctk.CTkButton(
            toolbar, text="✏️ 가중치 수정", width=105, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["accent_blue"], hover_color=THEME["accent_blue_hover"],
            command=self._on_edit_weight_clicked
        )
        btn_edit.pack(side="right", padx=(6, 0))

        btn_add = ctk.CTkButton(
            toolbar, text="➕ 키워드 추가", width=105, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=THEME["accent_green"], hover_color=THEME["accent_green_hover"],
            command=self._on_add_keyword_clicked
        )
        btn_add.pack(side="right", padx=(6, 0))

        # Treeview 테이블
        tree_container = ctk.CTkFrame(parent, fg_color=THEME["table_bg"], corner_radius=6)
        tree_container.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dict.Treeview",
            background=THEME["table_bg"],
            foreground=THEME["text_primary"],
            fieldbackground=THEME["table_bg"],
            rowheight=28,
            font=(FONT_FAMILY, 11),
            borderwidth=0
        )
        style.configure(
            "Dict.Treeview.Heading",
            background=THEME["table_header"],
            foreground=THEME["text_primary"],
            font=(FONT_FAMILY, 11, 'bold'),
            borderwidth=1,
            relief="solid"
        )
        style.map("Dict.Treeview", background=[("selected", THEME["table_selected"])])

        kw_columns = ("idx", "keyword", "genre", "weight", "tier")
        self.tree_kw = ttk.Treeview(
            tree_container,
            columns=kw_columns,
            show="headings",
            style="Dict.Treeview",
            selectmode="extended"
        )
        self.tree_kw.heading("idx", text="번호")
        self.tree_kw.heading("keyword", text="키워드 / 어휘")
        self.tree_kw.heading("genre", text="소속 장르")
        self.tree_kw.heading("weight", text="가중치 (1~10)")
        self.tree_kw.heading("tier", text="우선도 등급")

        self.tree_kw.column("idx", width=60, anchor="center")
        self.tree_kw.column("keyword", width=260)
        self.tree_kw.column("genre", width=120, anchor="center")
        self.tree_kw.column("weight", width=120, anchor="center")
        self.tree_kw.column("tier", width=180, anchor="center")

        kw_y_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_kw.yview)
        kw_x_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree_kw.xview)
        self.tree_kw.configure(yscrollcommand=kw_y_scroll.set, xscrollcommand=kw_x_scroll.set)

        self.tree_kw.grid(row=0, column=0, sticky="nsew")
        kw_y_scroll.grid(row=0, column=1, sticky="ns")
        kw_x_scroll.grid(row=1, column=0, sticky="ew")

        # 더블 클릭 시 바로 가중치 수정 모달 호출
        self.tree_kw.bind("<Double-1>", lambda _: self._on_edit_weight_clicked())

    def _reset_keyword_search(self):
        self.filter_genre.set("전체")
        self.search_entry.delete(0, "end")
        self._reload_keywords_table()

    def _reload_keywords_table(self):
        genre = self.filter_genre.get().strip()
        search = self.search_entry.get().strip()

        kws = self.syncer.get_keywords(genre=genre if genre != "전체" else None, search=search if search else None)
        self.current_keywords = kws

        for item in self.tree_kw.get_children():
            self.tree_kw.delete(item)

        for i, item in enumerate(kws, 1):
            w = item["weight"]
            tier_str = "⭐ 핵심 (10)" if w == 10 else ("🔷 주요 (7-9)" if w >= 7 else ("🔸 보조 (4-6)" if w >= 4 else "▫️ 일반 (1-3)"))
            self.tree_kw.insert("", "end", values=(i, item["keyword"], item["genre"], w, tier_str))

        self.lbl_kw_count.configure(text=f"조회: {len(kws):,}건")

    def _on_add_keyword_clicked(self):
        AddKeywordDialog(self, self.syncer, self._on_action_success)

    def _on_edit_weight_clicked(self):
        selected = self.tree_kw.selection()
        if not selected:
            messagebox.showinfo("알림", "수정할 키워드를 테이블에서 먼저 선택하세요.", parent=self)
            return

        item = self.tree_kw.item(selected[0])
        raw_vals = item.get("values", [])
        if not isinstance(raw_vals, (list, tuple)) or len(raw_vals) < 4:
            return
        kw = str(raw_vals[1])
        genre = str(raw_vals[2])
        weight = int(raw_vals[3])

        EditWeightDialog(self, self.syncer, kw, genre, weight, self._on_action_success)

    def _on_delete_keywords_clicked(self):
        selected = self.tree_kw.selection()
        if not selected:
            messagebox.showinfo("알림", "삭제할 키워드를 테이블에서 선택하세요.", parent=self)
            return

        items_to_delete = []
        for s in selected:
            raw_vals = self.tree_kw.item(s).get("values", [])
            if isinstance(raw_vals, (list, tuple)) and len(raw_vals) >= 3:
                items_to_delete.append((str(raw_vals[1]), str(raw_vals[2])))

        msg = f"선택한 {len(items_to_delete)}개의 키워드를 사전에서 영구 삭제하시겠습니까?\n"
        if len(items_to_delete) <= 5:
            msg += "\n" + "\n".join([f" • [{g}] {kw}" for kw, g in items_to_delete])
        else:
            msg += f"\n(예: [{items_to_delete[0][1]}] {items_to_delete[0][0]} 외 {len(items_to_delete)-1}개)"

        if not messagebox.askyesno("키워드 삭제 확인", msg, parent=self):
            return

        result = self.syncer.batch_delete_keywords(items_to_delete, run_regression_test=False)
        if result.success:
            self._on_action_success(f"키워드 {len(items_to_delete)}개 삭제 완료")
        else:
            messagebox.showerror("삭제 실패", result.error_message or "알 수 없는 오류", parent=self)

    def _on_action_success(self, log_msg: str):
        self._append_log(f"[✓] {log_msg}")
        self._refresh_stats()
        self._reload_keywords_table()

    # --------------------------------------------------------------------------
    # 탭 2: 캐시 마이닝 & 자동 최적화
    # --------------------------------------------------------------------------
    def _build_tab_mining(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=10, pady=(10, 8), sticky="ew")

        btn_mine = ctk.CTkButton(
            toolbar,
            text="🔍 1단계: 캐시 마이닝 실행",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
            width=170, height=34,
            command=self._start_mining_thread
        )
        btn_mine.pack(side="left", padx=(0, 10))

        self.btn_sync = ctk.CTkButton(
            toolbar,
            text="⚡ 2단계: 선택 후보 사전 반영",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=THEME["accent_green"],
            hover_color=THEME["accent_green_hover"],
            width=190, height=34,
            command=self._start_sync_thread
        )
        self.btn_sync.pack(side="left", padx=(0, 15))

        self.check_regression = ctk.CTkCheckBox(
            toolbar,
            text="동기화 후 자동 회귀 검증(pytest) 수행",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_secondary"]
        )
        self.check_regression.pack(side="left", padx=(0, 15))
        self.check_regression.select()

        # 체크 관리 버튼
        btn_check_all = ctk.CTkButton(
            toolbar, text="✓ 전체 선택", width=85, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["bg_card"], hover_color=THEME["bg_card_hover"],
            command=lambda: self._set_all_candidates_checked(True)
        )
        btn_check_all.pack(side="right", padx=(4, 0))

        btn_uncheck_all = ctk.CTkButton(
            toolbar, text="✗ 선택 해제", width=85, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["bg_card"], hover_color=THEME["bg_card_hover"],
            command=lambda: self._set_all_candidates_checked(False)
        )
        btn_uncheck_all.pack(side="right", padx=(4, 0))

        btn_remove_candidate = ctk.CTkButton(
            toolbar, text="🗑️ 후보 제외", width=85, height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=THEME["accent_red"], hover_color=THEME["accent_red_hover"],
            command=self._remove_selected_candidates
        )
        btn_remove_candidate.pack(side="right", padx=(4, 0))

        # 후보군 테이블
        tree_container = ctk.CTkFrame(parent, fg_color=THEME["table_bg"], corner_radius=6)
        tree_container.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        columns = ("check", "keyword", "genre", "count", "purity", "weight", "source")
        self.tree_candidates = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Dict.Treeview",
            selectmode="extended"
        )

        self.tree_candidates.heading("check", text="선택")
        self.tree_candidates.heading("keyword", text="키워드 / 어휘")
        self.tree_candidates.heading("genre", text="추천 장르")
        self.tree_candidates.heading("count", text="출현 빈도")
        self.tree_candidates.heading("purity", text="순도(Purity)")
        self.tree_candidates.heading("weight", text="제안 가중치")
        self.tree_candidates.heading("source", text="단서 출처 / CJK 원문")

        self.tree_candidates.column("check", width=60, anchor="center")
        self.tree_candidates.column("keyword", width=180)
        self.tree_candidates.column("genre", width=110, anchor="center")
        self.tree_candidates.column("count", width=80, anchor="center")
        self.tree_candidates.column("purity", width=90, anchor="center")
        self.tree_candidates.column("weight", width=90, anchor="center")
        self.tree_candidates.column("source", width=240)

        y_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_candidates.yview)
        x_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree_candidates.xview)
        self.tree_candidates.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree_candidates.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        # 클릭 시 체크 토글
        self.tree_candidates.bind("<ButtonRelease-1>", self._on_candidate_row_clicked)

    def _on_candidate_row_clicked(self, event):
        item_id = self.tree_candidates.identify_row(event.y)
        if not item_id:
            return
        children = self.tree_candidates.get_children()
        if item_id in children:
            idx = children.index(item_id)
            if 0 <= idx < len(self.candidate_checked):
                self.candidate_checked[idx] = not self.candidate_checked[idx]
                vals = list(self.tree_candidates.item(item_id, "values"))
                vals[0] = "✓" if self.candidate_checked[idx] else " "
                self.tree_candidates.item(item_id, values=vals)

    def _set_all_candidates_checked(self, checked: bool):
        for idx in range(len(self.candidate_checked)):
            self.candidate_checked[idx] = checked
        children = self.tree_candidates.get_children()
        for i, item_id in enumerate(children):
            vals = list(self.tree_candidates.item(item_id, "values"))
            vals[0] = "✓" if checked else " "
            self.tree_candidates.item(item_id, values=vals)

    def _remove_selected_candidates(self):
        selected = self.tree_candidates.selection()
        if not selected:
            messagebox.showinfo("알림", "제외할 후보를 선택하세요.", parent=self)
            return

        children = list(self.tree_candidates.get_children())
        indices_to_remove = sorted([children.index(s) for s in selected], reverse=True)

        for idx in indices_to_remove:
            if idx < len(self.candidates):
                del self.candidates[idx]
                del self.candidate_checked[idx]
            self.tree_candidates.delete(children[idx])

        self._refresh_stats()
        self._append_log(f"후보 목록에서 {len(indices_to_remove)}개 항목을 제외했습니다.")

    def _start_mining_thread(self):
        self._append_log("[*] 캐시 마이닝 시작 중...")
        threading.Thread(target=self._run_mining, daemon=True).start()

    def _run_mining(self):
        try:
            candidates = self.miner.mine(min_count=1, min_purity=0.6)
            self.candidates = candidates
            self.candidate_checked = [True] * len(candidates)
            self.after(0, self._on_mining_completed)
        except Exception as e:
            self.after(0, lambda: self._append_log(f"[!] 마이닝 오류: {e}"))

    def _on_mining_completed(self):
        self._refresh_stats()
        for item in self.tree_candidates.get_children():
            self.tree_candidates.delete(item)

        for i, c in enumerate(self.candidates):
            cjk = f"원문: {c.cjk_source}" if c.cjk_source else c.source_type
            self.tree_candidates.insert("", "end", values=(
                "✓", c.keyword, c.genre, c.count, f"{c.purity:.2f}", c.suggested_weight, cjk
            ))

        self._append_log(f"[✓] 마이닝 완료: 총 {len(self.candidates)}개의 후보 키워드가 추출되었습니다.")

    def _start_sync_thread(self):
        selected_candidates = [
            c for i, c in enumerate(self.candidates)
            if i < len(self.candidate_checked) and self.candidate_checked[i]
        ]

        if not selected_candidates:
            self._append_log("[!] 선택된 후보 키워드가 없습니다. 마이닝 후 체크박스를 확인하세요.")
            return

        run_test = self.check_regression.get() == 1
        self._append_log(f"[*] 사전 최적화 및 동기화 시작 (반영 대상: {len(selected_candidates)}개, 회귀 테스트: {'포함' if run_test else '생략'})...")
        threading.Thread(target=self._run_sync, args=(selected_candidates, run_test), daemon=True).start()

    def _run_sync(self, selected_candidates: List[GenreCandidate], run_test: bool):
        try:
            result = self.syncer.merge_and_sync(
                candidates=selected_candidates,
                run_regression_test=run_test,
                max_weight_cap=8
            )
            self.after(0, lambda: self._on_sync_completed(result))
        except Exception as e:
            self.after(0, lambda: self._append_log(f"[!] 동기화 중단: {e}"))

    def _on_sync_completed(self, result: SyncResult):
        self._refresh_stats()
        self._reload_keywords_table()
        if result.success:
            msg = (
                f"[✓] 성공적으로 사전을 동기화했습니다!\n"
                f" • 추가된 키워드: {result.added_count}개\n"
                f" • 갱신된 키워드: {result.updated_count}개\n"
                f" • 최종 등록 키워드: {result.total_keywords:,}개\n"
                f" • 회귀 단위 테스트: {'통과 (PASS)' if result.test_passed else '생략'}"
            )
            self._append_log(msg)
            messagebox.showinfo("사전 동기화 완료", msg, parent=self)
        else:
            msg = f"[✗] 동기화 실패: {result.error_message}"
            self._append_log(msg)
            messagebox.showerror("동기화 실패", msg, parent=self)

    # --------------------------------------------------------------------------
    # 탭 3: 특성/팬덤 & 음독 패턴 레퍼런스
    # --------------------------------------------------------------------------
    def _build_tab_reference(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # 상단 서브 세그먼트 버튼 (팬덤 / 특성 태그 / 중국 음독)
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=10, pady=(10, 8), sticky="ew")

        ctk.CTkLabel(
            toolbar, text="참조 범주:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=THEME["text_secondary"]
        ).pack(side="left", padx=(0, 10))

        self.ref_category = ctk.CTkSegmentedButton(
            toolbar,
            values=["패러디 팬덤 매핑", "핵심 특성 태그 (Trait)", "중국어 음독 접두사 (CJK)"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            selected_color=THEME["accent_blue"],
            selected_hover_color=THEME["accent_blue_hover"],
            command=lambda _: self._load_reference_data()
        )
        self.ref_category.set("패러디 팬덤 매핑")
        self.ref_category.pack(side="left", fill="x", expand=True)

        # 레퍼런스 테이블
        tree_container = ctk.CTkFrame(parent, fg_color=THEME["table_bg"], corner_radius=6)
        tree_container.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        ref_columns = ("col1", "col2", "col3")
        self.tree_ref = ttk.Treeview(
            tree_container,
            columns=ref_columns,
            show="headings",
            style="Dict.Treeview"
        )
        self.tree_ref.heading("col1", text="항목 / 패턴")
        self.tree_ref.heading("col2", text="정규화 결과 / 대표명")
        self.tree_ref.heading("col3", text="상세 설명 / 인식 어휘")

        self.tree_ref.column("col1", width=220)
        self.tree_ref.column("col2", width=180)
        self.tree_ref.column("col3", width=420)

        ref_y_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_ref.yview)
        ref_x_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree_ref.xview)
        self.tree_ref.configure(yscrollcommand=ref_y_scroll.set, xscrollcommand=ref_x_scroll.set)

        self.tree_ref.grid(row=0, column=0, sticky="nsew")
        ref_y_scroll.grid(row=0, column=1, sticky="ns")
        ref_x_scroll.grid(row=1, column=0, sticky="ew")

        self._load_reference_data()

    def _load_reference_data(self):
        cat = self.ref_category.get()
        for item in self.tree_ref.get_children():
            self.tree_ref.delete(item)

        if cat == "패러디 팬덤 매핑":
            self.tree_ref.heading("col1", text="인식 키워드/변형")
            self.tree_ref.heading("col2", text="표준 팬덤명")
            self.tree_ref.heading("col3", text="출처 및 비고")
            # PARODY_FANDOM_MAP 역정렬
            for raw_kw, norm_fandom in sorted(PARODY_FANDOM_MAP.items(), key=lambda x: (x[1], x[0])):
                self.tree_ref.insert("", "end", values=(raw_kw, norm_fandom, f"#{norm_fandom} 또는 [{norm_fandom}패러디] 태그 정규화"))

        elif cat == "핵심 특성 태그 (Trait)":
            self.tree_ref.heading("col1", text="특성 태그 (Trait)")
            self.tree_ref.heading("col2", text="분류 체계")
            self.tree_ref.heading("col3", text="매칭 정규식 패턴")
            for trait_name, patterns in TRAIT_PATTERNS:
                self.tree_ref.insert("", "end", values=(trait_name, "다중 서브장르/소재", ", ".join(patterns[:3]) + ("..." if len(patterns) > 3 else "")))

        elif cat == "중국어 음독 접두사 (CJK)":
            self.tree_ref.heading("col1", text="음독/직역 접두사")
            self.tree_ref.heading("col2", text="원문 CJK 한자")
            self.tree_ref.heading("col3", text="한국어 번역 의미")
            for regex_pat, desc in ChinesePhoneticAnalyzer.PREFIX_PATTERNS:
                # desc format: "이신몰상/아진몰상(我真没想: 내가 진짜 ~할 생각은 없었는데)"
                cjk_part = ""
                mean_part = desc
                if "(" in desc and ")" in desc:
                    inner = desc[desc.find("(")+1:desc.rfind(")")]
                    if ":" in inner:
                        cjk_part, mean_part = inner.split(":", 1)
                    else:
                        cjk_part = inner
                clean_pat = regex_pat.replace("^(?:", "").replace(")", "").replace("|", ", ")
                self.tree_ref.insert("", "end", values=(clean_pat, cjk_part.strip(), mean_part.strip()))

    # --------------------------------------------------------------------------
    # 하단 섹션: 실시간 콘솔 로그 & 닫기
    # --------------------------------------------------------------------------
    def _create_bottom_section(self):
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(
            bottom_frame,
            height=70,
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11),
            fg_color=THEME["bg_input"],
            text_color=THEME["text_secondary"]
        )
        self.log_text.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._append_log("준비 완료: 등록된 1,400+ 키워드를 조회하거나 캐시 마이닝을 실행할 수 있습니다.")

        btn_bar = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        btn_bar.grid(row=1, column=0, sticky="ew")

        close_btn = ctk.CTkButton(
            btn_bar, text="닫기", width=100, height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=THEME["accent_gray"], hover_color=THEME["accent_gray_hover"],
            command=self.destroy
        )
        close_btn.pack(side="right")

    def _append_log(self, text: str):
        now_str = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{now_str}] {text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _refresh_stats(self):
        dict_stats = self.syncer.get_statistics()
        cache_entries = self.miner.load_cache_entries()

        total = dict_stats.get("total", 0)
        version = dict_stats.get("version", "1.6.0")
        last_updated = dict_stats.get("last_updated", "-")
        genre_count = len(dict_stats.get("genres", {}))

        self.card_total_kw.configure(text=f"{total:,}개")
        self.card_version.configure(text=f"v{version} ({last_updated})")
        self.card_genres.configure(text=f"{genre_count}개 장르")
        self.card_cache.configure(text=f"{len(cache_entries):,}건 / {len(self.candidates)}개")


def show_genre_dictionary_dialog(parent) -> GenreDictionaryDialog:
    """장르 사전 관리 다이얼로그 호출 헬퍼"""
    return GenreDictionaryDialog(parent)
