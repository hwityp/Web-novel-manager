#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Folder Organizer GUI v2.0
향상된 폴더 정리기의 그래픽 사용자 인터페이스
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import os
import sys
from pathlib import Path
import json
import logging
from datetime import datetime

# folder_organizer2 모듈 임포트
try:
    from folder_organizer2 import EnhancedFolderOrganizer, find_unrar_near_executable, find_7z_executable
    import rarfile
except ImportError:
    messagebox.showerror("오류", "folder_organizer2.py 파일을 찾을 수 없습니다.\n같은 폴더에 있는지 확인해주세요.")
    sys.exit(1)

class FolderOrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Folder Organizer v2.0 - 향상된 폴더 정리기")
        self.root.geometry("800x750")
        self.root.minsize(700, 600)
        
        # 설정 파일 경로
        self.config_file = Path("folder_organizer_config.json")
        
        # 로그 큐 (다른 스레드에서 GUI로 로그 전달)
        self.log_queue = queue.Queue()
        
        # GUI 변수들
        self.setup_variables()
        
        # GUI 구성
        self.setup_ui()
        
        # 설정 로드
        self.load_config()
        
        # 로그 모니터링 시작
        self.monitor_log_queue()
        
        # 외부 도구 감지
        self.check_external_tools()

    def setup_variables(self):
        """GUI 변수들 초기화"""
        self.source_folder = tk.StringVar()
        self.target_folder = tk.StringVar(value="정리완료")
        
        # 기본 옵션들
        self.dry_run = tk.BooleanVar()
        self.fix_extensions = tk.BooleanVar()
        self.fix_filenames = tk.BooleanVar()
        self.try_all_extensions = tk.BooleanVar()
        
        # 임계값 옵션들
        self.txt_size_threshold = tk.IntVar(value=1024*1024)  # 1MB
        self.txt_ratio_threshold = tk.DoubleVar(value=0.1)
        self.max_files_direct = tk.IntVar(value=3)
        self.min_folders_recompress = tk.IntVar(value=2)
        
        # 처리 상태
        self.is_processing = False
        self.organizer = None

    def setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 그리드 가중치 설정
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)  # 로그 섹션이 확장되도록
        
        # 제목
        title_label = ttk.Label(main_frame, text="Folder Organizer v2.0", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 폴더 선택 섹션
        self.create_folder_section(main_frame, 1)
        
        # 옵션 섹션
        self.create_options_section(main_frame, 2)
        
        # 임계값 섹션
        self.create_threshold_section(main_frame, 3)
        
        # 버튼 섹션
        self.create_button_section(main_frame, 4)
        
        # 진행률 섹션
        self.create_progress_section(main_frame, 5)
        
        # 로그 섹션
        self.create_log_section(main_frame, 6)

    def create_folder_section(self, parent, row):
        """폴더 선택 섹션"""
        folder_frame = ttk.LabelFrame(parent, text="폴더 설정", padding="10")
        folder_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        folder_frame.columnconfigure(1, weight=1)
        
        # 소스 폴더
        ttk.Label(folder_frame, text="소스 폴더:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Entry(folder_frame, textvariable=self.source_folder, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(folder_frame, text="찾아보기", command=self.browse_source_folder).grid(row=0, column=2)
        
        # 목적 폴더
        ttk.Label(folder_frame, text="목적 폴더명:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        ttk.Entry(folder_frame, textvariable=self.target_folder, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(10, 0))

    def create_options_section(self, parent, row):
        """옵션 섹션"""
        options_frame = ttk.LabelFrame(parent, text="처리 옵션", padding="10")
        options_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 첫 번째 행
        ttk.Checkbutton(options_frame, text="드라이런 모드 (시뮬레이션만)", 
                       variable=self.dry_run).grid(row=0, column=0, sticky=tk.W, padx=(0, 20))
        ttk.Checkbutton(options_frame, text="확장자 자동 수정", 
                       variable=self.fix_extensions).grid(row=0, column=1, sticky=tk.W)
        
        # 두 번째 행
        ttk.Checkbutton(options_frame, text="파일명 복구", 
                       variable=self.fix_filenames).grid(row=1, column=0, sticky=tk.W, padx=(0, 20), pady=(10, 0))
        ttk.Checkbutton(options_frame, text="모든 확장자 시도", 
                       variable=self.try_all_extensions).grid(row=1, column=1, sticky=tk.W, pady=(10, 0))

    def create_threshold_section(self, parent, row):
        """임계값 섹션"""
        threshold_frame = ttk.LabelFrame(parent, text="처리 임계값", padding="8")
        threshold_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8))
        
        # 텍스트 파일 크기 임계값
        ttk.Label(threshold_frame, text="텍스트 파일 크기 임계값 (MB):").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        size_spinbox = ttk.Spinbox(threshold_frame, from_=0.1, to=100.0, increment=0.1, 
                                  textvariable=tk.DoubleVar(value=1.0), width=8,
                                  command=self.update_txt_size_threshold)
        size_spinbox.grid(row=0, column=1, sticky=tk.W, padx=(0, 15))
        self.size_spinbox = size_spinbox
        
        # 텍스트 파일 비율 임계값
        ttk.Label(threshold_frame, text="텍스트 파일 비율 임계값:").grid(row=0, column=2, sticky=tk.W, padx=(0, 8))
        ratio_spinbox = ttk.Spinbox(threshold_frame, from_=0.01, to=1.0, increment=0.01, 
                                   textvariable=self.txt_ratio_threshold, width=8)
        ratio_spinbox.grid(row=0, column=3, sticky=tk.W)
        
        # 직접 이동할 최대 파일 수
        ttk.Label(threshold_frame, text="직접 이동할 최대 파일 수:").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(8, 0))
        max_files_spinbox = ttk.Spinbox(threshold_frame, from_=1, to=20, increment=1, 
                                       textvariable=self.max_files_direct, width=8)
        max_files_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(0, 15), pady=(8, 0))
        
        # 재압축할 최소 폴더 수
        ttk.Label(threshold_frame, text="재압축할 최소 폴더 수:").grid(row=1, column=2, sticky=tk.W, padx=(0, 8), pady=(8, 0))
        min_folders_spinbox = ttk.Spinbox(threshold_frame, from_=2, to=20, increment=1, 
                                         textvariable=self.min_folders_recompress, width=8)
        min_folders_spinbox.grid(row=1, column=3, sticky=tk.W, pady=(8, 0))

    def create_button_section(self, parent, row):
        """버튼 섹션"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=0, columnspan=3, pady=(0, 8))
        
        # 시작 버튼
        self.start_button = ttk.Button(button_frame, text="정리 시작", 
                                      command=self.start_processing, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=(0, 8))
        
        # 중지 버튼
        self.stop_button = ttk.Button(button_frame, text="중지", 
                                     command=self.stop_processing, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=(0, 8))
        
        # 설정 저장 버튼
        ttk.Button(button_frame, text="설정 저장", 
                  command=self.save_config).pack(side=tk.LEFT, padx=(0, 8))
        
        # 설정 로드 버튼
        ttk.Button(button_frame, text="설정 로드", 
                  command=self.load_config).pack(side=tk.LEFT, padx=(0, 8))
        
        # 도움말 버튼
        ttk.Button(button_frame, text="도움말", 
                  command=self.show_help).pack(side=tk.LEFT)

    def create_progress_section(self, parent, row):
        """진행률 섹션"""
        progress_frame = ttk.LabelFrame(parent, text="진행 상태", padding="8")
        progress_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8))
        progress_frame.columnconfigure(0, weight=1)
        
        # 진행률 바
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # 상태 라벨
        self.status_label = ttk.Label(progress_frame, text="대기 중...")
        self.status_label.grid(row=1, column=0, sticky=tk.W)

    def create_log_section(self, parent, row):
        """로그 섹션"""
        log_frame = ttk.LabelFrame(parent, text="처리 로그", padding="8")
        log_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 8))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 로그 텍스트 위젯 (높이를 줄이고 패딩 조정)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
        
        # 로그 버튼들
        log_button_frame = ttk.Frame(log_frame)
        log_button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Button(log_button_frame, text="로그 지우기", 
                  command=self.clear_log).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(log_button_frame, text="로그 저장", 
                  command=self.save_log).pack(side=tk.LEFT)

    def update_txt_size_threshold(self):
        """텍스트 파일 크기 임계값 업데이트"""
        try:
            value = float(self.size_spinbox.get())
            self.txt_size_threshold.set(int(value * 1024 * 1024))  # MB를 바이트로 변환
        except ValueError:
            pass

    def browse_source_folder(self):
        """소스 폴더 선택"""
        folder = filedialog.askdirectory(title="소스 폴더 선택")
        if folder:
            self.source_folder.set(folder)

    def check_external_tools(self):
        """외부 도구 감지 및 상태 표시"""
        # UnRAR 감지
        find_unrar_near_executable()
        unrar_available = hasattr(rarfile, 'UNRAR_TOOL') and rarfile.UNRAR_TOOL
        
        # 7-Zip 감지
        seven_zip_path = find_7z_executable()
        
        status_text = "외부 도구 상태: "
        if unrar_available:
            status_text += "UnRAR ✓ "
        else:
            status_text += "UnRAR ✗ "
            
        if seven_zip_path:
            status_text += "7-Zip ✓"
        else:
            status_text += "7-Zip ✗"
            
        self.log_message(status_text)

    def start_processing(self):
        """처리 시작"""
        if not self.source_folder.get():
            messagebox.showerror("오류", "소스 폴더를 선택해주세요.")
            return
            
        if not os.path.exists(self.source_folder.get()):
            messagebox.showerror("오류", "선택한 소스 폴더가 존재하지 않습니다.")
            return
        
        # UI 상태 변경
        self.is_processing = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.progress_var.set(0)
        self.status_label.config(text="처리 중...")
        
        # 백그라운드 스레드에서 처리 실행
        self.processing_thread = threading.Thread(target=self.run_processing)
        self.processing_thread.daemon = True
        self.processing_thread.start()

    def run_processing(self):
        """실제 처리 실행 (백그라운드 스레드)"""
        try:
            # EnhancedFolderOrganizer 인스턴스 생성
            self.organizer = EnhancedFolderOrganizer(
                source_folder=self.source_folder.get(),
                target_folder=self.target_folder.get(),
                dry_run=self.dry_run.get(),
                fix_extensions=self.fix_extensions.get(),
                fix_filenames=self.fix_filenames.get(),
                try_all_extensions=self.try_all_extensions.get(),
                txt_size_threshold=self.txt_size_threshold.get(),
                txt_ratio_threshold=self.txt_ratio_threshold.get(),
                max_files_direct=self.max_files_direct.get(),
                min_folders_recompress=self.min_folders_recompress.get()
            )
            
            # 로거 설정 (GUI로 로그 전달)
            self.setup_logger()
            
            # 처리 실행
            self.organizer.organize_folders()
            
            # 완료 메시지
            self.log_message("\n=== 처리 완료 ===")
            self.log_message(f"확장자 수정: {self.organizer.stats['extensions_fixed']}개")
            self.log_message(f"파일명 복구: {self.organizer.stats['filenames_fixed']}개")
            self.log_message(f"시그니처 감지: {self.organizer.stats['signatures_detected']}개")
            self.log_message(f"압축 파일 처리: {self.organizer.stats['archives_processed']}개")
            
        except Exception as e:
            self.log_message(f"오류 발생: {str(e)}")
        finally:
            # UI 상태 복원
            self.root.after(0, self.processing_finished)

    def setup_logger(self):
        """로거 설정 (GUI로 로그 전달)"""
        class GUILogHandler(logging.Handler):
            def __init__(self, log_queue):
                super().__init__()
                self.log_queue = log_queue
                
            def emit(self, record):
                log_entry = self.format(record)
                self.log_queue.put(log_entry)
        
        # 기존 핸들러 제거
        for handler in self.organizer.logger.handlers[:]:
            self.organizer.logger.removeHandler(handler)
        
        # GUI 핸들러 추가
        gui_handler = GUILogHandler(self.log_queue)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.organizer.logger.addHandler(gui_handler)
        self.organizer.logger.setLevel(logging.INFO)

    def stop_processing(self):
        """처리 중지"""
        self.is_processing = False
        self.log_message("사용자에 의해 중지됨...")
        self.processing_finished()

    def processing_finished(self):
        """처리 완료 후 UI 상태 복원"""
        self.is_processing = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.progress_var.set(100)
        self.status_label.config(text="완료")

    def monitor_log_queue(self):
        """로그 큐 모니터링 (GUI 업데이트)"""
        try:
            while True:
                log_entry = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, log_entry + "\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        
        # 100ms마다 다시 체크
        self.root.after(100, self.monitor_log_queue)

    def log_message(self, message):
        """로그 메시지 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_text.insert(tk.END, log_entry + "\n")
        self.log_text.see(tk.END)

    def clear_log(self):
        """로그 지우기"""
        self.log_text.delete(1.0, tk.END)

    def save_log(self):
        """로그 저장"""
        filename = filedialog.asksaveasfilename(
            title="로그 저장",
            defaultextension=".txt",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("성공", "로그가 저장되었습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"로그 저장 실패: {str(e)}")

    def save_config(self):
        """설정 저장"""
        config = {
            "source_folder": self.source_folder.get(),
            "target_folder": self.target_folder.get(),
            "dry_run": self.dry_run.get(),
            "fix_extensions": self.fix_extensions.get(),
            "fix_filenames": self.fix_filenames.get(),
            "try_all_extensions": self.try_all_extensions.get(),
            "txt_size_threshold": self.txt_size_threshold.get(),
            "txt_ratio_threshold": self.txt_ratio_threshold.get(),
            "max_files_direct": self.max_files_direct.get(),
            "min_folders_recompress": self.min_folders_recompress.get()
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("성공", "설정이 저장되었습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 실패: {str(e)}")

    def load_config(self):
        """설정 로드"""
        if not self.config_file.exists():
            return
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.source_folder.set(config.get("source_folder", ""))
            self.target_folder.set(config.get("target_folder", "정리완료"))
            self.dry_run.set(config.get("dry_run", False))
            self.fix_extensions.set(config.get("fix_extensions", False))
            self.fix_filenames.set(config.get("fix_filenames", False))
            self.try_all_extensions.set(config.get("try_all_extensions", False))
            self.txt_size_threshold.set(config.get("txt_size_threshold", 1024*1024))
            self.txt_ratio_threshold.set(config.get("txt_ratio_threshold", 0.1))
            self.max_files_direct.set(config.get("max_files_direct", 3))
            self.min_folders_recompress.set(config.get("min_folders_recompress", 2))
            
            # 스핀박스 값 업데이트
            self.size_spinbox.delete(0, tk.END)
            self.size_spinbox.insert(0, str(self.txt_size_threshold.get() / (1024*1024)))
            
        except Exception as e:
            messagebox.showerror("오류", f"설정 로드 실패: {str(e)}")

    def show_help(self):
        """도움말 표시"""
        help_text = """
Folder Organizer v2.0 도움말

=== 기본 사용법 ===
1. 소스 폴더를 선택하세요
2. 목적 폴더명을 입력하세요 (기본: 정리완료)
3. 필요한 옵션을 선택하세요
4. '정리 시작' 버튼을 클릭하세요

=== 옵션 설명 ===
• 드라이런 모드: 실제 파일 조작 없이 시뮬레이션만 실행
• 확장자 자동 수정: 잘못된 확장자를 자동으로 수정
• 파일명 복구: 깨진 파일명을 복구 시도
• 모든 확장자 시도: 시그니처 기반으로 모든 확장자 조합 시도

=== 임계값 설정 ===
• 텍스트 파일 크기 임계값: 단일 텍스트 파일 추출 기준 (MB)
• 텍스트 파일 비율 임계값: 최대 텍스트 대비 2위 텍스트 비율
• 직접 이동할 최대 파일 수: 폴더 없이 직접 이동할 최대 파일 수
• 재압축할 최소 폴더 수: 개별 ZIP으로 재압축할 최소 폴더 수

=== 외부 도구 ===
• UnRAR: RAR 파일 처리용 (WinRAR 설치 필요)
• 7-Zip: ZIPX 및 특수 압축 파일 처리용

=== 주의사항 ===
• 처리 전에 중요한 데이터는 백업하세요
• 드라이런 모드로 먼저 테스트해보세요
• 설정은 자동으로 저장/로드됩니다
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("도움말")
        help_window.geometry("600x500")
        help_window.resizable(False, False)
        
        text_widget = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)
        
        ttk.Button(help_window, text="닫기", command=help_window.destroy).pack(pady=10)

def main():
    """메인 함수"""
    root = tk.Tk()
    
    # 스타일 설정
    style = ttk.Style()
    style.theme_use('clam')
    
    # 앱 실행
    app = FolderOrganizerGUI(root)
    
    # 창 닫기 이벤트 처리
    def on_closing():
        if app.is_processing:
            if messagebox.askokcancel("종료", "처리가 진행 중입니다. 정말 종료하시겠습니까?"):
                app.is_processing = False
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # GUI 시작
    root.mainloop()

if __name__ == "__main__":
    main()
