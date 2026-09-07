"""
==============================================================================
파일: gui/genre_dictionary_dialog.py
역할 및 목적:
    중국 웹소설 음독 패턴 분석기 및 통합 장르 키워드 사전의 상태를 시각화하고,
    캐시 데이터(`config/genre_cache.json`)로부터 신규 키워드/음독 쌍을 마이닝하여
    이중 JSON 사전에 원자적 동기화 및 무결성 검증을 수행할 수 있는 GUI 관리 모달 다이얼로그.
주요 구성 요소:
    - GenreDictionaryDialog: 관리 대화상자 클래스
    - show_genre_dictionary_dialog(): 모달 호출 헬퍼 함수
==============================================================================
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from pathlib import Path
from typing import Optional, List, Dict, Any

from core.utils.genre_cache_miner import GenreCacheMiner, GenreCandidate
from core.utils.keyword_syncer import KeywordSyncer, SyncResult

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
    "accent_gray": "#707070",
    "accent_gray_hover": "#808080",
    "status_success": "#4ade80",
    "status_error": "#f87171",
    "table_bg": "#2b2b2b",
    "table_header": "#404040",
    "table_selected": "#4A90D9",
}


class GenreDictionaryDialog(ctk.CTkToplevel):
    """장르 키워드 사전 관리 및 최적화 모달 다이얼로그"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("📚 장르 키워드 사전 및 중국 음독 패턴 관리기")
        self.geometry("960x720")
        self.minsize(880, 640)
        self.configure(fg_color=THEME["bg_main"])

        # 모달 설정
        self.transient(parent)
        self.grab_set()

        # 화면 중앙 배치
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 480
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 360
        self.geometry(f"+{max(50, x)}+{max(50, y)}")

        # 서비스 인스턴스
        self.miner = GenreCacheMiner()
        self.syncer = KeywordSyncer()
        self.candidates: List[GenreCandidate] = []

        # UI 생성 및 데이터 로드
        self._create_widgets()
        self._refresh_stats()

    def _create_widgets(self):
        """다이얼로그 내부 위젯 구성"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # 후보 테이블 영역 확장

        # 1. 헤더 섹션
        self._create_header_section()

        # 2. 통계 요약 카드 섹션
        self._create_stats_cards()

        # 3. 마이닝 & 동기화 제어 바 및 후보군 테이블
        self._create_candidate_table_section()

        # 4. 실시간 로그 및 하단 액션 버튼
        self._create_bottom_section()

    def _create_header_section(self):
        """헤더 영역 생성"""
        header_frame = ctk.CTkFrame(self, fg_color=THEME["bg_card"], corner_radius=10)
        header_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")

        title_label = ctk.CTkLabel(
            header_frame,
            text="📚 장르 사전 최적화 & 중국어 음독 패턴 동기화",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=THEME["text_primary"]
        )
        title_label.pack(anchor="w", padx=15, pady=(12, 4))

        sub_label = ctk.CTkLabel(
            header_frame,
            text="캐시 데이터(config/genre_cache.json)에서 CJK 원문-음독 쌍 및 고빈도 키워드를 자동 마이닝하여 사전에 안전하게 반영합니다.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=THEME["text_muted"]
        )
        sub_label.pack(anchor="w", padx=15, pady=(0, 12))

    def _create_stats_cards(self):
        """통계 요약 카드 4종"""
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")
        for i in range(4):
            stats_frame.grid_columnconfigure(i, weight=1)

        # 1. 총 키워드 수
        self.card_total_kw = self._build_stat_card(stats_frame, 0, "총 등록 키워드", "-", THEME["accent_blue"])
        # 2. 사전 버전
        self.card_version = self._build_stat_card(stats_frame, 1, "사전 버전 / 갱신일", "-", THEME["text_primary"])
        # 3. 축적된 캐시
        self.card_cache = self._build_stat_card(stats_frame, 2, "캐시 축적 데이터", "-", THEME["accent_green"])
        # 4. 발굴된 후보군
        self.card_candidates = self._build_stat_card(stats_frame, 3, "발굴 대기 후보군", "0개", THEME["accent_orange"])

    def _build_stat_card(self, parent, col: int, label: str, value: str, color: str) -> ctk.CTkLabel:
        card = ctk.CTkFrame(parent, fg_color=THEME["bg_card"], corner_radius=10)
        card.grid(row=0, column=col, padx=5, sticky="ew")
        
        lbl = ctk.CTkLabel(
            card, text=label,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_muted"]
        )
        lbl.pack(anchor="w", padx=12, pady=(10, 2))

        val_lbl = ctk.CTkLabel(
            card, text=value,
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=color
        )
        val_lbl.pack(anchor="w", padx=12, pady=(0, 10))
        return val_lbl

    def _create_candidate_table_section(self):
        """후보군 제어 바 및 결과 테이블"""
        table_card = ctk.CTkFrame(self, fg_color=THEME["bg_card"], corner_radius=10)
        table_card.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(1, weight=1)

        # 제어 툴바
        toolbar = ctk.CTkFrame(table_card, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=15, pady=10, sticky="ew")

        btn_mine = ctk.CTkButton(
            toolbar,
            text="🔍 1단계: 캐시 마이닝",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=THEME["accent_blue"],
            hover_color=THEME["accent_blue_hover"],
            width=150, height=36,
            command=self._start_mining_thread
        )
        btn_mine.pack(side="left", padx=(0, 10))

        self.btn_sync = ctk.CTkButton(
            toolbar,
            text="⚡ 2단계: 사전 최적화 & 동기화",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=THEME["accent_green"],
            hover_color=THEME["accent_green_hover"],
            width=200, height=36,
            command=self._start_sync_thread
        )
        self.btn_sync.pack(side="left", padx=(0, 15))

        self.check_regression = ctk.CTkCheckBox(
            toolbar,
            text="동기화 후 자동 회귀 검증(pytest) 수행",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=THEME["text_secondary"]
        )
        self.check_regression.pack(side="left")
        self.check_regression.select()

        # Treeview 스타일 설정
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dict.Treeview",
            background=THEME["table_bg"],
            foreground=THEME["text_primary"],
            fieldbackground=THEME["table_bg"],
            rowheight=30,
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

        # Treeview 컨테이너
        tree_container = ctk.CTkFrame(table_card, fg_color=THEME["table_bg"], corner_radius=6)
        tree_container.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        columns = ("keyword", "genre", "count", "purity", "weight", "source")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Dict.Treeview"
        )

        self.tree.heading("keyword", text="키워드 / 어휘")
        self.tree.heading("genre", text="추천 장르")
        self.tree.heading("count", text="출현 빈도")
        self.tree.heading("purity", text="순도(Purity)")
        self.tree.heading("weight", text="제안 가중치")
        self.tree.heading("source", text="단서 출처 / CJK 원문")

        self.tree.column("keyword", width=180)
        self.tree.column("genre", width=110)
        self.tree.column("count", width=80, anchor="center")
        self.tree.column("purity", width=100, anchor="center")
        self.tree.column("weight", width=90, anchor="center")
        self.tree.column("source", width=220)

        # 스크롤바
        y_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    def _create_bottom_section(self):
        """로그 창 및 하단 닫기 버튼"""
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)

        # 상태 로그 텍스트
        self.log_text = ctk.CTkTextbox(
            bottom_frame,
            height=85,
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11),
            fg_color=THEME["bg_input"],
            text_color=THEME["text_secondary"]
        )
        self.log_text.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._append_log("준비 완료: [1단계: 캐시 마이닝]을 클릭하여 신규 패턴을 탐색하세요.")

        # 버튼들
        btn_bar = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        btn_bar.grid(row=1, column=0, sticky="ew")

        close_btn = ctk.CTkButton(
            btn_bar, text="닫기", width=100, height=34,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=THEME["accent_gray"],
            hover_color=THEME["accent_gray_hover"],
            command=self.destroy
        )
        close_btn.pack(side="right")

    def _append_log(self, text: str):
        """로그 창에 텍스트 추가"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _refresh_stats(self):
        """사전 및 캐시 통계 갱신"""
        dict_stats = self.syncer.get_statistics()
        cache_entries = self.miner.load_cache_entries()

        total = dict_stats.get("total", 0)
        version = dict_stats.get("version", "1.6.0")
        last_updated = dict_stats.get("last_updated", "-")

        self.card_total_kw.configure(text=f"{total:,}개")
        self.card_version.configure(text=f"v{version} ({last_updated})")
        self.card_cache.configure(text=f"{len(cache_entries):,}건")
        self.card_candidates.configure(text=f"{len(self.candidates)}개")

    def _start_mining_thread(self):
        """캐시 마이닝 백그라운드 스레드 실행"""
        self._append_log("[*] 캐시 마이닝 시작 중...")
        threading.Thread(target=self._run_mining, daemon=True).start()

    def _run_mining(self):
        try:
            candidates = self.miner.mine(min_count=1, min_purity=0.6)
            self.candidates = candidates
            self.after(0, self._on_mining_completed)
        except Exception as e:
            self.after(0, lambda: self._append_log(f"[!] 마이닝 오류: {e}"))

    def _on_mining_completed(self):
        """마이닝 완료 시 UI 갱신"""
        self._refresh_stats()
        # 트리뷰 갱신
        for item in self.tree.get_children():
            self.tree.delete(item)

        for c in self.candidates:
            cjk = f"원문: {c.cjk_source}" if c.cjk_source else c.source_type
            self.tree.insert("", "end", values=(
                c.keyword, c.genre, c.count, f"{c.purity:.2f}", c.suggested_weight, cjk
            ))

        self._append_log(f"[✓] 마이닝 완료: 총 {len(self.candidates)}개의 후보 키워드가 추출되었습니다.")

    def _start_sync_thread(self):
        """동기화 백그라운드 스레드 실행"""
        if not self.candidates:
            # 먼저 마이닝하지 않은 경우 즉시 마이닝 후 동기화 진행 유도
            self._append_log("[!] 마이닝된 후보가 없습니다. 먼저 캐시 마이닝을 실행합니다.")
            self._start_mining_thread()
            return

        run_test = self.check_regression.get() == 1
        self._append_log(f"[*] 사전 최적화 및 동기화 시작 (회귀 테스트: {'포함' if run_test else '생략'})...")
        threading.Thread(target=self._run_sync, args=(run_test,), daemon=True).start()

    def _run_sync(self, run_test: bool):
        try:
            result = self.syncer.merge_and_sync(
                candidates=self.candidates,
                run_regression_test=run_test,
                max_weight_cap=8
            )
            self.after(0, lambda: self._on_sync_completed(result))
        except Exception as e:
            self.after(0, lambda: self._append_log(f"[!] 동기화 중단: {e}"))

    def _on_sync_completed(self, result: SyncResult):
        """동기화 완료 UI 갱신"""
        self._refresh_stats()
        if result.success:
            msg = (
                f"[✓] 성공적으로 사전을 동기화했습니다!\n"
                f" - 추가된 키워드: {result.added_count}개\n"
                f" - 갱신된 키워드: {result.updated_count}개\n"
                f" - 최종 등록 키워드: {result.total_keywords}개\n"
                f" - 회귀 단위 테스트: {'통과 (PASS)' if result.test_passed else '생략'}"
            )
            self._append_log(msg)
            messagebox.showinfo("사전 동기화 완료", msg)
        else:
            msg = f"[✗] 동기화 실패: {result.error_message}"
            self._append_log(msg)
            messagebox.showerror("동기화 실패", msg)


def show_genre_dictionary_dialog(parent) -> GenreDictionaryDialog:
    """장르 사전 관리 다이얼로그 호출 헬퍼"""
    return GenreDictionaryDialog(parent)
