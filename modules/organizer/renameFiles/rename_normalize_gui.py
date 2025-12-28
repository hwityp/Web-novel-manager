#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파일명 정규화 도구 - GUI 프로그램

한국 웹소설/라이트노벨 파일명을 표준화된 형식으로 변환하는 GUI 애플리케이션입니다.

주요 기능:
    - 폴더 선택 및 파일 자동 로드
    - 정규화 결과 실시간 미리보기
    - 컬럼 클릭으로 정렬 (오름차순/내림차순)
    - 개별 파일명 편집 (더블클릭)
    - 체크박스로 선택적 변환
    - 사용자 확인 필요 항목 표시 (노란색)
    - 매핑 파일 저장 (변환 내역 기록)
    - 안전한 파일명 변경 (중복 처리, 확인 다이얼로그)

사용 방법:
    1. "폴더 선택" 버튼으로 대상 폴더 선택
    2. 자동 로드된 파일 목록 확인
    3. 더블클릭으로 개별 수정 (선택사항)
    4. "파일명 변경 실행" 버튼으로 실행

단축키:
    - 더블클릭: 파일명 편집
    - 스페이스바: 체크 토글
    - 컬럼 헤더 클릭: 정렬

버전: 1.1.0
작성일: 2025-02-10
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import csv
from pathlib import Path
from typing import Tuple, Optional, List

# ============================================================================
# 정규화 로직 Import
# ============================================================================

# rename_normalize.py의 정규화 로직을 import
try:
    from rename_normalize import (
        normalize_line_without_genre_inference,  # GUI 탭 2 (정규화)용
        infer_genre_from_filename  # GUI 탭 1 (장르 추가)용
    )
