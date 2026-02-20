"""
웹소설 장르 분류기 GUI
tkinter 기반 사용자 인터페이스 - 좌우 분할 형태
리디북스 우선 추출 방식 적용 (V3)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import json
import shutil
import sys
from datetime import datetime
from core.version import __version__, __app_name__ as __version_name__, get_full_version as get_full_version_string
from modules.classifier.filename_genre_classifier import FilenameGenreClassifier
import threading


# 로그 파일 설정
class TeeOutput:
    """콘솔과 파일에 동시에 출력"""
    def __init__(self, file_path):
        self.terminal = sys.stdout
        try:
            self.log = open(file_path, 'w', encoding='utf-8')
        except:
            self.log = None
    
    def write(self, message):
        # PyInstaller 환경에서 sys.stdout이 None일 수 있음
        if self.terminal is not None:
            try:
                self.terminal.write(message)
            except:
                pass
        
        if self.log is not None:
            try:
                self.log.write(message)
                self.log.flush()
            except:
                pass
    
    def flush(self):
        if self.terminal is not None:
            try:
                self.terminal.flush()
            except:
                pass
        
        if self.log is not None:
            try:
                self.log.flush()
            except:
                pass
    
    def close(self):
        if self.log is not None:
            try:
                self.log.close()
            except:
                pass


# 로그 파일 경로 (PyInstaller 환경 고려)
def get_log_file_path():
    """로그 파일 경로 가져오기 (PyInstaller 환경 고려)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 실행 파일
        application_path = os.path.dirname(sys.executable)
    else:
        # 일반 Python 스크립트
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(application_path, 'debugging_list.txt')

LOG_FILE = get_log_file_path()

# stdout을 파일과 콘솔에 동시 출력하도록 설정
try:
    tee_output = TeeOutput(LOG_FILE)
    sys.stdout = tee_output
    
    print(f"="*80)
    print(f"웹소설 장르 분류기 실행 시작")
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"로그 파일: {LOG_FILE}")
    print(f"="*80)
    print()
except Exception as e:
    # 로그 설정 실패 시에도 프로그램은 계속 실행
    pass


class GenreClassifierGUI:
    """장르 분류기 GUI"""
    
    def __init__(self, root):
        self.root = root
        self.root.title(f"웹소설 장르 자동 분류기 {get_full_version_string()}")
        self.root.geometry("1800x1100")
        
        # 기본 폰트 크기 설정 (메시지박스 포함)
        import tkinter.font as tkfont
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=13)  # 기본 폰트 크기를 13으로 설정
        
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(size=13)
        
        caption_font = tkfont.nametofont("TkCaptionFont")
        caption_font.configure(size=12)
        
        # 시스템 비프음 비활성화 (messagebox 효과음 제거)
        self.root.bell = lambda: None
        
        # 색상 테마 설정
        self.colors = {
            'primary': '#4A90E2',      # 파란색
            'success': '#5CB85C',      # 초록색
            'warning': '#F0AD4E',      # 주황색
            'danger': '#D9534F',       # 빨간색
            'info': '#5BC0DE',         # 하늘색
            'light_bg': '#F8F9FA',     # 밝은 배경
            'dark_text': '#333333',    # 어두운 텍스트
            'gray': '#6C757D',         # 회색
            'tab_bg': '#E8F4FD',       # 탭 배경색 (연한 파란색)
            'tab_active': '#4A90E2',   # 활성 탭 색상
            'tab_inactive': '#B0BEC5', # 비활성 탭 색상
            'tree_bg': '#FAFBFC',      # 트리뷰 배경색
            'tree_select': '#E3F2FD',  # 트리뷰 선택 색상
            'tree_alt': '#F5F5F5'      # 트리뷰 교대 행 색상
        }
        
        self.classifier = FilenameGenreClassifier()
        self.current_directory = None
        self.results = []
        self.is_processing = False
        self.selected_items = []
        self.files_renamed = False  # 파일명 변경 완료 플래그
        
        self.setup_ui()
        
        # API 키 자동 로드
        self.auto_load_api_keys()
    
    def setup_ui(self):
        """UI 구성 - 좌우 분할"""
        # 상단 타이틀
        title_frame = tk.Frame(self.root, bg=self.colors['primary'], padx=10, pady=15)
        title_frame.pack(fill=tk.X)
        
        tk.Label(title_frame, text=f"웹소설 장르 자동 분류기 {get_full_version_string()}", 
                 font=("맑은 고딕", 20, "bold"), 
                 bg=self.colors['primary'], fg='white').pack()
        tk.Label(title_frame, text="파일명 → 제목 추출 → 장르 판정 (리디북스 > 문피아 > 네이버시리즈) → 파일명 변경", 
                 font=("맑은 고딕", 12), 
                 bg=self.colors['primary'], fg='white').pack()
        
        # 메인 컨테이너 (Grid 레이아웃으로 좌우 비율 고정)
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Grid 설정: 왼쪽(0열) 고정 너비, 오른쪽(1열) 확장
        main_container.grid_columnconfigure(0, weight=0, minsize=350)  # 왼쪽 고정 350px
        main_container.grid_columnconfigure(1, weight=1)  # 오른쪽 확장
        main_container.grid_rowconfigure(0, weight=1)
        
        # 왼쪽 패널 (분류 설정 및 진행) - 고정 너비
        left_panel = ttk.Frame(main_container, padding="5", width=350)
        left_panel.grid(row=0, column=0, sticky='nsew')
        left_panel.grid_propagate(False)  # 크기 고정
        
        # 오른쪽 패널 (결과 및 파일명 변경) - 확장
        right_panel = ttk.Frame(main_container, padding="5")
        right_panel.grid(row=0, column=1, sticky='nsew')
        
        self.setup_left_panel(left_panel)
        self.setup_right_panel(right_panel)
    
    def setup_left_panel(self, parent):
        """왼쪽 패널 구성"""
        # 1. 디렉토리 선택
        dir_frame = ttk.LabelFrame(parent, text="1. 디렉토리 선택", padding="10")
        dir_frame.pack(fill=tk.X, pady=5)
        
        self.dir_label = ttk.Label(dir_frame, text="없음", foreground="gray", wraplength=350)
        self.dir_label.pack(fill=tk.X, pady=5)
        
        dir_btn = tk.Button(dir_frame, text="📁 디렉토리 선택", 
                           command=self.select_directory,
                           font=("맑은 고딕", 11, "bold"), width=18,
                           bg=self.colors['success'], fg='white',
                           relief='raised', bd=2, cursor='hand2')
        dir_btn.pack(pady=5)
        
        # 2. 분류 옵션
        option_frame = ttk.LabelFrame(parent, text="2. 분류 옵션", padding="10")
        option_frame.pack(fill=tk.X, pady=5)
        
        # 네이버 검색 (V3 개선 버전) - 스타일 개선
        naver_outer_frame = tk.Frame(option_frame, bg=self.colors['primary'], relief='solid', bd=2)
        naver_outer_frame.pack(fill=tk.X, pady=5, padx=2)
        
        naver_frame = tk.Frame(naver_outer_frame, bg=self.colors['light_bg'], relief='flat')
        naver_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        self.use_naver_var = tk.BooleanVar(value=True)
        
        # 체크박스 컨테이너 (호버 효과용)
        checkbox_container = tk.Frame(naver_frame, bg=self.colors['light_bg'])
        checkbox_container.pack(fill=tk.X, pady=5, padx=5)
        
        # 커스텀 체크박스 스타일 (버튼 형태)
        def update_naver_button():
            if self.use_naver_var.get():
                naver_check.config(
                    text="✅ 네이버 검색 사용 (V3 - 리디북스 우선)",
                    bg=self.colors['success'],
                    fg='white',
                    relief='raised'
                )
            else:
                naver_check.config(
                    text="☐ 네이버 검색 사용 (V3 - 리디북스 우선)",
                    bg=self.colors['light_bg'],
                    fg=self.colors['dark_text'],
                    relief='sunken'
                )
        
        def toggle_naver_and_update():
            self.toggle_naver_options()
            update_naver_button()
        
        naver_check = tk.Button(checkbox_container, 
                               text="✅ 네이버 검색 사용 (V3 - 리디북스 우선)",
                               command=lambda: [self.use_naver_var.set(not self.use_naver_var.get()), toggle_naver_and_update()],
                               font=("맑은 고딕", 11, "bold"),
                               bg=self.colors['success'],  # 기본값: 체크됨
                               fg='white',
                               relief='raised',
                               bd=2,
                               cursor='hand2',
                               anchor='w',
                               padx=10,
                               pady=5)
        naver_check.pack(fill=tk.X, pady=3, padx=5)
        
        # 초기 상태 설정
        update_naver_button()
        
        info_label1 = tk.Label(naver_frame, text="📊 신뢰도 85-95%, 약 3초/건, 제목 검증 포함", 
                              font=("맑은 고딕", 9), 
                              fg=self.colors['gray'], bg=self.colors['light_bg'])
        info_label1.pack(anchor=tk.W, padx=30)
        
        info_label2 = tk.Label(naver_frame, text="🏆 우선순위: 리디북스 > 노벨피아 > 네이버시리즈", 
                              font=("맑은 고딕", 9), 
                              fg=self.colors['info'], bg=self.colors['light_bg'])
        info_label2.pack(anchor=tk.W, padx=30, pady=(0, 5))
        
        # 네이버 API 옵션 (들여쓰기)
        api_outer_frame = tk.Frame(option_frame, bg=self.colors['warning'], relief='solid', bd=1)
        api_outer_frame.pack(fill=tk.X, padx=20, pady=(5, 0))
        
        api_frame = tk.Frame(api_outer_frame, bg='white', relief='flat')
        api_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # API 키가 있으면 자동으로 API 사용 활성화 (PyInstaller 환경 고려)
        if getattr(sys, 'frozen', False):
            # PyInstaller로 빌드된 실행 파일
            application_path = os.path.dirname(sys.executable)
        else:
            # 일반 Python 스크립트
            application_path = os.path.dirname(os.path.abspath(__file__))
        
        api_config_path = os.path.join(application_path, 'naver_api_config.json')
        api_config_exists = os.path.exists(api_config_path)
        self.use_naver_api_var = tk.BooleanVar(value=api_config_exists)
        
        # API 체크박스 컨테이너
        api_checkbox_container = tk.Frame(api_frame, bg='white')
        api_checkbox_container.pack(fill=tk.X, pady=3, padx=5)
        
        # API 커스텀 체크박스 스타일
        def update_api_button():
            if self.use_naver_api_var.get():
                api_check.config(
                    text="✅ 네이버 검색 API 사용 (안정적, API 키 필요)",
                    bg=self.colors['primary'],
                    fg='white',
                    relief='raised'
                )
            else:
                api_check.config(
                    text="☐ 네이버 검색 API 사용 (안정적, API 키 필요)",
                    bg='white',
                    fg=self.colors['warning'],
                    relief='sunken'
                )
        
        def toggle_api_and_update():
            self.toggle_api_key_entry()
            update_api_button()
        
        api_check = tk.Button(api_checkbox_container,
                             text="☐ 네이버 검색 API 사용 (안정적, API 키 필요)",
                             command=lambda: [self.use_naver_api_var.set(not self.use_naver_api_var.get()), toggle_api_and_update()],
                             font=("맑은 고딕", 11, "bold"),
                             bg='white',  # 기본값: 체크 안됨
                             fg=self.colors['warning'],
                             relief='sunken',
                             bd=2,
                             cursor='hand2',
                             anchor='w',
                             padx=10,
                             pady=5)
        api_check.pack(fill=tk.X, pady=2, padx=5)
        
        # 초기 상태 설정
        update_api_button()
        
        # API 키 입력 프레임
        self.api_key_frame = ttk.Frame(api_frame)
        self.api_key_frame.pack(fill=tk.X, padx=20, pady=(2, 0))
        
        ttk.Label(self.api_key_frame, text="Client ID:", 
                 font=("맑은 고딕", 10)).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.api_client_id_var = tk.StringVar()
        self.api_client_id_entry = ttk.Entry(self.api_key_frame, textvariable=self.api_client_id_var, width=30)
        self.api_client_id_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(self.api_key_frame, text="Client Secret:", 
                 font=("맑은 고딕", 10)).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.api_client_secret_var = tk.StringVar()
        self.api_client_secret_entry = ttk.Entry(self.api_key_frame, textvariable=self.api_client_secret_var, 
                                                  width=30, show="*")
        self.api_client_secret_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # API 키 저장/불러오기 버튼
        api_button_frame = ttk.Frame(self.api_key_frame)
        api_button_frame.grid(row=2, column=0, columnspan=2, pady=5)
        
        save_api_btn = tk.Button(api_button_frame, text="💾 저장", command=self.save_api_keys,
                                font=("맑은 고딕", 9, "bold"), width=8,
                                bg=self.colors['primary'], fg='white',
                                relief='raised', bd=1, cursor='hand2')
        save_api_btn.pack(side=tk.LEFT, padx=2)
        
        load_api_btn = tk.Button(api_button_frame, text="📂 불러오기", command=self.load_api_keys,
                                font=("맑은 고딕", 9, "bold"), width=10,
                                bg=self.colors['info'], fg='white',
                                relief='raised', bd=1, cursor='hand2')
        load_api_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(self.api_key_frame, text="※ API 키는 로컬에 암호화되어 저장됩니다", 
                 font=("맑은 고딕", 9), foreground=self.colors['gray']).grid(row=3, column=0, columnspan=2, pady=2)
        
        # 초기 상태: API 키 입력 비활성화
        self.toggle_api_key_entry()
        
        ttk.Separator(option_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        # 확장자 - 1줄로 배치
        ext_label = ttk.Label(option_frame, text="파일 확장자:", 
                             font=("맑은 고딕", 11, "bold"))
        ext_label.pack(anchor=tk.W, pady=(2, 5))
        
        # 확장자 체크박스 프레임
        ext_row = ttk.Frame(option_frame)
        ext_row.pack(fill=tk.X, padx=10)
        
        self.ext_vars = {}
        extensions = ['.txt', '.epub', '.pdf', '.mobi']
        
        for ext in extensions:
            var = tk.BooleanVar(value=True)
            self.ext_vars[ext] = var
            ttk.Checkbutton(ext_row, text=ext, variable=var).pack(side=tk.LEFT, padx=5, pady=2)
        
        # 3. 실행 버튼 (1줄 배치)
        button_frame = ttk.LabelFrame(parent, text="3. 실행", padding="10")
        button_frame.pack(fill=tk.X, pady=5)
        
        # 버튼 컨테이너 (Grid 레이아웃)
        button_container = ttk.Frame(button_frame)
        button_container.pack(fill=tk.X)
        
        # Grid 설정: 4개 버튼을 동일한 너비로
        for i in range(4):
            button_container.grid_columnconfigure(i, weight=1, uniform="button")
        
        # 시작 버튼 (초록색)
        start_style_frame = tk.Frame(button_container, bg=self.colors['success'], padx=1, pady=1)
        start_style_frame.grid(row=0, column=0, sticky='ew', padx=2)
        
        self.start_button = tk.Button(start_style_frame, text="▶ 시작", 
                                       command=self.start_classification,
                                       bg=self.colors['success'], fg='white',
                                       font=("맑은 고딕", 11, "bold"),
                                       relief=tk.FLAT, cursor='hand2')
        self.start_button.pack(fill=tk.BOTH, expand=True)
        
        # 중지 버튼 (빨간색)
        stop_style_frame = tk.Frame(button_container, bg=self.colors['danger'], padx=1, pady=1)
        stop_style_frame.grid(row=0, column=1, sticky='ew', padx=2)
        
        self.stop_button = tk.Button(stop_style_frame, text="■ 중지", 
                                      command=self.stop_classification,
                                      bg=self.colors['danger'], fg='white',
                                      font=("맑은 고딕", 11, "bold"),
                                      relief=tk.FLAT, cursor='hand2',
                                      state=tk.DISABLED)
        self.stop_button.pack(fill=tk.BOTH, expand=True)
        
        # 결과 저장 버튼
        save_results_btn = tk.Button(button_container, text="💾 저장", command=self.save_results,
                                    font=("맑은 고딕", 10, "bold"),
                                    bg=self.colors['success'], fg='white',
                                    relief='raised', bd=2, cursor='hand2')
        save_results_btn.grid(row=0, column=2, sticky='ew', padx=2)
        
        # 초기화 버튼
        ttk.Button(button_container, text="🔄 초기화", 
                  command=self.clear_results).grid(row=0, column=3, sticky='ew', padx=2)
        
        # 4. 진행 상황
        progress_frame = ttk.LabelFrame(parent, text="4. 진행 상황", padding="10")
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="대기 중...", wraplength=350)
        self.progress_label.pack(pady=2)
        
        # 진행 상태바 스타일 설정
        style = ttk.Style()
        style.configure('Custom.Horizontal.TProgressbar',
                       background=self.colors['success'],  # 진행 부분 색상 (초록색)
                       troughcolor=self.colors['light_bg'],  # 배경 색상
                       borderwidth=1,
                       lightcolor=self.colors['success'],
                       darkcolor=self.colors['success'])
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', 
                                           style='Custom.Horizontal.TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # 5. 통계
        stats_frame = ttk.LabelFrame(parent, text="5. 통계", padding="10")
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 스크롤바 추가
        stats_scroll_frame = ttk.Frame(stats_frame)
        stats_scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        stats_scrollbar = ttk.Scrollbar(stats_scroll_frame)
        stats_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.stats_text = tk.Text(stats_scroll_frame, height=12, wrap=tk.WORD, 
                                  font=("맑은 고딕", 11),
                                  bg=self.colors['light_bg'],
                                  yscrollcommand=stats_scrollbar.set)
        self.stats_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        stats_scrollbar.config(command=self.stats_text.yview)
        
        self.stats_text.insert('1.0', "통계 정보가 여기에 표시됩니다.")
        self.stats_text.config(state=tk.DISABLED)
    
    def setup_right_panel(self, parent):
        """오른쪽 패널 구성"""
        # 탭 스타일 설정
        style = ttk.Style()
        
        # 탭 스타일 커스터마이징
        style.theme_use('clam')
        style.configure('Custom.TNotebook', 
                       background=self.colors['light_bg'],
                       borderwidth=2,
                       relief='solid')
        
        style.configure('Custom.TNotebook.Tab',
                       background=self.colors['tab_inactive'],
                       foreground=self.colors['dark_text'],
                       padding=[20, 10],
                       font=('맑은 고딕', 12, 'bold'))
        
        style.map('Custom.TNotebook.Tab',
                 background=[('selected', self.colors['tab_active']),
                           ('active', self.colors['info'])],
                 foreground=[('selected', 'white'),
                           ('active', 'white')])
        
        # 탭 생성
        self.notebook = ttk.Notebook(parent, style='Custom.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 탭 1: 분류 결과
        result_tab = ttk.Frame(self.notebook, padding="10")
        result_tab.configure(style='Tab.TFrame')
        self.notebook.add(result_tab, text="📋 분류 결과")
        
        # 탭 2: 파일명 변경
        rename_tab = ttk.Frame(self.notebook, padding="10")
        rename_tab.configure(style='Tab.TFrame')
        self.notebook.add(rename_tab, text="✏️ 파일명 변경")
        
        self.setup_result_tab(result_tab)
        self.setup_rename_tab(rename_tab)
    
    def setup_result_tab(self, parent):
        """분류 결과 탭"""
        # 상단 버튼
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)
        
        detail_btn = tk.Button(btn_frame, text="🔍 상세보기", command=self.show_detail,
                              font=("맑은 고딕", 11, "bold"), 
                              bg=self.colors['info'], fg='white',
                              relief='raised', bd=1, cursor='hand2')
        detail_btn.pack(side=tk.LEFT, padx=2)
        
        edit_btn = tk.Button(btn_frame, text="✏️ 장르 수정", command=self.edit_genre,
                            font=("맑은 고딕", 11, "bold"),
                            bg=self.colors['warning'], fg='white',
                            relief='raised', bd=1, cursor='hand2')
        edit_btn.pack(side=tk.LEFT, padx=2)
        
        filename_btn = tk.Button(btn_frame, text="📝 파일명 수정", command=self.edit_filename,
                                font=("맑은 고딕", 11, "bold"),
                                bg='#9B59B6', fg='white',  # 보라색
                                relief='raised', bd=1, cursor='hand2')
        filename_btn.pack(side=tk.LEFT, padx=2)
        
        stats_btn = tk.Button(btn_frame, text="📊 통계", command=self.show_statistics,
                             font=("맑은 고딕", 11, "bold"),
                             bg=self.colors['primary'], fg='white',
                             relief='raised', bd=1, cursor='hand2')
        stats_btn.pack(side=tk.LEFT, padx=2)
        
        delete_btn = tk.Button(btn_frame, text="🗑️ 선택 삭제", command=self.delete_selected,
                              font=("맑은 고딕", 11, "bold"),
                              bg=self.colors['danger'], fg='white',
                              relief='raised', bd=1, cursor='hand2')
        delete_btn.pack(side=tk.LEFT, padx=2)
        
        # 결과 트리뷰 프레임 (배경색 적용)
        tree_frame = tk.Frame(parent, bg=self.colors['tree_bg'], relief='sunken', bd=2)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 트리뷰 스타일 설정
        style = ttk.Style()
        style.configure('Result.Treeview',
                       background=self.colors['tree_bg'],
                       foreground=self.colors['dark_text'],
                       fieldbackground=self.colors['tree_bg'],
                       font=('맑은 고딕', 12))
        
        style.configure('Result.Treeview.Heading',
                       background=self.colors['primary'],
                       foreground='white',
                       font=('맑은 고딕', 13, 'bold'))
        
        style.map('Result.Treeview',
                 background=[('selected', self.colors['tree_select'])],
                 foreground=[('selected', self.colors['dark_text'])])
        
        columns = ('파일명', '제목', '장르', '신뢰도', '출처')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', 
                                selectmode='extended', style='Result.Treeview')
        
        self.tree.heading('파일명', text='📁 파일명', command=lambda: self.sort_column('파일명'))
        self.tree.heading('제목', text='📖 추출된 제목', command=lambda: self.sort_column('제목'))
        self.tree.heading('장르', text='🎭 장르', command=lambda: self.sort_column('장르'))
        self.tree.heading('신뢰도', text='📊 신뢰도', command=lambda: self.sort_column('신뢰도'))
        self.tree.heading('출처', text='🔍 출처', command=lambda: self.sort_column('출처'))
        
        # 컬럼 너비 및 정렬 설정
        self.tree.column('파일명', width=300, anchor='w')  # 왼쪽 정렬
        self.tree.column('제목', width=400, anchor='w')    # 왼쪽 정렬
        self.tree.column('장르', width=80, anchor='center')  # 중앙 정렬
        self.tree.column('신뢰도', width=80, anchor='center')  # 중앙 정렬
        self.tree.column('출처', width=120, anchor='center')  # 중앙 정렬, 너비 축소
        
        # 스크롤바
        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # 장르별 색상 태그 설정
        self.setup_genre_colors()
        
        # 더블클릭 이벤트 (장르 수정)
        self.tree.bind('<Double-1>', lambda e: self.edit_genre())
    
    def _simplify_method(self, method, result_details=None):
        """분류 방법을 출처로 표시 (플랫폼 이름 우선)"""
        if not method:
            return "-"
        
        # result_details에서 네이버 검색 결과의 source 정보 추출
        platform_source = None
        if result_details and isinstance(result_details, dict):
            naver_result = result_details.get('naver_result')
            if naver_result and isinstance(naver_result, dict):
                platform_source = naver_result.get('source', '')
        
        # 방법별 출처 표시 (플랫폼 이름 우선)
        method_mapping = {
            # 네이버 검색 기반 - 플랫폼 이름 표시
            'naver_ridibooks_meta_priority': '리디북스',
            'naver_ridibooks_priority': '리디북스',
            'naver_novelpia_priority': '노벨피아',
            'naver_novelpia_hashtag': '노벨피아',
            'naver_novelpia_hashtag_analysis': '노벨피아',
            'naver_munpia_priority': '문피아',
            'naver_naver_series_priority': '네이버시리즈',
            'naver_kakao_priority': '카카오페이지',
            
            # 재매핑 - 플랫폼+키워드
            'naverseries_keyword_refined': '키워드+네이버시리즈',
            'naverseriesports_refined': '키워드+네이버시리즈',
            'naverseries_sports_refined': '키워드+네이버시리즈',
            'kakaopage_keyword_refined': '키워드+카카오페이지',
            'kakaopagesports_refined': '키워드+카카오페이지',
            'kakaopage_sports_refined': '키워드+카카오페이지',
            'ridibooks_history_refined': '키워드+리디북스',
            'ridibookssports_refined': '키워드+리디북스',
            'ridibooks_sports_refined': '키워드+리디북스',
            'ridibooksgame_refined': '키워드+리디북스',
            'ridibooks_game_refined': '키워드+리디북스',
            
            # 키워드 기반
            'keyword_only': '키워드',
            'keyword_high_confidence': '키워드',
            'keyword_higher_confidence': '키워드',
            
            # 특수 케이스
            'special_case': '키워드',
            'compound_pattern': '키워드',
            'manual_edit': '사용자',
            'author_genre_db': '저자DB',
            'author_genre_db_fallback': '저자DB',
            'title_keyword_analysis': '키워드',
            
            # 통합 결과 - platform_source 확인 필요
            'both_agree': None,  # 동적 처리
            'naver_high_confidence': None,  # 동적 처리
            'naver_higher_confidence': None,  # 동적 처리
            'naver_only': None,  # 동적 처리
            
            # 신뢰도 부족
            'low_confidence': '키워드'
        }
        
        # 매핑된 값이 있으면 사용 (None이 아닌 경우)
        if method in method_mapping and method_mapping[method] is not None:
            return method_mapping[method]
        
        # 네이버 관련 method는 platform_source로 플랫폼 이름 추출
        if method in ['naver_only', 'naver_high_confidence', 'naver_higher_confidence', 'both_agree']:
            if platform_source:
                # platform_source에서 플랫폼 이름 추출 (한글 포함)
                platform_source_lower = platform_source.lower()
                if 'ridibooks' in platform_source_lower or '리디북스' in platform_source:
                    platform_name = '리디북스'
                elif 'novelpia' in platform_source_lower or '노벨피아' in platform_source:
                    platform_name = '노벨피아'
                elif 'munpia' in platform_source_lower or '문피아' in platform_source:
                    platform_name = '문피아'
                elif 'naver' in platform_source_lower or '네이버시리즈' in platform_source:
                    platform_name = '네이버시리즈'
                elif 'kakao' in platform_source_lower or '카카오' in platform_source:
                    platform_name = '카카오페이지'
                elif 'novelnet' in platform_source_lower or '소설넷' in platform_source:
                    platform_name = '소설넷'
                elif 'mrblue' in platform_source_lower or '미스터블루' in platform_source:
                    platform_name = '미스터블루'
                elif 'webtoonguide' in platform_source_lower or '웹툰가이드' in platform_source:
                    platform_name = '웹툰가이드'
                elif 'yes24' in platform_source_lower or 'YES24' in platform_source:
                    platform_name = 'YES24'
                elif 'kyobo' in platform_source_lower or '교보문고' in platform_source:
                    platform_name = '교보문고'
                elif 'aladin' in platform_source_lower or '알라딘' in platform_source:
                    platform_name = '알라딘'
                elif 'joar' in platform_source_lower or '조아라' in platform_source:
                    platform_name = '조아라'
                else:
                    platform_name = '네이버'
                
                # both_agree는 키워드+플랫폼
                if method == 'both_agree':
                    return f'키워드+{platform_name}'
                else:
                    return platform_name
            else:
                # platform_source가 없으면 기본값
                if method == 'both_agree':
                    return '키워드+네이버'
                else:
                    return '네이버'
        
        # 매핑되지 않은 경우 플랫폼 이름 추출 (한글 포함)
        method_lower = method.lower()
        
        # 플랫폼별 우선순위로 확인 (한글 이름도 체크)
        if 'ridibooks' in method_lower or 'ridi' in method_lower or '리디북스' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+리디북스'
            return '리디북스'
        elif 'novelpia' in method_lower or '노벨피아' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+노벨피아'
            return '노벨피아'
        elif 'munpia' in method_lower or '문피아' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+문피아'
            return '문피아'
        elif ('naver' in method_lower and 'series' in method_lower) or '네이버시리즈' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+네이버시리즈'
            return '네이버시리즈'
        elif 'kakao' in method_lower or '카카오' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+카카오페이지'
            return '카카오페이지'
        elif 'novelnet' in method_lower or '소설넷' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+소설넷'
            return '소설넷'
        elif 'mrblue' in method_lower or '미스터블루' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+미스터블루'
            return '미스터블루'
        elif 'webtoonguide' in method_lower or '웹툰가이드' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+웹툰가이드'
            return '웹툰가이드'
        elif 'yes24' in method_lower:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+YES24'
            return 'YES24'
        elif 'kyobo' in method_lower or '교보문고' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+교보문고'
            return '교보문고'
        elif 'aladin' in method_lower or '알라딘' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+알라딘'
            return '알라딘'
        elif 'joar' in method_lower or '조아라' in method:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+조아라'
            return '조아라'
        elif 'naver' in method_lower:
            if 'keyword' in method_lower or 'refined' in method_lower:
                return '키워드+네이버'
            return '네이버'
        elif 'keyword' in method_lower:
            return '키워드'
        else:
            return method[:8]  # 최대 8글자로 제한
    
    def _add_section_header(self, parent, title, color):
        """섹션 헤더 추가"""
        header_frame = tk.Frame(parent, bg=color, height=40)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=title, bg=color, fg='white',
                font=("맑은 고딕", 12, "bold")).pack(side=tk.LEFT, padx=15, pady=8)
    
    def _add_info_row(self, parent, label, value, bold=False, large=False):
        """정보 행 추가"""
        row_frame = tk.Frame(parent, bg='white')
        row_frame.pack(fill=tk.X, padx=15, pady=2)
        
        # 라벨
        label_font = ("맑은 고딕", 10, "bold")
        tk.Label(row_frame, text=f"{label}:", bg='white', fg='#666666',
                font=label_font, width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(10, 5))
        
        # 값
        if large:
            value_font = ("맑은 고딕", 14, "bold" if bold else "normal")
        else:
            value_font = ("맑은 고딕", 10, "bold" if bold else "normal")
        
        value_label = tk.Label(row_frame, text=str(value), bg='white', fg='#000000',
                              font=value_font, anchor=tk.W, wraplength=450, justify=tk.LEFT)
        value_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
    
    def setup_genre_colors(self):
        """장르별 색상 태그 설정"""
        genre_colors = {
            '무협': '#FF6B6B',      # 빨간색 계열
            '로판': '#FF69B4',      # 핑크색
            '현판': '#4ECDC4',      # 청록색
            '퓨판': '#45B7D1',      # 파란색
            '겜판': '#96CEB4',      # 연두색
            '선협': '#FFEAA7',      # 노란색
            '역사': '#DDA0DD',      # 자주색
            'SF': '#87CEEB',        # 하늘색
            '스포츠': '#FFA500',    # 주황색
            '밀리터리': '#556B2F',  # 올리브 그린
            '패러디': '#DA70D6',    # 오키드
            '언정': '#F0A0A0',      # 연한 빨간색
            '현대': '#B0C4DE',      # 연한 파란색
            '소설': '#D3D3D3',      # 연한 회색
            '공포': '#2F2F2F',      # 어두운 회색
            '미분류': '#F5F5F5'     # 매우 연한 회색
        }
        
        for genre, color in genre_colors.items():
            self.tree.tag_configure(genre, background=color, foreground='white' if genre == '공포' else 'black')
    
    def setup_rename_tab(self, parent):
        """파일명 변경 탭"""
        # 설명
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(info_frame, text="분류된 장르를 파일명에 추가합니다.", 
                 font=("맑은 고딕", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(info_frame, text="예: 화산귀환.txt → [무협] 화산귀환.txt", 
                 foreground="gray").pack(anchor=tk.W)
        
        # 옵션
        option_frame = ttk.LabelFrame(parent, text="변경 옵션", padding="10")
        option_frame.pack(fill=tk.X, pady=5)
        
        # 형식 선택
        format_frame = ttk.Frame(option_frame)
        format_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(format_frame, text="형식:").pack(side=tk.LEFT)
        
        self.rename_format_var = tk.StringVar(value="[장르] 제목")
        formats = ["[장르] 제목", "제목 [장르]", "장르_제목"]
        for fmt in formats:
            ttk.Radiobutton(format_frame, text=fmt, value=fmt, 
                           variable=self.rename_format_var).pack(side=tk.LEFT, padx=10)
        
        # 미리보기 프레임 (배경색 적용)
        preview_outer = tk.Frame(parent, bg=self.colors['tree_bg'], relief='sunken', bd=2)
        preview_outer.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        preview_frame = ttk.LabelFrame(preview_outer, text="📋 미리보기 (체크박스로 변경할 파일 선택)", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 미리보기 트리뷰 스타일 설정
        style = ttk.Style()
        style.configure('Preview.Treeview',
                       background=self.colors['tree_bg'],
                       foreground=self.colors['dark_text'],
                       fieldbackground=self.colors['tree_bg'],
                       font=('맑은 고딕', 12))
        
        style.configure('Preview.Treeview.Heading',
                       background=self.colors['warning'],
                       foreground='white',
                       font=('맑은 고딕', 13, 'bold'))
        
        style.map('Preview.Treeview',
                 background=[('selected', self.colors['tree_select'])],
                 foreground=[('selected', self.colors['dark_text'])])
        
        # 미리보기 리스트 (체크박스 추가)
        preview_columns = ('선택', '원본', '변경후')
        self.preview_tree = ttk.Treeview(preview_frame, columns=preview_columns, 
                                        show='tree headings', height=15, style='Preview.Treeview')
        
        self.preview_tree.heading('#0', text='')
        self.preview_tree.heading('선택', text='✅ 선택')
        self.preview_tree.heading('원본', text='📁 원본 파일명')
        self.preview_tree.heading('변경후', text='✏️ 변경될 파일명')
        
        self.preview_tree.column('#0', width=30)
        self.preview_tree.column('선택', width=50)
        self.preview_tree.column('원본', width=300)
        self.preview_tree.column('변경후', width=300)
        
        # 체크박스 토글 이벤트
        self.preview_tree.bind('<Button-1>', self.toggle_preview_checkbox)
        
        preview_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, 
                                      command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=preview_scroll.set)
        
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 체크박스 상태 저장
        self.preview_checkboxes = {}
        self.last_clicked_item = None  # Shift 선택을 위한 마지막 클릭 항목
        
        # 버튼
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)
        
        select_all_btn = tk.Button(btn_frame, text="☑️ 전체 선택", command=self.select_all_preview,
                                   font=("맑은 고딕", 12, "bold"),
                                   bg=self.colors['success'], fg='white',
                                   relief='raised', bd=1, cursor='hand2')
        select_all_btn.pack(side=tk.LEFT, padx=2)
        
        deselect_all_btn = tk.Button(btn_frame, text="☐ 전체 해제", command=self.deselect_all_preview,
                                    font=("맑은 고딕", 12, "bold"),
                                    bg=self.colors['gray'], fg='white',
                                    relief='raised', bd=1, cursor='hand2')
        deselect_all_btn.pack(side=tk.LEFT, padx=2)
        
        refresh_btn = tk.Button(btn_frame, text="🔄 미리보기 새로고침", command=self.update_rename_preview,
                               font=("맑은 고딕", 12, "bold"),
                               bg=self.colors['info'], fg='white',
                               relief='raised', bd=1, cursor='hand2')
        refresh_btn.pack(side=tk.LEFT, padx=2)
        
        execute_btn = tk.Button(btn_frame, text="✏️ 파일명 변경 실행", command=self.execute_rename,
                               font=("맑은 고딕", 12, "bold"),
                               bg=self.colors['warning'], fg='white',
                               relief='raised', bd=1, cursor='hand2')
        execute_btn.pack(side=tk.LEFT, padx=2)
        
        restore_btn = tk.Button(btn_frame, text="↩️ 원래대로 복구", command=self.restore_filenames,
                               font=("맑은 고딕", 12, "bold"),
                               bg=self.colors['danger'], fg='white',
                               relief='raised', bd=1, cursor='hand2')
        restore_btn.pack(side=tk.LEFT, padx=2)
        
        # 탭이 표시될 때 자동으로 미리보기 업데이트 (파일명 변경 완료 시 제외)
        parent.bind('<Visibility>', lambda e: self._on_rename_tab_visible())
    
    def _on_rename_tab_visible(self):
        """파일명 변경 탭이 보일 때 처리"""
        if not self.files_renamed:
            # 파일명 변경이 완료되지 않았으면 미리보기 업데이트
            self.update_rename_preview()
        # 파일명 변경이 완료되었으면 미리보기 업데이트 안 함 (빈 상태 유지)
    
    def toggle_naver_options(self):
        """네이버 검색 옵션 토글"""
        if not self.use_naver_var.get():
            # 네이버 검색을 끄면 API 옵션도 비활성화
            self.use_naver_api_var.set(False)
            self.toggle_api_key_entry()
    
    def toggle_api_key_entry(self):
        """API 키 입력 필드 활성화/비활성화"""
        if self.use_naver_api_var.get() and self.use_naver_var.get():
            # API 사용 시 입력 필드 활성화
            for widget in self.api_key_frame.winfo_children():
                if isinstance(widget, (ttk.Entry, ttk.Button)):
                    widget.config(state='normal')
                elif isinstance(widget, ttk.Frame):
                    for btn in widget.winfo_children():
                        if isinstance(btn, ttk.Button):
                            btn.config(state='normal')
        else:
            # API 미사용 시 입력 필드 비활성화
            for widget in self.api_key_frame.winfo_children():
                if isinstance(widget, (ttk.Entry, ttk.Button)):
                    widget.config(state='disabled')
                elif isinstance(widget, ttk.Frame):
                    for btn in widget.winfo_children():
                        if isinstance(btn, ttk.Button):
                            btn.config(state='disabled')
    
    def save_api_keys(self):
        """API 키 저장 (간단한 암호화)"""
        client_id = self.api_client_id_var.get().strip()
        client_secret = self.api_client_secret_var.get().strip()
        
        if not client_id or not client_secret:
            messagebox.showwarning("경고", "Client ID와 Client Secret을 모두 입력해주세요.")
            return
        
        try:
            from modules.classifier.api_config_manager import APIConfigManager
            
            # APIConfigManager로 암호화 저장
            manager = APIConfigManager()
            success = manager.save_config(client_id, client_secret, encrypt=True)
            
            if success:
                messagebox.showinfo("성공", "API 키가 암호화되어 저장되었습니다.")
                print("✅ API 키 암호화 저장 완료")
            else:
                messagebox.showerror("오류", "API 키 저장에 실패했습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"API 키 저장 실패: {str(e)}")
    
    def auto_load_api_keys(self):
        """저장된 API 키 자동 로드 (메시지 없이)"""
        try:
            from modules.classifier.api_config_manager import APIConfigManager
            
            # APIConfigManager로 로드 (자동 복호화)
            manager = APIConfigManager()
            config = manager.load_config()
            
            if config:
                self.api_client_id_var.set(config['client_id'])
                self.api_client_secret_var.set(config['client_secret'])
                
                # API 사용 체크박스 활성화
                self.use_naver_api_var.set(True)
                
                print("✅ 네이버 API 키 자동 로드 완료 (암호화)")
            else:
                print("ℹ️  저장된 API 키 없음")
        except Exception as e:
            print(f"⚠️  API 키 자동 로드 실패: {str(e)}")
    
    def load_api_keys(self):
        """API 키 불러오기 (버튼 클릭 시)"""
        try:
            from modules.classifier.api_config_manager import APIConfigManager
            
            # APIConfigManager로 로드 (자동 복호화)
            manager = APIConfigManager()
            config = manager.load_config()
            
            if not config:
                messagebox.showinfo("알림", "저장된 API 키가 없습니다.")
                return
            
            self.api_client_id_var.set(config['client_id'])
            self.api_client_secret_var.set(config['client_secret'])
            
            # API 사용 체크박스 활성화
            self.use_naver_api_var.set(True)
            
            messagebox.showinfo("성공", "API 키를 불러왔습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"API 키 불러오기 실패: {str(e)}")
    
    def select_directory(self):
        """디렉토리 선택"""
        directory = filedialog.askdirectory(title="웹소설 파일이 있는 디렉토리 선택")
        
        if directory:
            self.current_directory = directory
            self.dir_label.config(text=f"선택된 디렉토리: {directory}", 
                                 foreground="black")
            
            # 파일 개수 확인
            extensions = [ext for ext, var in self.ext_vars.items() if var.get()]
            files = [f for f in os.listdir(directory) 
                    if any(f.endswith(ext) for ext in extensions)]
            
            messagebox.showinfo("디렉토리 선택", 
                              f"{len(files)}개의 파일을 찾았습니다.")
    
    def start_classification(self):
        """분류 시작"""
        if not self.current_directory:
            messagebox.showwarning("경고", "먼저 디렉토리를 선택해주세요.")
            return
        
        if self.is_processing:
            messagebox.showwarning("경고", "이미 처리 중입니다.")
            return
        
        # 새로운 분류 시작 시 플래그 리셋
        self.files_renamed = False
        
        # 파일 목록 가져오기
        extensions = [ext for ext, var in self.ext_vars.items() if var.get()]
        files = [f for f in os.listdir(self.current_directory) 
                if any(f.endswith(ext) for ext in extensions)]
        
        if not files:
            messagebox.showwarning("경고", "선택한 확장자의 파일이 없습니다.")
            return
        
        # 확인
        use_naver = self.use_naver_var.get()
        use_naver_api = self.use_naver_api_var.get()
        estimated_time = len(files) * (3 if use_naver else 0.1)
        
        msg = f"{len(files)}개 파일을 분류합니다.\n"
        if use_naver:
            if use_naver_api:
                msg += f"네이버 검색: API 사용 (안정적, 빠름)\n"
            else:
                msg += f"네이버 검색: 웹 크롤링 (V3 - 리디북스 우선)\n"
            msg += f"신뢰도: 85-95% (공식 플랫폼 페이지)\n"
            msg += f"우선순위: 리디북스 > 노벨피아 > 네이버시리즈\n"
        else:
            msg += f"네이버 검색: 미사용\n"
        msg += f"예상 시간: 약 {estimated_time:.0f}초\n\n"
        msg += "계속하시겠습니까?"
        
        if not messagebox.askyesno("확인", msg):
            return
        
        # 버튼 상태 변경
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_processing = True
        
        # 결과 초기화
        self.clear_results()
        
        # 분류 결과 탭으로 자동 전환 (탭 인덱스 0)
        self.notebook.select(0)
        
        # 별도 스레드에서 실행
        thread = threading.Thread(target=self.process_files, args=(files,))
        thread.daemon = True
        thread.start()
    
    def process_files(self, files):
        """파일 처리 (별도 스레드)"""
        use_naver = self.use_naver_var.get()
        use_naver_api = self.use_naver_api_var.get()
        total = len(files)
        
        # API 키 가져오기
        naver_api_config = None
        if use_naver and use_naver_api:
            client_id = self.api_client_id_var.get().strip()
            client_secret = self.api_client_secret_var.get().strip()
            
            if client_id and client_secret:
                naver_api_config = {
                    'client_id': client_id,
                    'client_secret': client_secret
                }
            else:
                # API 키가 없으면 웹 크롤링으로 폴백
                self.root.after(0, messagebox.showwarning, "경고", 
                              "API 키가 입력되지 않아 웹 크롤링 방식을 사용합니다.")
                use_naver_api = False
        
        for i, filename in enumerate(files):
            if not self.is_processing:
                break
            
            # 진행 상황 업데이트
            self.root.after(0, self.update_progress, i + 1, total, filename)
            
            # 분류 실행
            filepath = os.path.join(self.current_directory, filename)
            
            # FilenameGenreClassifier가 내부적으로 HybridClassifier를 사용하고
            # HybridClassifier가 NaverGenreExtractorV3를 사용하므로
            # use_naver 옵션과 API 설정을 전달
            result_data = self.classifier.classify_file(
                filename, 
                use_naver=use_naver,
                naver_api_config=naver_api_config
            )
            
            result = {
                'filename': filename,
                'title': result_data.get('title', filename),
                'genre': result_data['genre'],
                'confidence': result_data['confidence'],
                'method': result_data['method'],
                'details': result_data.get('details', {})
            }
            
            # 결과 추가
            self.root.after(0, self.add_result, result)
            
            # 진행률 업데이트
            progress = (i + 1) / total * 100
            self.root.after(0, self.progress_bar.config, {'value': progress})
        
        # 완료
        self.root.after(0, self.finish_processing)
    
    def update_progress(self, current, total, filename):
        """진행 상황 업데이트"""
        self.progress_label.config(
            text=f"처리 중... ({current}/{total}) - {filename}"
        )
    
    def add_result(self, result):
        """결과 추가"""
        self.results.append(result)
        
        # 파일명에서 폴더명 제거
        filename_only = os.path.basename(result['filename'])
        
        # 제목 가져오기 (경로가 아니므로 basename 불필요)
        title = result['title'] or '-'
        
        # 트리뷰에 추가
        confidence_str = f"{result['confidence']:.0%}" if result['confidence'] > 0 else "-"
        
        # 장르에 따라 색상 구분
        tag = result['genre']
        
        self.tree.insert('', tk.END, values=(
            filename_only,
            title,
            result['genre'],
            confidence_str,
            self._simplify_method(result['method'], result.get('details'))
        ), tags=(tag,))
        
        # 통계 업데이트
        self.update_statistics()
    

    def finish_processing(self):
        """처리 완료"""
        self.is_processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_label.config(text="완료!")
        
        messagebox.showinfo("완료", 
                          f"{len(self.results)}개 파일 분류가 완료되었습니다.")
    
    def stop_classification(self):
        """분류 중지"""
        if messagebox.askyesno("확인", "분류를 중지하시겠습니까?"):
            self.is_processing = False
    
    def save_results(self):
        """결과 저장 (JSON 또는 텍스트)"""
        if not self.results:
            messagebox.showwarning("경고", "저장할 결과가 없습니다.")
            return
        
        # 저장 형식 선택 창
        save_window = tk.Toplevel(self.root)
        save_window.title("저장 형식 선택")
        save_window.geometry("450x250")
        save_window.transient(self.root)
        save_window.grab_set()
        
        # 메인 창 위치 기준으로 팝업 위치 설정
        self.root.update_idletasks()
        x = self.root.winfo_x() + 150
        y = self.root.winfo_y() + 150
        save_window.geometry(f"450x250+{x}+{y}")
        
        # 중앙 정렬을 위한 프레임
        main_frame = ttk.Frame(save_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="저장 형식을 선택하세요:", 
                 font=("맑은 고딕", 13, "bold")).pack(pady=(0, 20))
        
        format_var = tk.StringVar(value="json")
        
        ttk.Radiobutton(main_frame, text="JSON 파일 (상세 정보 포함)", 
                       value="json", variable=format_var).pack(anchor=tk.W, padx=20, pady=5)
        ttk.Radiobutton(main_frame, text="텍스트 파일 (분류 결과 표 형식)", 
                       value="text", variable=format_var).pack(anchor=tk.W, padx=20, pady=5)
        ttk.Radiobutton(main_frame, text="텍스트 파일 (상세 정보 포함)", 
                       value="text_detail", variable=format_var).pack(anchor=tk.W, padx=20, pady=5)
        
        def do_save():
            format_type = format_var.get()
            save_window.destroy()
            
            if format_type == "json":
                self._save_as_json()
            elif format_type == "text":
                self._save_as_text()
            else:
                self._save_as_text_detail()
        
        def do_cancel():
            save_window.destroy()
        
        # 버튼 프레임
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 0))
        
        save_format_btn = tk.Button(button_frame, text="💾 저장", command=do_save,
                                    font=("맑은 고딕", 11, "bold"), width=12,
                                    bg=self.colors['success'], fg='white',
                                    relief='raised', bd=2, cursor='hand2')
        save_format_btn.pack(side=tk.LEFT, padx=10)
        
        cancel_format_btn = tk.Button(button_frame, text="❌ 취소", command=do_cancel,
                                     font=("맑은 고딕", 11, "bold"), width=12,
                                     bg=self.colors['gray'], fg='white',
                                     relief='raised', bd=2, cursor='hand2')
        cancel_format_btn.pack(side=tk.LEFT, padx=10)
    
    def _save_as_json(self):
        """JSON 형식으로 저장"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")],
            initialfile=f"classification_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, ensure_ascii=False, indent=2)
                
                messagebox.showinfo("저장 완료", f"JSON 파일로 저장되었습니다:\n{filename}")
            except Exception as e:
                messagebox.showerror("오류", f"저장 실패:\n{str(e)}")
    
    def _save_as_text(self):
        """텍스트 파일로 저장 (장르별 그룹화, 보기 편한 형식)"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
            initialfile=f"classification_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if filename:
            try:
                from collections import Counter, defaultdict
                
                with open(filename, 'w', encoding='utf-8') as f:
                    # 헤더
                    f.write("╔" + "═"*98 + "╗\n")
                    f.write("║" + " "*35 + "웹소설 장르 분류 결과" + " "*43 + "║\n")
                    f.write("╠" + "═"*98 + "╣\n")
                    f.write(f"║  생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " "*68 + "║\n")
                    f.write(f"║  총 파일 수: {len(self.results)}개" + " "*(85-len(str(len(self.results)))) + "║\n")
                    f.write("╚" + "═"*98 + "╝\n\n")
                    
                    # 통계
                    genres = [r['genre'] for r in self.results]
                    genre_counts = Counter(genres)
                    
                    # 평균 신뢰도
                    confidences = [r['confidence'] for r in self.results if r['confidence'] > 0]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                    
                    f.write("┌─ 📊 통계 요약 " + "─"*83 + "┐\n")
                    f.write("│\n")
                    f.write(f"│  평균 신뢰도: {avg_confidence:.1%}\n")
                    f.write("│\n")
                    f.write("│  장르별 분포:\n")
                    for genre, count in genre_counts.most_common():
                        percentage = count / len(self.results) * 100
                        bar_length = int(percentage / 2)  # 50% = 25칸
                        bar = "█" * bar_length + "░" * (25 - bar_length)
                        f.write(f"│    {genre:8s} │ {bar} │ {count:3d}개 ({percentage:5.1f}%)\n")
                    f.write("│\n")
                    f.write("└" + "─"*98 + "┘\n\n")
                    
                    # 장르별로 그룹화
                    genre_groups = defaultdict(list)
                    for result in self.results:
                        genre_groups[result['genre']].append(result)
                    
                    # 장르별로 출력
                    for genre, count in genre_counts.most_common():
                        results_in_genre = genre_groups[genre]
                        
                        # 장르 헤더
                        f.write("\n" + "┌─ " + f"📁 {genre} ({len(results_in_genre)}개)" + " ─"*(92-len(genre)-len(str(len(results_in_genre)))) + "┐\n")
                        
                        # 해당 장르의 작품들
                        for i, result in enumerate(results_in_genre, 1):
                            filename_only = os.path.basename(result['filename'])
                            title = result['title']
                            confidence = f"{result['confidence']:.0%}" if result['confidence'] > 0 else "-"
                            method = self._simplify_method(result['method'], result.get('details'))
                            
                            # 신뢰도 아이콘
                            if result['confidence'] >= 0.95:
                                conf_icon = "✓✓"
                            elif result['confidence'] >= 0.85:
                                conf_icon = "✓ "
                            elif result['confidence'] > 0:
                                conf_icon = "○ "
                            else:
                                conf_icon = "? "
                            
                            # 파일명 (최대 50자)
                            if len(filename_only) > 50:
                                filename_display = filename_only[:47] + "..."
                            else:
                                filename_display = filename_only
                            
                            f.write(f"│ {i:3d}. {conf_icon} {filename_display}\n")
                            
                            # 제목 (최대 50자)
                            if len(title) > 50:
                                title_display = title[:47] + "..."
                            else:
                                title_display = title
                            f.write(f"│      제목: {title_display}\n")
                            
                            # 신뢰도와 출처
                            f.write(f"│      신뢰도: {confidence:5s} │ 출처: {method}\n")
                            
                            if i < len(results_in_genre):
                                f.write("│      " + "─"*90 + "\n")
                        
                        f.write("└" + "─"*98 + "┘\n")
                    
                    # 푸터
                    f.write("\n" + "╔" + "═"*98 + "╗\n")
                    f.write("║  범례:                                                                                           ║\n")
                    f.write("║    ✓✓ = 95% 이상 (매우 높은 신뢰도)                                                              ║\n")
                    f.write("║    ✓  = 85% 이상 (높은 신뢰도)                                                                   ║\n")
                    f.write("║    ○  = 85% 미만 (중간 신뢰도)                                                                   ║\n")
                    f.write("║    ?  = 미분류 (수동 확인 필요)                                                                  ║\n")
                    f.write("╚" + "═"*98 + "╝\n")
                
                messagebox.showinfo("저장 완료", f"텍스트 파일로 저장되었습니다:\n{filename}")
            except Exception as e:
                messagebox.showerror("오류", f"저장 실패:\n{str(e)}")
    
    def _save_as_text_detail(self):
        """텍스트 파일로 저장 (상세 정보 포함)"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
            initialfile=f"classification_results_detail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    # 헤더
                    f.write("="*100 + "\n")
                    f.write("웹소설 장르 분류 결과 (상세)\n")
                    f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"총 파일 수: {len(self.results)}개\n")
                    f.write("="*100 + "\n\n")
                    
                    # 각 파일별 상세 정보
                    for i, result in enumerate(self.results, 1):
                        f.write(f"\n{'='*100}\n")
                        f.write(f"[{i}/{len(self.results)}] {os.path.basename(result['filename'])}\n")
                        f.write(f"{'='*100}\n\n")
                        
                        # 기본 정보
                        f.write("【파일 정보】\n")
                        f.write(f"  파일명: {result['filename']}\n")
                        f.write(f"  추출된 제목: {result['title']}\n\n")
                        
                        # 최종 결과
                        f.write("【최종 분류 결과】\n")
                        f.write(f"  장르: {result['genre']}\n")
                        f.write(f"  신뢰도: {result['confidence']:.1%}\n")
                        f.write(f"  출처: {self._simplify_method(result['method'], result.get('details'))}\n\n")
                        
                        # 상세 정보
                        if result.get('details'):
                            details = result['details']
                            
                            # 파일명 기반 결과
                            if details.get('filename_result'):
                                fn = details['filename_result']
                                f.write("【파일명 기반 분류】\n")
                                f.write(f"  장르: {fn['genre']}\n")
                                f.write(f"  신뢰도: {fn['confidence']:.1%}\n")
                                f.write(f"  출처: {fn['method']}\n\n")
                            
                            # 네이버 검색 결과
                            if details.get('naver_result') and details['naver_result'].get('genre'):
                                nv = details['naver_result']
                                f.write("【네이버 검색 결과 (노벨피아 우선)】\n")
                                f.write(f"  장르: {nv['genre']}\n")
                                f.write(f"  신뢰도: {nv['confidence']:.1%}\n")
                                f.write(f"  출처: {nv['source']}\n")
                                
                                if nv.get('raw_genre'):
                                    f.write(f"  원본 장르: {nv['raw_genre']}\n")
                                
                                if nv.get('url'):
                                    f.write(f"  URL: {nv['url']}\n")
                                
                                # 신뢰도 설명
                                confidence = nv['confidence']
                                if confidence >= 0.95:
                                    f.write("  ✓ 매우 높은 신뢰도 (공식 메타 태그)\n")
                                elif confidence >= 0.85:
                                    f.write("  ✓ 높은 신뢰도 (공식 플랫폼 페이지)\n")
                                elif confidence >= 0.75:
                                    f.write("  ○ 중간 신뢰도 (구조화된 데이터)\n")
                                else:
                                    f.write("  △ 낮은 신뢰도 (추측)\n")
                                
                                f.write("\n")
                        
                        f.write("-"*100 + "\n")
                    
                    # 통계 요약
                    f.write(f"\n{'='*100}\n")
                    f.write("【전체 통계】\n")
                    f.write(f"{'='*100}\n\n")
                    
                    from collections import Counter
                    genres = [r['genre'] for r in self.results]
                    genre_counts = Counter(genres)
                    
                    f.write("장르별 분포:\n")
                    for genre, count in genre_counts.most_common():
                        percentage = count / len(self.results) * 100
                        f.write(f"  {genre:10s}: {count:4d}개 ({percentage:5.1f}%)\n")
                    
                    f.write("\n")
                    
                    # 출처별 통계
                    methods = [r['method'] for r in self.results]
                    method_counts = Counter(methods)
                    
                    f.write("출처별 분포:\n")
                    for method, count in method_counts.most_common():
                        percentage = count / len(self.results) * 100
                        f.write(f"  {method:20s}: {count:4d}개 ({percentage:5.1f}%)\n")
                    
                    f.write("\n")
                    
                    # 평균 신뢰도
                    confidences = [r['confidence'] for r in self.results if r['confidence'] > 0]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                    f.write(f"평균 신뢰도: {avg_confidence:.1%}\n")
                
                messagebox.showinfo("저장 완료", f"상세 텍스트 파일로 저장되었습니다:\n{filename}")
            except Exception as e:
                messagebox.showerror("오류", f"저장 실패:\n{str(e)}")
    
    def clear_results(self):
        """결과 초기화"""
        self.results = []
        
        # 트리뷰 초기화
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 진행률 초기화
        self.progress_bar.config(value=0)
        self.progress_label.config(text="대기 중...")
        
        # 통계 초기화
        self.update_statistics()
    
    def on_closing(self):
        """창 닫기"""
        if self.is_processing:
            if not messagebox.askyesno("확인", "분류가 진행 중입니다. 종료하시겠습니까?"):
                return
        
        # 리소스 정리
        if hasattr(self.classifier, 'close'):
            self.classifier.close()
        
        self.root.destroy()
    
    def update_statistics(self):
        """통계 업데이트"""
        if not self.results:
            self.stats_text.config(state=tk.NORMAL)
            self.stats_text.delete('1.0', tk.END)
            self.stats_text.insert('1.0', "통계: 파일 0개")
            self.stats_text.config(state=tk.DISABLED)
            return
        
        from collections import Counter
        
        total = len(self.results)
        genres = [r['genre'] for r in self.results]
        genre_counts = Counter(genres)
        
        confidences = [r['confidence'] for r in self.results if r['confidence'] > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        methods = [r['method'] for r in self.results]
        method_counts = Counter(methods)
        
        # 통계 텍스트 생성
        stats = []
        stats.append(f"📊 전체 통계")
        stats.append(f"  총 파일: {total}개")
        stats.append(f"  평균 신뢰도: {avg_confidence:.1%}")
        stats.append("")
        
        stats.append(f"📁 장르별 분포:")
        for genre, count in genre_counts.most_common():
            percentage = count / total * 100
            stats.append(f"  {genre:10s}: {count:3d}개 ({percentage:5.1f}%)")
        
        stats.append("")
        stats.append(f"🔍 출처:")
        for method, count in method_counts.most_common():
            percentage = count / total * 100
            stats.append(f"  {method:15s}: {count:3d}개 ({percentage:5.1f}%)")
        
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete('1.0', tk.END)
        self.stats_text.insert('1.0', '\n'.join(stats))
        self.stats_text.config(state=tk.DISABLED)
    
    def sort_column(self, col):
        """컬럼 정렬"""
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]
        items.sort()
        
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)
    
    def show_detail(self):
        """상세 정보 표시"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("알림", "항목을 선택해주세요.")
            return
        
        item = selection[0]
        values = self.tree.item(item)['values']
        
        # 결과에서 찾기
        filename = values[0]
        result = next((r for r in self.results if r['filename'] == filename), None)
        
        if not result:
            return
        
        # 상세 정보 창
        detail_window = tk.Toplevel(self.root)
        detail_window.title("📋 상세 정보")
        detail_window.geometry("700x500")
        detail_window.configure(bg='#f5f5f5')
        
        # 메인 창 위치 기준으로 팝업 위치 설정
        self.root.update_idletasks()
        x = self.root.winfo_x() + 50
        y = self.root.winfo_y() + 50
        detail_window.geometry(f"700x500+{x}+{y}")
        
        # 스크롤 가능한 프레임 생성
        canvas = tk.Canvas(detail_window, bg='#f5f5f5', highlightthickness=0)
        scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f5f5f5')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        # 정보 표시 (개선된 포맷)
        
        # 파일 정보 섹션
        self._add_section_header(scrollable_frame, "📄 파일 정보", "#4A90E2")
        self._add_info_row(scrollable_frame, "파일명", os.path.basename(result['filename']))
        self._add_info_row(scrollable_frame, "추출된 제목", result['title'] or '(없음)')
        
        # 최종 분류 결과 섹션
        self._add_section_header(scrollable_frame, "🎯 최종 분류 결과", "#50C878")
        self._add_info_row(scrollable_frame, "장르", result['genre'], bold=True, large=True)
        self._add_info_row(scrollable_frame, "신뢰도", f"{result['confidence']:.1%}")
        self._add_info_row(scrollable_frame, "출처", self._simplify_method(result['method'], result.get('details')))
        
        # 구분선
        tk.Frame(scrollable_frame, height=2, bg='#e0e0e0').pack(fill=tk.X, pady=10)
        
        if result.get('details'):
            details = result['details']
            
            # 파일명 기반 결과
            if details.get('filename_result'):
                fn = details['filename_result']
                self._add_section_header(scrollable_frame, "📝 파일명 기반 분류", "#FF9500")
                self._add_info_row(scrollable_frame, "장르", fn['genre'])
                self._add_info_row(scrollable_frame, "신뢰도", f"{fn['confidence']:.1%}")
                self._add_info_row(scrollable_frame, "출처", fn['method'])
                tk.Frame(scrollable_frame, height=2, bg='#e0e0e0').pack(fill=tk.X, pady=10)
            
            # 네이버 검색 결과
            if details.get('naver_result') and details['naver_result'].get('genre'):
                nv = details['naver_result']
                self._add_section_header(scrollable_frame, "🔍 네이버 검색 결과", "#5856D6")
                self._add_info_row(scrollable_frame, "장르", nv['genre'])
                self._add_info_row(scrollable_frame, "신뢰도", f"{nv['confidence']:.1%}")
                self._add_info_row(scrollable_frame, "출처", nv['source'])
                
                # 출처별 설명
                source_desc = {
                    'ridibooks_page': '리디북스 공식 페이지',
                    'ridibooks_meta': '리디북스 메타 태그',
                    'ridibooks_link': '리디북스 장르 링크',
                    'novelpia_page': '노벨피아 공식 페이지',
                    'novelpia_meta': '노벨피아 메타 태그',
                    'novelpia_tag': '노벨피아 태그',
                    'naver_series_page': '네이버시리즈 공식 페이지',
                    'naver_series_meta': '네이버시리즈 메타 태그',
                    'naver_search': '네이버 검색 결과'
                }
                
                if nv['source'] in source_desc:
                    self._add_info_row(scrollable_frame, "출처 설명", source_desc[nv['source']])
                
                if nv.get('raw_genre'):
                    self._add_info_row(scrollable_frame, "원본 장르", nv['raw_genre'])
                
                if nv.get('url'):
                    self._add_info_row(scrollable_frame, "URL", nv['url'][:50] + "...")
                
                # 신뢰도 설명
                confidence = nv['confidence']
                if confidence >= 0.95:
                    badge_text = "✓ 매우 높은 신뢰도"
                    badge_color = "#34C759"
                elif confidence >= 0.85:
                    badge_text = "✓ 높은 신뢰도"
                    badge_color = "#50C878"
                elif confidence >= 0.75:
                    badge_text = "○ 중간 신뢰도"
                    badge_color = "#FF9500"
                else:
                    badge_text = "△ 낮은 신뢰도"
                    badge_color = "#FF3B30"
                
                badge_frame = tk.Frame(scrollable_frame, bg='#f5f5f5')
                badge_frame.pack(fill=tk.X, padx=15, pady=5)
                tk.Label(badge_frame, text=badge_text, bg=badge_color, fg='white',
                        font=("맑은 고딕", 10, "bold"), padx=10, pady=5,
                        relief=tk.FLAT).pack(anchor=tk.W)
                
                tk.Frame(scrollable_frame, height=2, bg='#e0e0e0').pack(fill=tk.X, pady=10)
            
            # 에러 정보
            if details.get('naver_error'):
                self._add_section_header(scrollable_frame, "⚠️ 네이버 검색 오류", "#FF3B30")
                self._add_info_row(scrollable_frame, "오류", details['naver_error'])
    
    def edit_genre(self):
        """선택한 항목의 장르 수정"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("알림", "장르를 수정할 항목을 선택해주세요.")
            return
        
        if len(selection) > 1:
            messagebox.showinfo("알림", "한 번에 하나의 항목만 수정할 수 있습니다.")
            return
        
        item = selection[0]
        values = self.tree.item(item)['values']
        filename = values[0]
        current_genre = values[2]
        
        # 결과에서 찾기
        result = next((r for r in self.results if os.path.basename(r['filename']) == filename), None)
        if not result:
            return
        
        # 장르 수정 창
        edit_window = tk.Toplevel(self.root)
        edit_window.title("장르 수정")
        edit_window.geometry("450x700")  # 세로 크기 증가 (650 -> 700)
        edit_window.transient(self.root)
        
        # 메인 창 위치 기준으로 팝업 위치 설정
        self.root.update_idletasks()
        x = self.root.winfo_x() + 100
        y = self.root.winfo_y() + 100
        edit_window.geometry(f"450x700+{x}+{y}")
        
        edit_window.grab_set()
        
        # 중앙 정렬을 위한 프레임
        main_frame = ttk.Frame(edit_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 파일 정보 섹션 (박스 스타일)
        info_frame = tk.Frame(main_frame, bg=self.colors['light_bg'], relief='solid', bd=1)
        info_frame.pack(fill=tk.X, pady=(0, 20), padx=5)
        
        tk.Label(info_frame, text="📁 파일 정보", 
                font=("맑은 고딕", 12, "bold"), 
                bg=self.colors['light_bg']).pack(pady=5)
        
        tk.Label(info_frame, text=f"파일명: {filename}", 
                font=("맑은 고딕", 11), 
                bg=self.colors['light_bg']).pack(pady=2)
        
        current_label = tk.Label(info_frame, text=f"현재 장르: {current_genre}", 
                                font=("맑은 고딕", 12, "bold"), 
                                fg='white', bg=self.colors['primary'])
        current_label.pack(pady=5)
        
        # 장르 선택 섹션
        selection_frame = tk.Frame(main_frame, bg=self.colors['tree_bg'], relief='solid', bd=1)
        selection_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20), padx=5)
        
        tk.Label(selection_frame, text="🎭 새 장르 선택", 
                font=("맑은 고딕", 12, "bold"), 
                bg=self.colors['tree_bg']).pack(pady=(10, 5))
        
        # 장르 목록 (색상별 그룹화)
        genre_groups = {
            '판타지 계열': ['판타지', '퓨판', '겜판', '현판'],
            '로맨스 계열': ['로판', '언정'],
            '무협/선협': ['무협', '선협'],
            '기타': ['SF', '스포츠', '역사', '밀리터리', '패러디', '현대', '소설', '미분류']
        }
        
        genre_var = tk.StringVar(value=current_genre)
        
        # 그룹별로 라디오 버튼 배치
        for group_name, genres in genre_groups.items():
            group_frame = tk.LabelFrame(selection_frame, text=group_name, 
                                       font=("맑은 고딕", 10, "bold"),
                                       bg=self.colors['tree_bg'])
            group_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # 각 그룹 내에서 2열로 배치
            for i, genre in enumerate(genres):
                col = i % 2
                row = i // 2
                
                # 장르별 색상 적용
                genre_colors = {
                    '무협': '#FF6B6B', '로판': '#FF69B4', '현판': '#4ECDC4',
                    '퓨판': '#45B7D1', '겜판': '#96CEB4', '선협': '#FFEAA7',
                    '역사': '#DDA0DD', 'SF': '#87CEEB', '스포츠': '#FFA500',
                    '밀리터리': '#556B2F', '패러디': '#DA70D6',
                    '언정': '#F0A0A0', '현대': '#B0C4DE', '소설': '#D3D3D3',
                    '판타지': '#9B59B6', '미분류': '#F5F5F5'
                }
                
                color = genre_colors.get(genre, '#E0E0E0')
                
                radio = tk.Radiobutton(group_frame, text=f"  {genre}  ", value=genre,
                                     variable=genre_var, font=("맑은 고딕", 11),
                                     bg=color, fg='white' if genre in ['무협', 'SF'] else 'black',
                                     selectcolor=color, activebackground=color,
                                     indicatoron=0, width=8, relief='raised', bd=2)
                radio.grid(row=row, column=col, padx=5, pady=3, sticky='ew')
            
            # 컬럼 가중치 설정
            group_frame.grid_columnconfigure(0, weight=1)
            group_frame.grid_columnconfigure(1, weight=1)
        
        def do_save():
            new_genre = genre_var.get()
            if new_genre == current_genre:
                messagebox.showinfo("알림", "장르가 변경되지 않았습니다.")
                edit_window.destroy()
                return
            
            # 결과 업데이트
            result['genre'] = new_genre
            result['method'] = 'manual_edit'  # 수동 수정 표시
            
            # 트리뷰 업데이트
            self.tree.item(item, values=(
                filename,
                values[1],  # 제목
                new_genre,
                values[3],  # 신뢰도
                self._simplify_method('manual_edit', result.get('details'))  # 출처
            ), tags=(new_genre,))
            
            # 통계 업데이트
            self.update_statistics()
            
            # 메시지 없이 바로 창 닫기
            edit_window.destroy()
        
        def do_cancel():
            edit_window.destroy()
        
        # 버튼 프레임
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=(20, 0))
        
        # 저장 버튼 (초록색)
        save_btn = tk.Button(button_frame, text="✅ 저장", command=do_save, 
                            font=("맑은 고딕", 11, "bold"), width=12,
                            bg=self.colors['success'], fg='white',
                            relief='raised', bd=2, cursor='hand2')
        save_btn.pack(side=tk.LEFT, padx=10)
        
        # 취소 버튼 (회색)
        cancel_btn = tk.Button(button_frame, text="❌ 취소", command=do_cancel,
                              font=("맑은 고딕", 11, "bold"), width=12,
                              bg=self.colors['gray'], fg='white',
                              relief='raised', bd=2, cursor='hand2')
        cancel_btn.pack(side=tk.LEFT, padx=10)
    
    def edit_filename(self):
        """선택한 항목의 파일명 수정"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("알림", "파일명을 수정할 항목을 선택해주세요.")
            return
        
        if len(selection) > 1:
            messagebox.showinfo("알림", "한 번에 하나의 항목만 수정할 수 있습니다.")
            return
        
        item = selection[0]
        values = self.tree.item(item)['values']
        filename = values[0]
        extracted_title = values[1]  # 추출된 제목
        
        # 결과에서 찾기 (원본 파일명 또는 수정된 파일명으로 검색)
        result = None
        for r in self.results:
            original_filename = os.path.basename(r['filename'])
            custom_filename = r.get('custom_filename', '')
            
            if original_filename == filename or custom_filename == filename:
                result = r
                break
        
        if not result:
            messagebox.showerror("오류", "결과를 찾을 수 없습니다.")
            return
        
        # 현재 표시된 파일명에서 확장자 제거 (이것이 수정할 기본값)
        # 이미 수정된 파일명이면 그것을 기준으로, 아니면 원본 파일명을 기준으로
        base_name, ext = os.path.splitext(filename)
        current_filename_without_ext = base_name
        
        # 파일명 수정 창
        edit_window = tk.Toplevel(self.root)
        edit_window.title("파일명 수정")
        edit_window.geometry("500x450")  # 높이 증가
        edit_window.transient(self.root)
        
        # 메인 창 위치 기준으로 팝업 위치 설정
        self.root.update_idletasks()
        x = self.root.winfo_x() + 100
        y = self.root.winfo_y() + 100
        edit_window.geometry(f"500x450+{x}+{y}")
        
        edit_window.grab_set()
        
        # 중앙 정렬을 위한 프레임
        main_frame = ttk.Frame(edit_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 파일 정보 섹션 (박스 스타일)
        info_frame = tk.Frame(main_frame, bg=self.colors['light_bg'], relief='solid', bd=1)
        info_frame.pack(fill=tk.X, pady=(0, 20), padx=5)
        
        tk.Label(info_frame, text="📁 파일 정보", 
                font=("맑은 고딕", 12, "bold"), 
                bg=self.colors['light_bg']).pack(pady=5)
        
        tk.Label(info_frame, text=f"원본 파일명: {filename}", 
                font=("맑은 고딕", 11), 
                bg=self.colors['light_bg'], wraplength=450).pack(pady=2)
        
        tk.Label(info_frame, text=f"추출된 제목: {extracted_title}", 
                font=("맑은 고딕", 11), 
                bg=self.colors['light_bg']).pack(pady=2)
        
        # 제목 수정 섹션
        edit_frame = tk.Frame(main_frame, bg=self.colors['tree_bg'], relief='solid', bd=1)
        edit_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20), padx=5)
        
        tk.Label(edit_frame, text="📝 파일명 수정 (확장자 제외)", 
                font=("맑은 고딕", 12, "bold"), 
                bg=self.colors['tree_bg']).pack(pady=(10, 5))
        
        tk.Label(edit_frame, text="예: '심두혈 1-258 (완)' → '심두혈 (19N) 1-258 (완)'", 
                font=("맑은 고딕", 9), 
                bg=self.colors['tree_bg'], fg='gray').pack(pady=2)
        
        # 제목 입력 필드 (원본 파일명의 확장자 제외 부분)
        title_var = tk.StringVar(value=current_filename_without_ext)
        title_entry = tk.Entry(edit_frame, textvariable=title_var, 
                              font=("맑은 고딕", 12), width=40)
        title_entry.pack(pady=10, padx=20)
        title_entry.focus()
        
        # 미리보기
        preview_frame = tk.LabelFrame(edit_frame, text="미리보기", 
                                     font=("맑은 고딕", 10, "bold"),
                                     bg=self.colors['tree_bg'])
        preview_frame.pack(fill=tk.X, padx=20, pady=10)
        
        preview_label = tk.Label(preview_frame, text="", 
                                font=("맑은 고딕", 10),
                                bg=self.colors['tree_bg'], fg=self.colors['primary'])
        preview_label.pack(pady=5)
        
        def update_preview(*args):
            new_filename_without_ext = title_var.get().strip()
            if new_filename_without_ext:
                # 파일 확장자 유지
                new_filename = f"{new_filename_without_ext}{ext}"
                preview_label.config(text=f"새 파일명: {new_filename}")
            else:
                preview_label.config(text="파일명을 입력해주세요")
        
        title_var.trace('w', update_preview)
        update_preview()  # 초기 미리보기
        
        def do_save():
            new_filename_without_ext = title_var.get().strip()
            if not new_filename_without_ext:
                messagebox.showwarning("경고", "파일명을 입력해주세요.")
                return
            
            if new_filename_without_ext == current_filename_without_ext:
                messagebox.showinfo("알림", "파일명이 변경되지 않았습니다.")
                edit_window.destroy()
                return
            
            # 새 파일명 생성
            new_filename = f"{new_filename_without_ext}{ext}"
            
            # 결과 업데이트 (파일명 변경 정보 저장)
            result['custom_filename'] = new_filename
            result['filename_edited'] = True  # 사용자가 수정했음을 표시
            
            # 트리뷰 업데이트 (파일명 열 업데이트)
            self.tree.item(item, values=(
                new_filename,  # 새 파일명
                extracted_title,  # 추출된 제목은 그대로
                values[2],  # 장르
                values[3],  # 신뢰도
                values[4]   # 출처
            ))
            
            # 메시지 없이 바로 창 닫기
            edit_window.destroy()
        
        def do_cancel():
            edit_window.destroy()
        
        # 버튼 프레임
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=(20, 0))
        
        # 저장 버튼 (초록색)
        save_btn = tk.Button(button_frame, text="✅ 저장", command=do_save, 
                            font=("맑은 고딕", 11, "bold"), width=12,
                            bg=self.colors['success'], fg='white',
                            relief='raised', bd=2, cursor='hand2')
        save_btn.pack(side=tk.LEFT, padx=10)
        
        # 취소 버튼 (회색)
        cancel_btn = tk.Button(button_frame, text="❌ 취소", command=do_cancel,
                              font=("맑은 고딕", 11, "bold"), width=12,
                              bg=self.colors['gray'], fg='white',
                              relief='raised', bd=2, cursor='hand2')
        cancel_btn.pack(side=tk.LEFT, padx=10)
    
    def show_statistics(self):
        """통계 창 표시"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title("통계")
        stats_window.geometry("500x400")
        
        # 메인 창 위치 기준으로 팝업 위치 설정
        self.root.update_idletasks()
        x = self.root.winfo_x() + 100
        y = self.root.winfo_y() + 100
        stats_window.geometry(f"500x400+{x}+{y}")
        
        text = scrolledtext.ScrolledText(stats_window, wrap=tk.WORD, 
                                         font=("맑은 고딕", 12))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text.insert('1.0', self.stats_text.get('1.0', tk.END))
        text.config(state=tk.DISABLED)
    
    def delete_selected(self):
        """선택 항목 삭제"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("알림", "삭제할 항목을 선택해주세요.")
            return
        
        if not messagebox.askyesno("확인", f"{len(selection)}개 항목을 삭제하시겠습니까?"):
            return
        
        # 결과에서 삭제
        for item in selection:
            values = self.tree.item(item)['values']
            filename = values[0]
            self.results = [r for r in self.results if r['filename'] != filename]
            self.tree.delete(item)
        
        self.update_statistics()
    
    def update_rename_preview(self):
        """파일명 변경 미리보기 업데이트"""
        # 기존 항목 삭제
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        
        # 체크박스 상태 초기화
        self.preview_checkboxes = {}
        self.last_clicked_item = None  # Shift 선택 초기화
        
        if not self.results:
            return
        
        format_type = self.rename_format_var.get()
        
        for result in self.results:
            if result['genre'] == '미분류':
                continue
            
            original = result['filename']
            genre = result['genre']
            
            # 새 파일명 생성
            basename = os.path.basename(original)
            
            # 사용자가 파일명을 직접 수정했으면 그것을 사용
            if result.get('filename_edited') and result.get('custom_filename'):
                # 사용자가 수정한 파일명 (이미 확장자 포함)
                custom_basename = result['custom_filename']
                name, ext = os.path.splitext(custom_basename)
                
                # 장르 추가 형식 적용
                if format_type == "[장르] 제목":
                    new_name = f"[{genre}] {name}{ext}"
                elif format_type == "제목 [장르]":
                    new_name = f"{name} [{genre}]{ext}"
                else:  # "장르_제목"
                    new_name = f"{genre}_{name}{ext}"
            else:
                # 기존 로직 (원본 파일명 사용)
                if format_type == "[장르] 제목":
                    new_name = f"[{genre}] {basename}"
                elif format_type == "제목 [장르]":
                    name, ext = os.path.splitext(basename)
                    new_name = f"{name} [{genre}]{ext}"
                else:  # "장르_제목"
                    new_name = f"{genre}_{basename}"
            
            # 체크박스 추가 (기본값: 선택됨)
            item_id = self.preview_tree.insert('', tk.END, values=('☑', basename, new_name))
            self.preview_checkboxes[item_id] = True
    
    def toggle_preview_checkbox(self, event):
        """미리보기 체크박스 토글 (Shift 키로 범위 선택 지원)"""
        region = self.preview_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.preview_tree.identify_column(event.x)
            if column == '#1':  # 선택 열
                item = self.preview_tree.identify_row(event.y)
                if item:
                    # Shift 키가 눌린 경우 범위 선택
                    if event.state & 0x0001:  # Shift 키 (0x0001)
                        self._handle_shift_selection(item)
                    else:
                        # 일반 클릭: 체크박스 상태 토글
                        current_state = self.preview_checkboxes.get(item, True)
                        new_state = not current_state
                        self.preview_checkboxes[item] = new_state
                        
                        # 표시 업데이트
                        values = list(self.preview_tree.item(item)['values'])
                        values[0] = '☑' if new_state else '☐'
                        self.preview_tree.item(item, values=values)
                        
                        # 마지막 클릭 위치 저장 (Shift 선택용)
                        self.last_clicked_item = item
    
    def _handle_shift_selection(self, current_item):
        """Shift 키를 사용한 범위 선택 처리"""
        # 마지막 클릭 위치가 없으면 현재 항목만 토글
        if not hasattr(self, 'last_clicked_item') or not self.last_clicked_item:
            current_state = self.preview_checkboxes.get(current_item, True)
            new_state = not current_state
            self.preview_checkboxes[current_item] = new_state
            values = list(self.preview_tree.item(current_item)['values'])
            values[0] = '☑' if new_state else '☐'
            self.preview_tree.item(current_item, values=values)
            self.last_clicked_item = current_item
            return
        
        # 모든 항목 가져오기
        all_items = self.preview_tree.get_children()
        
        try:
            # 시작과 끝 인덱스 찾기
            start_idx = all_items.index(self.last_clicked_item)
            end_idx = all_items.index(current_item)
            
            # 순서 정렬
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
            
            # 현재 항목의 상태를 기준으로 범위 내 모든 항목 설정
            target_state = not self.preview_checkboxes.get(current_item, True)
            
            # 범위 내 모든 항목 선택/해제
            for idx in range(start_idx, end_idx + 1):
                item = all_items[idx]
                self.preview_checkboxes[item] = target_state
                values = list(self.preview_tree.item(item)['values'])
                values[0] = '☑' if target_state else '☐'
                self.preview_tree.item(item, values=values)
            
            # 마지막 클릭 위치 업데이트
            self.last_clicked_item = current_item
            
        except ValueError:
            # 항목을 찾을 수 없는 경우 현재 항목만 토글
            current_state = self.preview_checkboxes.get(current_item, True)
            new_state = not current_state
            self.preview_checkboxes[current_item] = new_state
            values = list(self.preview_tree.item(current_item)['values'])
            values[0] = '☑' if new_state else '☐'
            self.preview_tree.item(current_item, values=values)
            self.last_clicked_item = current_item
    
    def select_all_preview(self):
        """미리보기 전체 선택"""
        for item in self.preview_tree.get_children():
            self.preview_checkboxes[item] = True
            values = list(self.preview_tree.item(item)['values'])
            values[0] = '☑'
            self.preview_tree.item(item, values=values)
    
    def deselect_all_preview(self):
        """미리보기 전체 해제"""
        for item in self.preview_tree.get_children():
            self.preview_checkboxes[item] = False
            values = list(self.preview_tree.item(item)['values'])
            values[0] = '☐'
            self.preview_tree.item(item, values=values)
    
    def execute_rename(self):
        """파일명 변경 실행 (선택된 파일만)"""
        if not self.results:
            messagebox.showwarning("경고", "분류 결과가 없습니다.")
            return
        
        if not self.current_directory:
            messagebox.showwarning("경고", "디렉토리가 선택되지 않았습니다.")
            return
        
        # 선택된 파일 수 확인
        selected_count = sum(1 for checked in self.preview_checkboxes.values() if checked)
        
        if selected_count == 0:
            messagebox.showinfo("알림", "선택된 파일이 없습니다.")
            return
        
        msg = f"{selected_count}개 파일의 이름을 변경하시겠습니까?\n\n"
        msg += "※ 원본 파일은 backup 폴더에 백업됩니다."
        
        if not messagebox.askyesno("확인", msg):
            return
        
        # 백업 폴더 생성
        backup_dir = os.path.join(self.current_directory, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        format_type = self.rename_format_var.get()
        success_count = 0
        renamed_items = []  # 성공적으로 변경된 항목 추적
        
        # 미리보기 트리의 항목과 결과를 매핑
        preview_items = list(self.preview_tree.get_children())
        
        # 미분류가 아닌 결과만 필터링 (미리보기 트리와 동일한 순서)
        valid_results = [r for r in self.results if r['genre'] != '미분류']
        
        for idx, item in enumerate(preview_items):
            # 체크박스가 선택되지 않은 항목은 스킵
            if not self.preview_checkboxes.get(item, False):
                continue
            
            # 인덱스 범위 확인
            if idx >= len(valid_results):
                break
            
            result = valid_results[idx]
            
            try:
                original_path = os.path.join(self.current_directory, 
                                            os.path.basename(result['filename']))
                
                if not os.path.exists(original_path):
                    continue
                
                # 백업
                backup_path = os.path.join(backup_dir, os.path.basename(result['filename']))
                shutil.copy2(original_path, backup_path)
                
                # 새 파일명 생성
                basename = os.path.basename(result['filename'])
                genre = result['genre']
                
                # 사용자가 파일명을 직접 수정했으면 그것을 사용
                if result.get('filename_edited') and result.get('custom_filename'):
                    # 사용자가 수정한 파일명 (이미 확장자 포함)
                    custom_basename = result['custom_filename']
                    name, ext = os.path.splitext(custom_basename)
                    
                    # 장르 추가 형식 적용
                    if format_type == "[장르] 제목":
                        new_name = f"[{genre}] {name}{ext}"
                    elif format_type == "제목 [장르]":
                        new_name = f"{name} [{genre}]{ext}"
                    else:  # "장르_제목"
                        new_name = f"{genre}_{name}{ext}"
                else:
                    # 기존 로직 (원본 파일명 사용)
                    if format_type == "[장르] 제목":
                        new_name = f"[{genre}] {basename}"
                    elif format_type == "제목 [장르]":
                        name, ext = os.path.splitext(basename)
                        new_name = f"{name} [{genre}]{ext}"
                    else:  # "장르_제목"
                        new_name = f"{genre}_{basename}"
                
                new_path = os.path.join(self.current_directory, new_name)
                
                # 파일명 변경
                os.rename(original_path, new_path)
                success_count += 1
                renamed_items.append(item)  # 성공한 항목 기록
                
            except Exception as e:
                print(f"오류: {result['filename']} - {str(e)}")
        
        # 성공적으로 변경된 항목들을 미리보기에서 제거
        for item in renamed_items:
            self.preview_tree.delete(item)
            if item in self.preview_checkboxes:
                del self.preview_checkboxes[item]
        
        # 분류 결과 데이터에서도 변경된 파일들 제거
        if success_count > 0:
            self._remove_renamed_files_from_results()
            self.files_renamed = True  # 파일명 변경 완료 플래그 설정
        
        messagebox.showinfo("완료", 
                          f"{success_count}개 파일 이름이 변경되었습니다.\n"
                          f"백업: {backup_dir}")
    
    def _remove_renamed_files_from_results(self):
        """파일명 변경된 파일들을 분류 결과에서 제거"""
        if not self.results:
            return
        
        # 현재 디렉토리의 파일 목록 확인
        try:
            current_files = set()
            if self.current_directory and os.path.exists(self.current_directory):
                for file in os.listdir(self.current_directory):
                    if os.path.isfile(os.path.join(self.current_directory, file)):
                        current_files.add(file)
            
            # 분류 결과에서 존재하지 않는 파일들 제거
            remaining_results = []
            removed_count = 0
            
            for result in self.results:
                original_filename = os.path.basename(result['filename'])
                if original_filename in current_files:
                    # 파일이 여전히 존재하면 유지
                    remaining_results.append(result)
                else:
                    # 파일이 없으면 제거 (파일명이 변경됨)
                    removed_count += 1
            
            # 결과 업데이트
            self.results = remaining_results
            
            # 분류 결과 트리뷰에서도 제거
            self._update_result_tree_after_rename()
            
            # 통계 업데이트
            self.update_statistics()
            
            print(f"분류 결과에서 {removed_count}개 항목 제거됨")
            
        except Exception as e:
            print(f"분류 결과 정리 중 오류: {str(e)}")
    
    def _update_result_tree_after_rename(self):
        """파일명 변경 후 분류 결과 트리뷰 업데이트"""
        if not hasattr(self, 'tree'):
            return
        
        # 현재 디렉토리의 파일 목록
        current_files = set()
        if self.current_directory and os.path.exists(self.current_directory):
            for file in os.listdir(self.current_directory):
                if os.path.isfile(os.path.join(self.current_directory, file)):
                    current_files.add(file)
        
        # 트리뷰에서 존재하지 않는 파일들 제거
        items_to_remove = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if values and len(values) > 0:
                filename = values[0]  # 첫 번째 컬럼이 파일명
                if filename not in current_files:
                    items_to_remove.append(item)
        
        # 항목 제거
        for item in items_to_remove:
            self.tree.delete(item)
    
    def restore_filenames(self):
        """파일명 복구"""
        if not self.current_directory:
            messagebox.showwarning("경고", "디렉토리가 선택되지 않았습니다.")
            return
        
        backup_dir = os.path.join(self.current_directory, "backup")
        
        if not os.path.exists(backup_dir):
            messagebox.showinfo("알림", "백업 폴더가 없습니다.")
            return
        
        backup_files = os.listdir(backup_dir)
        
        if not backup_files:
            messagebox.showinfo("알림", "백업된 파일이 없습니다.")
            return
        
        msg = f"{len(backup_files)}개 파일을 원래대로 복구하시겠습니까?"
        
        if not messagebox.askyesno("확인", msg):
            return
        
        success_count = 0
        
        for filename in backup_files:
            try:
                backup_path = os.path.join(backup_dir, filename)
                restore_path = os.path.join(self.current_directory, filename)
                
                # 기존 파일 삭제 (변경된 파일)
                if os.path.exists(restore_path):
                    os.remove(restore_path)
                
                # 백업에서 복구
                shutil.copy2(backup_path, restore_path)
                success_count += 1
                
            except Exception as e:
                print(f"오류: {filename} - {str(e)}")
        
        messagebox.showinfo("완료", f"{success_count}개 파일이 복구되었습니다.")






def main():
    """메인 함수"""
    root = tk.Tk()
    app = GenreClassifierGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    finally:
        # 로그 파일 닫기
        print()
        print(f"="*80)
        print(f"프로그램 종료")
        print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"="*80)
        
        if hasattr(sys.stdout, 'close'):
            sys.stdout.close()
            sys.stdout = sys.__stdout__


if __name__ == "__main__":
    main()