except ImportError:
    # import 실패시 기본 정규화 함수 사용
    def normalize_line_without_genre_inference(filename: str) -> Optional[str]:
        """
        기본 정규화 함수 (fallback)
        
        rename_normalize.py를 찾을 수 없을 때 사용되는 간단한 정규화
        """
        name = filename.strip()
        name = re.sub(r'[_+]', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        return name if name else None
    
    def infer_genre_from_filename(filename: str, return_confidence: bool = False):
        """
        기본 장르 추론 함수 (fallback)
        """
        return (None, 'low') if return_confidence else None


# ============================================================================
# 메인 애플리케이션 클래스
# ============================================================================

class FileRenameApp:
    """
    파일명 정규화 GUI 애플리케이션
    
    Attributes:
        root: tkinter 루트 윈도우
        folder_path: 선택된 폴더 경로
        file_items: 파일 정보 리스트
            각 항목: [원본경로, 원본파일명, 정규화파일명, 체크여부, 수정된파일명, 확인필요여부]
        sort_column: 현재 정렬 컬럼
        sort_reverse: 정렬 방향 (False: 오름차순, True: 내림차순)
    """
    
    def __init__(self, root):
        """
        애플리케이션 초기화
        
        Args:
            root: tkinter 루트 윈도우
        """
        self.root = root
        self.root.title("📝 파일명 정규화 도구 v1.1")
        self.root.geometry("1500x850")
        
        # 아이콘 설정 (선택사항)
        try:
            # Windows에서 작업 표시줄 아이콘 설정
            import ctypes
            myappid = 'kiro.filenamenormalizer.1.1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass
        
        # 폰트 설정
        self.default_font = ('굴림', 11)
        self.tree_font = ('굴림', 12)
        self.button_font = ('굴림', 12, 'bold')
        self.title_font = ('굴림', 13, 'bold')
        
        # 색상 테마
        self.colors = {
            'primary': '#2196F3',      # 파란색 (주요 버튼)
            'success': '#4CAF50',      # 녹색 (실행 버튼)
            'warning': '#FF9800',      # 주황색 (경고)
            'danger': '#F44336',       # 빨간색 (위험)
            'info': '#00BCD4',         # 청록색 (정보)
            'secondary': '#9E9E9E',    # 회색 (보조)
            'tab1': '#E3F2FD',         # 탭1 배경 (연한 파란색)
            'tab2': '#F3E5F5',         # 탭2 배경 (연한 보라색)
        }
        
        # 다크 모드 설정
        self.dark_mode = False
        self.setup_theme()
        
        # 데이터 저장
        self.folder_path = ""
        # 각 항목: [원본경로, 원본파일명, 정규화파일명, 체크여부, 수정된파일명, 확인필요여부]
        self.file_items = []
        
        # 실행 취소를 위한 히스토리
        self.rename_history = []  # [(old_path, new_path), ...]
        
        # 정렬 상태 저장 (정규화 탭)
        self.sort_column = None
        self.sort_reverse = False
        
        # 정렬 상태 저장 (장르 추가 탭)
        self.genre_sort_column = None
        self.genre_sort_reverse = False
        
        # UI 생성
        self.create_widgets()
    
    def setup_theme(self):
        """
        테마 설정 (라이트/다크 모드)
        """
        style = ttk.Style()
        style.theme_use('clam')  # 더 현대적인 테마 사용
        
        if self.dark_mode:
            # 다크 모드 색상
            self.bg_color = '#1e1e1e'
            self.fg_color = '#e0e0e0'
            self.tree_bg = '#252525'
            self.tree_fg = '#e0e0e0'
            self.tree_select_bg = '#0d47a1'
            self.tree_select_fg = '#ffffff'
            self.button_bg = '#424242'
            self.entry_bg = '#2d2d2d'
            self.entry_fg = '#e0e0e0'
            self.frame_bg = '#1e1e1e'
            
            # 다크 모드 스타일 적용
            self.root.configure(bg=self.bg_color)
            style.configure("TFrame", background=self.bg_color)
            style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=self.default_font)
            style.configure("TButton", 
                          font=self.button_font,
                          background=self.button_bg,
                          foreground=self.fg_color,
                          borderwidth=1,
                          relief='raised')
            style.map("TButton",
                     background=[('active', '#616161'), ('pressed', '#757575')])
            
            style.configure("Treeview", 
                          background=self.tree_bg, 
                          foreground=self.tree_fg, 
                          fieldbackground=self.tree_bg,
                          font=self.tree_font, 
                          rowheight=30,
                          borderwidth=0)
            style.configure("Treeview.Heading", 
                          background='#424242', 
                          foreground=self.fg_color,
                          font=self.title_font,
                          relief='raised',
                          borderwidth=1)
            style.map("Treeview.Heading",
                     background=[('active', '#616161')])
            style.map("Treeview", 
                     background=[('selected', self.tree_select_bg)],
                     foreground=[('selected', self.tree_select_fg)])
        else:
            # 라이트 모드 색상 (더 밝고 현대적)
            self.bg_color = '#fafafa'
            self.fg_color = '#212121'
            self.tree_bg = '#ffffff'
            self.tree_fg = '#212121'
            self.tree_select_bg = '#2196F3'
            self.tree_select_fg = '#ffffff'
            self.button_bg = '#e3f2fd'
            self.entry_bg = '#ffffff'
            self.entry_fg = '#212121'
            self.frame_bg = '#fafafa'
            
            # 라이트 모드 스타일 적용
            self.root.configure(bg=self.bg_color)
            style.configure("TFrame", background=self.bg_color)
            style.configure("TLabel", 
                          background=self.bg_color, 
                          foreground=self.fg_color, 
                          font=self.default_font)
            style.configure("TButton", 
                          font=self.button_font,
                          background=self.button_bg,
                          foreground=self.fg_color,
                          borderwidth=1,
                          relief='raised',
                          padding=6)
            style.map("TButton",
                     background=[('active', '#bbdefb'), ('pressed', '#90caf9')])
            
            # 색상 버튼 스타일
            style.configure("Primary.TButton", background=self.colors['primary'], foreground='white')
            style.configure("Success.TButton", background=self.colors['success'], foreground='white')
            style.configure("Warning.TButton", background=self.colors['warning'], foreground='white')
            style.configure("Danger.TButton", background=self.colors['danger'], foreground='white')
            
            style.configure("Treeview", 
                          background=self.tree_bg, 
                          foreground=self.tree_fg, 
                          fieldbackground=self.tree_bg,
                          font=self.tree_font, 
                          rowheight=32,
                          borderwidth=1,
                          relief='solid')
            style.configure("Treeview.Heading", 
                          background='#e3f2fd', 
                          foreground='#1565c0',
                          font=self.title_font,
                          relief='raised',
                          borderwidth=1)
            style.map("Treeview.Heading",
                     background=[('active', '#bbdefb')])
            style.map("Treeview", 
                     background=[('selected', self.tree_select_bg)],
                     foreground=[('selected', self.tree_select_fg)])
            
            # 노트북 (탭) 스타일
            style.configure("TNotebook", background=self.bg_color, borderwidth=0)
            style.configure("TNotebook.Tab", 
                          font=self.title_font,
                          padding=[20, 10],
                          background='#e0e0e0',
                          foreground='#424242')
            style.map("TNotebook.Tab",
                     background=[('selected', '#2196F3')],
                     foreground=[('selected', 'white')],
                     expand=[('selected', [1, 1, 1, 0])])
    
    def toggle_dark_mode(self):
        """
        다크 모드 토글
        """
        self.dark_mode = not self.dark_mode
        self.setup_theme()
        self.update_tree()
        
        # 다크 모드 버튼 텍스트 업데이트
        if hasattr(self, 'dark_mode_button'):
            self.dark_mode_button.config(text="🌙 다크" if not self.dark_mode else "☀️ 라이트")
        
    def create_widgets(self):
        """
        GUI 위젯 생성 및 배치
        
        구성:
            - 탭 1: 파일명 정규화 (기존 기능)
            - 탭 2: 장르 추가 (장르 추론 및 추가)
        """
        # === 탭 컨트롤 생성 ===
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 탭 1: 파일명 정규화 (선행 작업)
        self.tab_normalize = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_normalize, text="📝 1단계: 파일명 정규화")
        
        # 탭 2: 장르 추가 (후속 작업)
        self.tab_genre = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_genre, text="🎭 2단계: 장르 추가")
        
        # 각 탭 UI 생성
        self.create_normalize_tab()
        self.create_genre_tab()
        
        # === 상태바 (공통) ===
        status_frame = tk.Frame(self.root, bg='#E3F2FD', relief=tk.RAISED, bd=1)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = tk.Label(status_frame, text="📂 폴더를 선택하세요", 
                                     bg='#E3F2FD', fg='#1565C0',
                                     font=self.default_font, anchor=tk.W, padx=10, pady=5)
        self.status_label.pack(fill=tk.X)
    
    def create_normalize_tab(self):
        """
        파일명 정규화 탭 UI 생성 (탭 1 - 선행 작업)
        
        장르 태그가 있는 파일의 파일명을 정규화합니다.
        - 완결 표시 통일 (完, 완 → (완))
        - 범위 정보 정리 (1-536화 → 1-536)
        - 노이즈 제거 (번역 정보, 저자명 등)
        - 외전/후기 정보 추출
        
        장르가 없는 파일은 탭 2에서 장르를 추가할 수 있습니다.
        """
        # === 상단: 폴더 선택 ===
        top_frame = ttk.Frame(self.tab_normalize, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="대상 폴더:", font=self.default_font).pack(side=tk.LEFT, padx=(0, 5))
        
        self.folder_entry = ttk.Entry(top_frame, width=70, state='readonly', font=self.default_font)
        self.folder_entry.pack(side=tk.LEFT, padx=5)
        
        # 버튼들 (색상 적용)
        btn_browse = tk.Button(top_frame, text="📁 폴더 선택", command=self.browse_folder,
                              bg=self.colors['primary'], fg='white', font=self.button_font,
                              relief='raised', bd=2, padx=15, pady=5, cursor='hand2')
        btn_browse.pack(side=tk.LEFT, padx=5)
        
        btn_refresh = tk.Button(top_frame, text="🔄 새로고침", command=self.reload_files,
                               bg=self.colors['info'], fg='white', font=self.button_font,
                               relief='raised', bd=2, padx=15, pady=5, cursor='hand2')
        btn_refresh.pack(side=tk.LEFT, padx=5)
        
        # 다크 모드 버튼
        self.dark_mode_button = tk.Button(top_frame, text="🌙 다크", command=self.toggle_dark_mode,
                                         bg=self.colors['secondary'], fg='white', font=self.button_font,
                                         relief='raised', bd=2, padx=15, pady=5, cursor='hand2')
        self.dark_mode_button.pack(side=tk.RIGHT, padx=5)
        
        # === 중간: 파일 목록 테이블 ===
        table_frame = ttk.Frame(self.tab_normalize, padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 테이블 생성
        columns = ('check', 'original', 'normalized')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', selectmode='browse')
        
        # 헤더 설정 및 정렬 이벤트 바인딩
        self.tree.heading('check', text='선택', command=lambda: self.sort_by_column('check'))
        self.tree.heading('original', text='원본 파일명 ▼', command=lambda: self.sort_by_column('original'))
        self.tree.heading('normalized', text='변경될 파일명', command=lambda: self.sort_by_column('normalized'))
        
        self.tree.column('check', width=60, anchor='center')
        self.tree.column('original', width=500)
        self.tree.column('normalized', width=500)
        
        # 기본 정렬: 원본 파일명 오름차순
        self.sort_column = 'original'
        self.sort_reverse = False
        
        # 스크롤바
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 이벤트 바인딩
        self.tree.bind('<Double-Button-1>', self.on_double_click)
        self.tree.bind('<Button-1>', self.on_single_click)  # 싱글 클릭으로 체크 토글
        self.tree.bind('<space>', self.toggle_check)
        
        # === 하단: 버튼들 ===
        bottom_frame = ttk.Frame(self.tab_normalize, padding="10")
        bottom_frame.pack(fill=tk.X)
        
        # 왼쪽 버튼들
        left_buttons = ttk.Frame(bottom_frame)
        left_buttons.pack(side=tk.LEFT)
        
        tk.Button(left_buttons, text="☑ 전체 선택", command=self.check_all,
                 bg='#E8F5E9', fg='#2E7D32', font=self.button_font,
                 relief='raised', bd=2, padx=10, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(left_buttons, text="☐ 전체 해제", command=self.uncheck_all,
                 bg='#FFEBEE', fg='#C62828', font=self.button_font,
                 relief='raised', bd=2, padx=10, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(left_buttons, text="🔄 선택 반전", command=self.invert_check,
                 bg='#FFF3E0', fg='#E65100', font=self.button_font,
                 relief='raised', bd=2, padx=10, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        
        # 오른쪽 버튼들
        right_buttons = ttk.Frame(bottom_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        tk.Button(right_buttons, text="💾 매핑 저장", command=self.save_csv,
                 bg=self.colors['info'], fg='white', font=self.button_font,
                 relief='raised', bd=2, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        # 실행 취소 버튼
        self.undo_button = tk.Button(right_buttons, text="↶ 실행 취소", command=self.undo_rename,
                                     bg=self.colors['warning'], fg='white', font=self.button_font,
                                     relief='raised', bd=2, padx=15, pady=5, cursor='hand2', state='disabled')
        self.undo_button.pack(side=tk.LEFT, padx=5)
        
        tk.Button(right_buttons, text="✨ 파일명 변경 실행", command=self.execute_rename,
                 bg=self.colors['success'], fg='white', font=self.button_font,
                 relief='raised', bd=2, padx=20, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
    
    def create_genre_tab(self):
        """
        장르 추가 탭 UI 생성 (탭 2 - 후속 작업)
        
        장르 태그가 없는 파일에 [장르] 태그를 추가합니다.
        - 파일명 키워드 분석으로 장르 자동 추론
        - 신뢰도 표시 (high/medium/low)
        - 더블클릭으로 장르 수동 수정 가능
        
        정규화는 탭 1에서 먼저 수행하는 것을 권장합니다.
        """
        # === 상단: 폴더 선택 ===
        top_frame = ttk.Frame(self.tab_genre, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="대상 폴더:", font=self.default_font).pack(side=tk.LEFT, padx=(0, 5))
        
        self.genre_folder_entry = ttk.Entry(top_frame, width=70, state='readonly', font=self.default_font)
        self.genre_folder_entry.pack(side=tk.LEFT, padx=5)
        
        # 버튼들 (색상 적용)
        tk.Button(top_frame, text="📁 폴더 선택", command=self.browse_folder_genre,
                 bg=self.colors['primary'], fg='white', font=self.button_font,
                 relief='raised', bd=2, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="🔄 새로고침", command=self.reload_files_genre,
                 bg=self.colors['info'], fg='white', font=self.button_font,
                 relief='raised', bd=2, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        # 다크 모드 버튼
        tk.Button(top_frame, text="🌙 다크", command=self.toggle_dark_mode,
                 bg=self.colors['secondary'], fg='white', font=self.button_font,
                 relief='raised', bd=2, padx=15, pady=5, cursor='hand2').pack(side=tk.RIGHT, padx=5)
        
        # === 중간: 파일 목록 테이블 ===
        table_frame = ttk.Frame(self.tab_genre, padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 테이블 생성 (복수 선택 가능)
        columns = ('check', 'original', 'genre', 'confidence')
        self.genre_tree = ttk.Treeview(table_frame, columns=columns, show='headings', selectmode='extended')
        
        # 헤더 설정 및 정렬 이벤트 바인딩
        self.genre_tree.heading('check', text='선택', command=lambda: self.sort_genre_by_column('check'))
        self.genre_tree.heading('original', text='파일명 ▼', command=lambda: self.sort_genre_by_column('original'))
        self.genre_tree.heading('genre', text='추론된 장르', command=lambda: self.sort_genre_by_column('genre'))
        self.genre_tree.heading('confidence', text='신뢰도', command=lambda: self.sort_genre_by_column('confidence'))
        
        self.genre_tree.column('check', width=60, anchor='center')
        self.genre_tree.column('original', width=500)
        self.genre_tree.column('genre', width=150, anchor='center')
        self.genre_tree.column('confidence', width=100, anchor='center')
        
        # 스크롤바
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.genre_tree.yview)
        self.genre_tree.configure(yscrollcommand=vsb.set)
        
        self.genre_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 이벤트 바인딩
        self.genre_tree.bind('<Double-Button-1>', self.on_double_click_genre)
        self.genre_tree.bind('<Button-1>', self.on_single_click_genre)  # 싱글 클릭으로 체크 토글
        
        # === 하단: 버튼들 ===
        bottom_frame = ttk.Frame(self.tab_genre, padding="10")
        bottom_frame.pack(fill=tk.X)
        
        # 왼쪽 버튼들
        left_buttons = ttk.Frame(bottom_frame)
        left_buttons.pack(side=tk.LEFT)
        
        tk.Button(left_buttons, text="☑ 전체 선택", command=self.check_all_genre,
                 bg='#E8F5E9', fg='#2E7D32', font=self.button_font,
                 relief='raised', bd=2, padx=10, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(left_buttons, text="☐ 전체 해제", command=self.uncheck_all_genre,
                 bg='#FFEBEE', fg='#C62828', font=self.button_font,
                 relief='raised', bd=2, padx=10, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(left_buttons, text="🔄 선택 반전", command=self.invert_check_genre,
                 bg='#FFF3E0', fg='#E65100', font=self.button_font,
                 relief='raised', bd=2, padx=10, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        
        # 중간 버튼들
        middle_buttons = ttk.Frame(bottom_frame)
        middle_buttons.pack(side=tk.LEFT, padx=20)
        
        tk.Button(middle_buttons, text="✏️ 선택 항목 장르 수정", command=self.edit_selected_genres,
                 bg=self.colors['warning'], fg='white', font=self.button_font,
                 relief='raised', bd=2, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        
        # 오른쪽 버튼들
        right_buttons = ttk.Frame(bottom_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        tk.Button(right_buttons, text="💾 장르 목록 저장", command=self.save_genre_list,
                 bg=self.colors['info'], fg='white', font=self.button_font,
                 relief='raised', bd=2, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        tk.Button(right_buttons, text="🎭 장르 추가 실행", command=self.execute_add_genre,
                 bg=self.colors['success'], fg='white', font=self.button_font,
                 relief='raised', bd=2, padx=20, pady=8, cursor='hand2').pack(side=tk.LEFT, padx=5)
        
        # 장르 파일 목록 저장
        self.genre_file_items = []
        self.genre_folder_path = ""
    
    # ========== 장르 추가 탭 함수들 ==========
    
    def browse_folder_genre(self):
        """장르 추가 탭: 폴더 선택"""
        folder = filedialog.askdirectory(title="장르를 추가할 폴더 선택")
        if folder:
            self.genre_folder_path = folder
            self.genre_folder_entry.config(state='normal')
            self.genre_folder_entry.delete(0, tk.END)
            self.genre_folder_entry.insert(0, folder)
            self.genre_folder_entry.config(state='readonly')
            self.load_files_genre()
    
    def load_files_genre(self):
        """장르 추가 탭: 파일 로드 및 장르 추론"""
        if not self.genre_folder_path or not os.path.isdir(self.genre_folder_path):
            return
        
        self.genre_file_items.clear()
        
        # 지원 확장자
        supported_exts = ('.txt', '.epub', '.zip', '.zipx', '.7z', '.rar')
        
        try:
            # 장르 추론 함수 import
            try:
                from rename_normalize import infer_genre_from_filename
            except ImportError:
                infer_genre_from_filename = lambda f, r: (None, 'low')
            
            files = [f for f in os.listdir(self.genre_folder_path) 
                    if os.path.isfile(os.path.join(self.genre_folder_path, f)) 
                    and f.lower().endswith(supported_exts)]
            
            for filename in sorted(files):
                full_path = os.path.join(self.genre_folder_path, filename)
                
                # 이미 장르가 있는지 확인 ([ 또는 ( 로 시작)
                has_genre = filename.startswith('[') or filename.startswith('(')
                
                # 장르 추론
                try:
                    genre, confidence = infer_genre_from_filename(filename, return_confidence=True)
                except:
                    genre, confidence = None, 'low'
                
                # 장르가 없는 파일만 추가 (추론 성공 여부 무관)
                if not has_genre:
                    # 장르가 추론되지 않았으면 기본값 설정
                    if not genre:
                        genre = None
                        confidence = 'low'
                    
                    # 장르가 추론된 경우만 체크 (high/medium 신뢰도)
                    should_check = (genre is not None and confidence in ['high', 'medium'])
                    
                    self.genre_file_items.append([
                        full_path,      # 0: 원본 전체 경로
                        filename,       # 1: 원본 파일명
                        genre,          # 2: 추론된 장르 (None 가능)
                        confidence,     # 3: 신뢰도 (high/medium/low)
                        should_check    # 4: 체크 여부 (장르 추론 성공 시만 True)
                    ])
                    # print(f"[DEBUG] 장르 탭 추가: {filename[:30]}... → {genre}")
            
            # 기본 정렬: 체크된 항목 먼저, 그 다음 신뢰도 순, 마지막으로 파일명 오름차순
            self.genre_sort_column = 'check'
            self.genre_sort_reverse = False
            confidence_order = {'high': 0, 'medium': 1, 'low': 2}
            self.genre_file_items.sort(key=lambda x: (not x[4], confidence_order.get(x[3], 3), x[1].lower()))
            
            self.update_genre_tree()
            self.update_genre_sort_indicators()
            
            # 체크된 파일 수 계산
            checked_count = sum(1 for item in self.genre_file_items if item[4])
            self.status_label.config(text=f"🎭 총 {len(self.genre_file_items)}개 파일 (장르 추론 성공: {checked_count}개)")
            
        except Exception as e:
            messagebox.showerror("오류", f"파일 로드 실패:\n{str(e)}")
            self.status_label.config(text="❌ 파일 로드 실패")
    
    def reload_files_genre(self):
        """장르 추가 탭: 새로고침"""
        if self.genre_folder_path:
            self.load_files_genre()
    
    def update_genre_tree(self):
        """장르 추가 탭: 트리뷰 업데이트"""
        # 기존 항목 삭제
        for item in self.genre_tree.get_children():
            self.genre_tree.delete(item)
        
        # 새 항목 추가
        for idx, item in enumerate(self.genre_file_items):
            check_mark = "☑" if item[4] else "☐"
            genre_str = f"[{item[2]}]" if item[2] else "없음"
            confidence_str = {'high': '🟢 확정', 'medium': '🟡 추정', 'low': '🔴 실패'}[item[3]]
            
            item_id = self.genre_tree.insert('', 'end', iid=str(idx), 
                                            values=(check_mark, item[1], genre_str, confidence_str))
            
            # 신뢰도에 따라 색상 표시
            if item[3] == 'medium':
                self.genre_tree.item(item_id, tags=('medium_confidence',))
            elif item[3] == 'low':
                self.genre_tree.item(item_id, tags=('low_confidence',))
        
        # 태그 색상 설정
        self.genre_tree.tag_configure('medium_confidence', background='#FFF9C4')  # 노란색
        self.genre_tree.tag_configure('low_confidence', background='#FFCDD2')     # 빨간색
    
    def on_double_click_genre(self, event):
        """장르 추가 탭: 더블클릭으로 장르 수정 (복수 선택 지원)"""
        selection = self.genre_tree.selection()
        if not selection:
            return
        
        # 복수 선택인 경우
        if len(selection) > 1:
            # 복수 선택 편집 다이얼로그
            dialog = GenreEditDialog(self.root, f"{len(selection)}개 파일 선택됨", None, True)
            self.root.wait_window(dialog.top)
            
            if dialog.result:
                new_genre, checked = dialog.result
                # 선택된 모든 항목에 적용
                for sel in selection:
                    idx = int(sel)
                    self.genre_file_items[idx][2] = new_genre
                    self.genre_file_items[idx][4] = checked
                    self.genre_file_items[idx][3] = 'high'
                self.update_genre_tree()
        else:
            # 단일 선택인 경우
            idx = int(selection[0])
            item = self.genre_file_items[idx]
            
            # 장르 수정 다이얼로그
            dialog = GenreEditDialog(self.root, item[1], item[2], item[4])
            self.root.wait_window(dialog.top)
            
            if dialog.result:
                new_genre, checked = dialog.result
                self.genre_file_items[idx][2] = new_genre
                self.genre_file_items[idx][4] = checked
                # 사용자가 수정했으면 신뢰도를 high로 변경
                self.genre_file_items[idx][3] = 'high'
                self.update_genre_tree()
    
    def on_single_click_genre(self, event):
        """장르 추가 탭: 싱글 클릭으로 체크 토글 (체크 컬럼만)"""
        # 클릭한 위치의 항목과 컬럼 확인
        item = self.genre_tree.identify_row(event.y)
        column = self.genre_tree.identify_column(event.x)
        
        # 체크 컬럼(#1)을 클릭한 경우만 토글
        if column == '#1' and item:
            idx = int(item)
            self.genre_file_items[idx][4] = not self.genre_file_items[idx][4]
            self.update_genre_tree()
            # 클릭 후 선택 상태 유지
            self.genre_tree.selection_set(item)
            return "break"  # 이벤트 전파 중단
    
    def check_all_genre(self):
        """장르 추가 탭: 전체 선택"""
        for item in self.genre_file_items:
            item[4] = True
        self.update_genre_tree()
    
    def uncheck_all_genre(self):
        """장르 추가 탭: 전체 해제"""
        for item in self.genre_file_items:
            item[4] = False
        self.update_genre_tree()
    
    def invert_check_genre(self):
        """장르 추가 탭: 선택 반전"""
        for item in self.genre_file_items:
            item[4] = not item[4]
        self.update_genre_tree()
    
    def sort_genre_by_column(self, column):
        """
        장르 추가 탭: 컬럼 클릭 시 정렬 수행
        
        정렬 규칙:
            - 같은 컬럼 재클릭: 오름차순 ↔ 내림차순 토글
            - 다른 컬럼 클릭: 해당 컬럼 기준 오름차순 정렬
        
        Args:
            column: 정렬할 컬럼 ('check', 'original', 'genre', 'confidence')
        """
        # 같은 컬럼을 다시 클릭하면 역순으로
        if self.genre_sort_column == column:
            self.genre_sort_reverse = not self.genre_sort_reverse
        else:
            self.genre_sort_column = column
            self.genre_sort_reverse = False
        
        # 정렬 수행
        if column == 'check':
            # 체크 여부로 정렬 (체크된 항목 먼저)
            self.genre_file_items.sort(key=lambda x: x[4], reverse=not self.genre_sort_reverse)
        elif column == 'original':
            # 파일명으로 정렬
            self.genre_file_items.sort(key=lambda x: x[1].lower(), reverse=self.genre_sort_reverse)
        elif column == 'genre':
            # 장르로 정렬 (None은 맨 뒤로)
            self.genre_file_items.sort(key=lambda x: (x[2] is None, x[2] or ''), reverse=self.genre_sort_reverse)
        elif column == 'confidence':
            # 신뢰도로 정렬 (high > medium > low)
            confidence_order = {'high': 0, 'medium': 1, 'low': 2}
            self.genre_file_items.sort(key=lambda x: confidence_order.get(x[3], 3), reverse=self.genre_sort_reverse)
        
        # 헤더 업데이트 (정렬 방향 표시)
        self.update_genre_sort_indicators()
        
        # 트리뷰 업데이트
        self.update_genre_tree()
    
    def update_genre_sort_indicators(self):
        """장르 추가 탭: 정렬 방향 표시 업데이트"""
        # 모든 헤더 초기화
        self.genre_tree.heading('check', text='☑ 선택')
        self.genre_tree.heading('original', text='파일명')
        self.genre_tree.heading('genre', text='추론된 장르')
        self.genre_tree.heading('confidence', text='신뢰도')
        
        # 현재 정렬 컬럼에 화살표 추가
        arrow = ' ▼' if not self.genre_sort_reverse else ' ▲'
        
        if self.genre_sort_column == 'check':
            self.genre_tree.heading('check', text='☑ 선택' + arrow)
        elif self.genre_sort_column == 'original':
            self.genre_tree.heading('original', text='파일명' + arrow)
        elif self.genre_sort_column == 'genre':
            self.genre_tree.heading('genre', text='추론된 장르' + arrow)
        elif self.genre_sort_column == 'confidence':
            self.genre_tree.heading('confidence', text='신뢰도' + arrow)
    
    def edit_selected_genres(self):
        """장르 추가 탭: 선택된 항목들의 장르 일괄 수정"""
        selection = self.genre_tree.selection()
        
        if not selection:
            messagebox.showwarning("경고", "수정할 파일을 선택하세요")
            return
        
        # 선택된 항목 수
        count = len(selection)
        
        if count == 1:
            # 단일 선택인 경우 기존 로직 사용
            idx = int(selection[0])
            item = self.genre_file_items[idx]
            dialog = GenreEditDialog(self.root, item[1], item[2], item[4])
            self.root.wait_window(dialog.top)
            
            if dialog.result:
                new_genre, checked = dialog.result
                self.genre_file_items[idx][2] = new_genre
                self.genre_file_items[idx][4] = checked
                self.genre_file_items[idx][3] = 'high'
                self.update_genre_tree()
        else:
            # 복수 선택인 경우
            dialog = GenreEditDialog(self.root, f"{count}개 파일 선택됨", None, True)
            self.root.wait_window(dialog.top)
            
            if dialog.result:
                new_genre, checked = dialog.result
                # 선택된 모든 항목에 적용
                for sel in selection:
                    idx = int(sel)
                    self.genre_file_items[idx][2] = new_genre
                    self.genre_file_items[idx][4] = checked
                    self.genre_file_items[idx][3] = 'high'
                self.update_genre_tree()
                messagebox.showinfo("완료", f"{count}개 파일의 장르가 [{new_genre}]로 변경되었습니다")
    
    def execute_add_genre(self):
        """장르 추가 탭: 장르 추가 실행"""
        checked_items = [item for item in self.genre_file_items if item[4]]
        
        if not checked_items:
            messagebox.showwarning("경고", "선택된 파일이 없습니다")
            return
        
        # 확인 다이얼로그
        msg = f"{len(checked_items)}개 파일에 장르를 추가하시겠습니까?"
        if not messagebox.askyesno("확인", msg):
            return
        
        success_count = 0
        fail_count = 0
        fail_list = []
        
        for item in checked_items:
            old_path = item[0]
            old_name = item[1]
            genre = item[2]
            
            # 새 파일명 생성
            new_name = f"[{genre}] {old_name}"
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            
            try:
                # 파일명 변경
                os.rename(old_path, new_path)
                success_count += 1
            except Exception as e:
                fail_count += 1
                fail_list.append(f"{old_name}: {str(e)}")
        
        # 결과 메시지
        result_msg = f"완료!\n성공: {success_count}개\n실패: {fail_count}개"
        if fail_list:
            result_msg += "\n\n실패 목록:\n" + "\n".join(fail_list[:10])
            if len(fail_list) > 10:
                result_msg += f"\n... 외 {len(fail_list)-10}개"
        
        messagebox.showinfo("결과", result_msg)
        
        # 새로고침
        self.reload_files_genre()
        self.status_label.config(text=f"✅ 장르 추가 완료: 성공 {success_count}개, 실패 {fail_count}개")
    
    def save_genre_list(self):
        """장르 추가 탭: 장르 목록을 genre_list.txt로 저장 (현재 정렬 순서 유지)"""
        if not self.genre_file_items:
            messagebox.showwarning("경고", "저장할 데이터가 없습니다")
            return
        
        # 기본 파일명 설정
        default_filename = "genre_list.txt"
        if self.genre_folder_path:
            default_filename = os.path.join(self.genre_folder_path, "genre_list.txt")
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
            initialfile=default_filename
        )
        
        if not filename:
            return
        
        try:
            # 정렬 정보 표시
            sort_info = ""
            if self.genre_sort_column:
                column_names = {
                    'check': '선택 상태',
                    'original': '파일명',
                    'genre': '장르',
                    'confidence': '신뢰도'
                }
                sort_direction = '내림차순' if self.genre_sort_reverse else '오름차순'
                sort_info = f" (정렬: {column_names.get(self.genre_sort_column, '파일명')} {sort_direction})"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"장르 추가 목록{sort_info}\n")
                f.write("=" * 80 + "\n\n")
                
                # 현재 정렬된 순서대로 저장 (self.genre_file_items는 이미 정렬되어 있음)
                for item in self.genre_file_items:
                    original_name = item[1]
                    genre = item[2]
                    confidence = item[3]
                    checked = item[4]
                    
                    # 체크 상태 표시
                    check_mark = "[✓]" if checked else "[ ]"
                    
                    # 신뢰도 표시
                    confidence_str = {'high': '🟢 확정', 'medium': '🟡 추정', 'low': '🔴 실패'}[confidence]
                    
                    # 장르 표시
                    genre_str = f"[{genre}]" if genre else "[없음]"
                    
                    f.write(f"{check_mark} {original_name}\n")
                    f.write(f"    장르: {genre_str} (신뢰도: {confidence_str})\n")
                    f.write(f"    변경 후: {genre_str} {original_name}\n")
                    f.write("-" * 80 + "\n\n")
                
                # 통계 정보
                total = len(self.genre_file_items)
                checked_count = sum(1 for item in self.genre_file_items if item[4])
                high_conf = sum(1 for item in self.genre_file_items if item[3] == 'high')
                medium_conf = sum(1 for item in self.genre_file_items if item[3] == 'medium')
                low_conf = sum(1 for item in self.genre_file_items if item[3] == 'low')
                
                f.write("=" * 80 + "\n")
                f.write("통계 정보\n")
                f.write("=" * 80 + "\n")
                f.write(f"총 파일 수: {total}개\n")
                f.write(f"선택된 파일: {checked_count}개\n")
                f.write(f"신뢰도 - 확정: {high_conf}개, 추정: {medium_conf}개, 실패: {low_conf}개\n")
            
            messagebox.showinfo("완료", f"장르 목록 저장 완료:\n{filename}")
            self.status_label.config(text=f"💾 장르 목록 저장 완료: {filename}")
            
        except Exception as e:
            messagebox.showerror("오류", f"파일 저장 실패:\n{str(e)}")
            self.status_label.config(text="❌ 장르 목록 저장 실패")
        
    def browse_folder(self):
        """
        폴더 선택 다이얼로그 표시 및 파일 로드
        
        사용자가 폴더를 선택하면 해당 폴더의 파일들을 자동으로 로드합니다.
        """
        folder = filedialog.askdirectory(title="파일명을 정규화할 폴더 선택")
        if folder:
            self.folder_path = folder
            self.folder_entry.config(state='normal')
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder)
            self.folder_entry.config(state='readonly')
            self.load_files()
            
    def load_files(self):
        """
        폴더에서 파일 목록을 읽어와 정규화 (탭 2 - 정규화 전용)
        
        지원 확장자: .txt, .epub, .zip, .zipx, .7z, .rar
        정규화가 필요한 파일(원본과 다른 경우)만 목록에 추가됩니다.
        
        주의: 장르 자동 추론 기능은 제거되었습니다.
        장르는 탭 1에서 이미 추가되었다고 가정합니다.
        """
        # print(f"[DEBUG] load_files 호출됨. folder_path={self.folder_path}")
        
        if not self.folder_path or not os.path.isdir(self.folder_path):
            # print(f"[DEBUG] 폴더 경로 없음 또는 유효하지 않음")
            return
            
        self.file_items.clear()
        # print(f"[DEBUG] file_items 초기화됨")
        
        # 지원 확장자
        supported_exts = ('.txt', '.epub', '.zip', '.zipx', '.7z', '.rar')
        
        try:
            files = [f for f in os.listdir(self.folder_path) 
                    if os.path.isfile(os.path.join(self.folder_path, f)) 
                    and f.lower().endswith(supported_exts)]
            
            for filename in sorted(files):
                full_path = os.path.join(self.folder_path, filename)
                
                # 장르 추론 없이 정규화만 수행
                normalized = normalize_line_without_genre_inference(filename)
                
                # 정규화 결과가 있으면 추가 (원본과 같아도 표시)
                if normalized:
                    # 원본과 다른 경우만 체크 상태로 설정
                    needs_change = (normalized != filename)
                    
                    self.file_items.append([
                        full_path,      # 0: 원본 전체 경로
                        filename,       # 1: 원본 파일명
                        normalized,     # 2: 정규화된 파일명
                        needs_change,   # 3: 체크 여부 (변경 필요한 경우만 True)
                        normalized,     # 4: 사용자가 수정한 파일명
                        False,          # 5: 사용자 확인 필요 여부 (항상 False)
                        'high'          # 6: 신뢰도 (항상 high)
                    ])
            
            # 기본 정렬 적용 (체크된 항목 먼저, 그 다음 원본 파일명 오름차순)
            self.file_items.sort(key=lambda x: (not x[3], x[1].lower()))
            
            # 정렬 상태 설정 (체크 컬럼 내림차순)
            self.sort_column = 'check'
            self.sort_reverse = False
            
            # print(f"[DEBUG] file_items 개수: {len(self.file_items)}")
            
            self.update_tree()
            self.update_sort_indicators()
            
            # 변경 필요한 파일 수 계산
            needs_change_count = sum(1 for item in self.file_items if item[3])
            self.status_label.config(text=f"📝 총 {len(self.file_items)}개 파일 (변경 필요: {needs_change_count}개)")
            
            # print(f"[DEBUG] update_tree 완료")
            
        except Exception as e:
            messagebox.showerror("오류", f"파일 로드 실패:\n{str(e)}")
            self.status_label.config(text="❌ 파일 로드 실패")
            
    def reload_files(self):
        """현재 폴더 새로고침"""
        if self.folder_path:
            self.load_files()
            
    def update_tree(self):
        """트리뷰 업데이트 (정규화 탭)"""
        # 기존 항목 삭제
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # 새 항목 추가
        for idx, item in enumerate(self.file_items):
            check_mark = "☑" if item[3] else "☐"
            
            # 정규화 탭에서는 색상 표시 없음 (장르 추론 안 함)
            self.tree.insert('', 'end', iid=str(idx), 
                           values=(check_mark, item[1], item[4]))
                           
    def on_double_click(self, event):
        """더블클릭시 편집 다이얼로그"""
        selection = self.tree.selection()
        if not selection:
            return
            
        idx = int(selection[0])
        item = self.file_items[idx]
        
        # 편집 다이얼로그 표시
        dialog = EditDialog(self.root, item[1], item[4], item[3])
        self.root.wait_window(dialog.top)
        
        if dialog.result:
            new_name, checked = dialog.result
            self.file_items[idx][3] = checked
            self.file_items[idx][4] = new_name
            # 사용자가 수정했으면 확인 필요 플래그 제거
            if len(self.file_items[idx]) > 5:
                self.file_items[idx][5] = False
            self.update_tree()
            
    def on_single_click(self, event):
        """싱글 클릭으로 체크 토글 (체크 컬럼만)"""
        # 클릭한 위치의 항목과 컬럼 확인
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        # 체크 컬럼(#1)을 클릭한 경우만 토글
        if column == '#1' and item:
            idx = int(item)
            self.file_items[idx][3] = not self.file_items[idx][3]
            self.update_tree()
            # 클릭 후 선택 상태 유지
            self.tree.selection_set(item)
            return "break"  # 이벤트 전파 중단
    
    def toggle_check(self, event):
        """스페이스바로 체크 토글"""
        selection = self.tree.selection()
        if selection:
            idx = int(selection[0])
            self.file_items[idx][3] = not self.file_items[idx][3]
            self.update_tree()
            
    def check_all(self):
        """전체 선택"""
        for item in self.file_items:
            item[3] = True
        self.update_tree()
        
    def uncheck_all(self):
        """전체 해제"""
        for item in self.file_items:
            item[3] = False
        self.update_tree()
        
    def invert_check(self):
        """선택 반전"""
        for item in self.file_items:
            item[3] = not item[3]
        self.update_tree()
        
    def sort_by_column(self, column):
        """
        컬럼 클릭 시 정렬 수행
        
        정렬 규칙:
            - 같은 컬럼 재클릭: 오름차순 ↔ 내림차순 토글
            - 다른 컬럼 클릭: 해당 컬럼 기준 오름차순 정렬
        
        Args:
            column: 정렬할 컬럼 ('check', 'original', 'normalized')
        """
        # 같은 컬럼을 다시 클릭하면 역순으로
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        # 정렬 수행
        if column == 'check':
            # 체크 여부로 정렬 (체크된 항목 먼저)
            self.file_items.sort(key=lambda x: x[3], reverse=not self.sort_reverse)
        elif column == 'original':
            # 원본 파일명으로 정렬
            self.file_items.sort(key=lambda x: x[1].lower(), reverse=self.sort_reverse)
        elif column == 'normalized':
            # 정규화된 파일명으로 정렬
            self.file_items.sort(key=lambda x: x[4].lower(), reverse=self.sort_reverse)
        
        # 헤더 업데이트 (정렬 방향 표시)
        self.update_sort_indicators()
        
        # 트리뷰 업데이트
        self.update_tree()
        
    def update_sort_indicators(self):
        """정렬 방향 표시 업데이트"""
        # 모든 헤더 초기화
        self.tree.heading('check', text='☑ 선택')
        self.tree.heading('original', text='원본 파일명')
        self.tree.heading('normalized', text='변경될 파일명')
        
        # 현재 정렬 컬럼에 화살표 추가
        arrow = ' ▼' if not self.sort_reverse else ' ▲'
        
        if self.sort_column == 'check':
            self.tree.heading('check', text='☑ 선택' + arrow)
        elif self.sort_column == 'original':
            self.tree.heading('original', text='원본 파일명' + arrow)
        elif self.sort_column == 'normalized':
            self.tree.heading('normalized', text='변경될 파일명' + arrow)
        
    def save_csv(self):
        """매핑 파일로 저장"""
        if not self.file_items:
            messagebox.showwarning("경고", "저장할 데이터가 없습니다")
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("CSV 파일", "*.csv"), ("모든 파일", "*.*")],
            initialfile="rename_mapping.txt"
        )
        
        if not filename:
            return
            
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for item in self.file_items:
                    f.write("=" * 60 + "\n")
                    f.write(f"{item[1]}\n")
                    f.write(f"-> {item[4]}\n")
                    f.write("=" * 60 + "\n\n")
                    
            messagebox.showinfo("완료", f"매핑 파일 저장 완료:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("오류", f"파일 저장 실패:\n{str(e)}")
            
    def execute_rename(self):
        """
        실제 파일명 변경 실행
        
        처리 과정:
            1. 체크된 항목만 필터링
            2. 사용자 확인 다이얼로그 표시
            3. 파일명 변경 실행
            4. 중복 파일명 자동 처리 (번호 추가)
            5. 결과 리포트 표시
            6. 목록 새로고침
        """
        # 체크된 항목만 필터링
        checked_items = [item for item in self.file_items if item[3]]
        
        if not checked_items:
            messagebox.showwarning("경고", "선택된 파일이 없습니다")
            return
            
        # 확인 메시지
        msg = f"{len(checked_items)}개 파일의 이름을 변경하시겠습니까?\n\n"
        msg += "이 작업은 되돌릴 수 없습니다."
        
        if not messagebox.askyesno("확인", msg):
            return
            
        # 파일명 변경 실행
        success_count = 0
        fail_count = 0
        errors = []
        
        # 히스토리 초기화 (새로운 변경 시작)
        self.rename_history.clear()
        
        for item in checked_items:
            old_path = item[0]
            new_name = item[4]
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            
            try:
                # 중복 파일명 처리
                if os.path.exists(new_path) and old_path != new_path:
                    base, ext = os.path.splitext(new_name)
                    counter = 1
                    while os.path.exists(new_path):
                        new_name = f"{base} ({counter}){ext}"
                        new_path = os.path.join(os.path.dirname(old_path), new_name)
                        counter += 1
                        
                os.rename(old_path, new_path)
                success_count += 1
                
                # 히스토리에 저장 (실행 취소용)
                self.rename_history.append((old_path, new_path))
                
            except Exception as e:
                fail_count += 1
                errors.append(f"{item[1]} → {str(e)}")
                
        # 결과 메시지
        result_msg = f"완료: {success_count}개 성공"
        if fail_count > 0:
            result_msg += f", {fail_count}개 실패"
            
        if errors:
            error_text = "\n".join(errors[:5])
            if len(errors) > 5:
                error_text += f"\n... 외 {len(errors)-5}개"
            messagebox.showwarning("변경 완료", f"{result_msg}\n\n실패 목록:\n{error_text}")
        else:
            messagebox.showinfo("완료", result_msg)
            
        # 히스토리에 저장 (성공한 항목만)
        if success_count > 0:
            # 실행 취소 버튼 활성화
            self.undo_button.config(state='normal')
        
        # 목록 새로고침
        self.reload_files()
    
    def undo_rename(self):
        """
        마지막 파일명 변경 실행 취소
        
        히스토리에 저장된 변경 내역을 역순으로 되돌립니다.
        """
        if not self.rename_history:
            messagebox.showinfo("알림", "실행 취소할 내역이 없습니다")
            return
        
        # 확인 다이얼로그
        if not messagebox.askyesno("확인", f"{len(self.rename_history)}개 파일의 이름 변경을 취소하시겠습니까?"):
            return
        
        success_count = 0
        fail_count = 0
        errors = []
        
        # 역순으로 되돌리기
        for old_path, new_path in reversed(self.rename_history):
            try:
                # 새 파일이 존재하는지 확인
                if os.path.exists(new_path):
                    os.rename(new_path, old_path)
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{os.path.basename(new_path)} → 파일을 찾을 수 없음")
            except Exception as e:
                fail_count += 1
                errors.append(f"{os.path.basename(new_path)} → {str(e)}")
        
        # 결과 메시지
        result_msg = f"실행 취소 완료: {success_count}개 성공"
        if fail_count > 0:
            result_msg += f", {fail_count}개 실패"
        
        if errors:
            error_text = "\n".join(errors[:5])
            if len(errors) > 5:
                error_text += f"\n... 외 {len(errors)-5}개"
            messagebox.showwarning("실행 취소 완료", f"{result_msg}\n\n실패 목록:\n{error_text}")
        else:
            messagebox.showinfo("완료", result_msg)
        
        # 히스토리 초기화
        self.rename_history.clear()
        self.undo_button.config(state='disabled')
        
        # 목록 새로고침
        self.reload_files()


# ============================================================================
# 편집 다이얼로그 클래스
# ============================================================================

class EditDialog:
    """
    파일명 편집 다이얼로그
    
    사용자가 개별 파일명을 수정하거나 변환 여부를 선택할 수 있는 다이얼로그입니다.
    
    Attributes:
        result: 사용자 입력 결과 (파일명, 체크 여부) 또는 None
    """
    
    def __init__(self, parent, original_name, current_name, checked):
        """
        다이얼로그 초기화
        
        Args:
            parent: 부모 윈도우
            original_name: 원본 파일명 (읽기 전용)
            current_name: 현재 파일명 (편집 가능)
            checked: 체크 상태
        """
        self.result = None
        
        self.top = tk.Toplevel(parent)
        self.top.title("파일명 편집")
        self.top.geometry("700x180")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        
        # 폰트 설정 (크기 11pt)
        dialog_font = ('굴림', 11)
        bold_font = ('굴림', 11, 'bold')
        
        # 원본 파일명 (읽기 전용)
        ttk.Label(self.top, text="원본 파일명:", font=bold_font).grid(
            row=0, column=0, sticky='w', padx=10, pady=(10, 5))
        ttk.Label(self.top, text=original_name, foreground='gray', font=dialog_font).grid(
            row=0, column=1, sticky='w', padx=10, pady=(10, 5))
        
        # 변경할 파일명 (편집 가능)
        ttk.Label(self.top, text="변경할 파일명:", font=bold_font).grid(
            row=1, column=0, sticky='w', padx=10, pady=5)
        
        self.name_var = tk.StringVar(value=current_name)
        self.name_entry = ttk.Entry(self.top, textvariable=self.name_var, width=70, font=dialog_font)
        self.name_entry.grid(row=1, column=1, sticky='ew', padx=10, pady=5)
        self.name_entry.focus_set()
        self.name_entry.select_range(0, tk.END)
        
        # 체크박스
        self.check_var = tk.BooleanVar(value=checked)
        ttk.Checkbutton(self.top, text="이 파일 변경하기", variable=self.check_var).grid(
            row=2, column=1, sticky='w', padx=10, pady=5)
        
        # 버튼
        btn_frame = ttk.Frame(self.top)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=15)
        
        ttk.Button(btn_frame, text="확인", width=10, command=self.ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="취소", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # 엔터키 바인딩
        self.top.bind('<Return>', lambda e: self.ok())
        self.top.bind('<Escape>', lambda e: self.cancel())
        
        # 그리드 설정
        self.top.columnconfigure(1, weight=1)
        
    def ok(self):
        new_name = self.name_var.get().strip()
        if not new_name:
            messagebox.showwarning("경고", "파일명을 입력하세요", parent=self.top)
            return
            
        self.result = (new_name, self.check_var.get())
        self.top.destroy()
        
    def cancel(self):
        self.top.destroy()


class GenreEditDialog:
    """
    장르 편집 다이얼로그
    
    사용자가 추론된 장르를 수정하거나 선택할 수 있는 다이얼로그입니다.
    
    Attributes:
        result: 사용자 입력 결과 (장르, 체크 여부) 또는 None
    """
    
    def __init__(self, parent, filename, current_genre, checked):
        """
        다이얼로그 초기화
        
        Args:
            parent: 부모 윈도우
            filename: 파일명 (읽기 전용)
            current_genre: 현재 장르 (편집 가능)
            checked: 체크 상태
        """
        self.result = None
        
        self.top = tk.Toplevel(parent)
        self.top.title("장르 편집")
        self.top.geometry("700x200")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        
        # 폰트 설정
        dialog_font = ('굴림', 11)
        bold_font = ('굴림', 11, 'bold')
        
        # 파일명 (읽기 전용)
        ttk.Label(self.top, text="파일명:", font=bold_font).grid(
            row=0, column=0, sticky='w', padx=10, pady=(10, 5))
        ttk.Label(self.top, text=filename, foreground='gray', font=dialog_font).grid(
            row=0, column=1, sticky='w', padx=10, pady=(10, 5))
        
        # 장르 선택 (콤보박스)
        ttk.Label(self.top, text="장르:", font=bold_font).grid(
            row=1, column=0, sticky='w', padx=10, pady=5)
        
        self.genre_var = tk.StringVar(value=current_genre if current_genre else "")
        
        # 장르 목록
        genres = ['판타지', '무협', '현판', '퓨판', '겜판', '로판', '로맨스', 
                 '역사', '선협', 'SF', '스포츠', '언정', '공포', '패러디', 'BL']
        
        self.genre_combo = ttk.Combobox(self.top, textvariable=self.genre_var, 
                                       values=genres, width=20, font=dialog_font)
        self.genre_combo.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        self.genre_combo.focus_set()
        
        # 체크박스
        self.check_var = tk.BooleanVar(value=checked)
        ttk.Checkbutton(self.top, text="이 파일에 장르 추가하기", variable=self.check_var).grid(
            row=2, column=1, sticky='w', padx=10, pady=5)
        
        # 버튼
        btn_frame = ttk.Frame(self.top)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=15)
        
        ttk.Button(btn_frame, text="확인", width=10, command=self.ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="취소", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # 엔터키 바인딩
        self.top.bind('<Return>', lambda e: self.ok())
        self.top.bind('<Escape>', lambda e: self.cancel())
        
        # 그리드 설정
        self.top.columnconfigure(1, weight=1)
    
    def ok(self):
        genre = self.genre_var.get().strip()
        if not genre:
            messagebox.showwarning("경고", "장르를 선택하세요", parent=self.top)
            return
        
        self.result = (genre, self.check_var.get())
        self.top.destroy()
    
    def cancel(self):
        self.top.destroy()


def main():
    root = tk.Tk()
    app = FileRenameApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
