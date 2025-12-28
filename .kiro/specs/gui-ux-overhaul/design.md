# Design Document: GUI UX Overhaul

## Overview

이 설계 문서는 WNAP GUI의 전면적인 UX 고도화를 위한 기술적 설계를 정의합니다. 주요 목표는 '전문적인 상용 소프트웨어' 수준의 시인성과 편의성을 확보하는 것입니다.

핵심 변경사항:
1. 로그 시스템 개편 - 화면 로그 제거, 파일 로깅으로 전환
2. 색상 대비 개선 - 밝은 다크 테마 적용
3. 장르 다이얼로그 미적 개선 - 폰트 및 간격 확대
4. 사용자 편의 기능 - 더블클릭 폴더 열기, 동적 프로그레스 바, 툴팁
5. 윈도우 상태 보존 - 위치/크기 기억

## Architecture

### 시스템 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    WNAPMainWindow                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Top Section: Folder Card + Dashboard Widget         │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Options Section: Settings + Help Tooltips           │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Result Table Section (Expanded - weight 5)          │   │
│  │ - Treeview with double-click handler                │   │
│  │ - Dynamic progress bar (color by mode)              │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Action Buttons Section                              │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  WindowStateManager ←→ config/gui_state.json               │
│  TooltipManager ←→ Help Icons                              │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    PipelineLogger                           │
│  - File-only logging to logs/wnap.log                      │
│  - RotatingFileHandler (10MB, 5 backups)                   │
│  - No console output in GUI mode                           │
└─────────────────────────────────────────────────────────────┘
```

### 레이아웃 아키텍처 (Requirement 1)

기존 레이아웃에서 로그 섹션(row 3)을 제거하고 Treeview 섹션의 weight를 확장합니다.

```python
# 기존 레이아웃
self.grid_rowconfigure(0, weight=0)  # 상단 카드 (고정)
self.grid_rowconfigure(1, weight=0)  # 옵션 섹션 (고정)
self.grid_rowconfigure(2, weight=3)  # 결과 테이블 (확장)
self.grid_rowconfigure(3, weight=2)  # 로그 영역 (확장) ← 제거
self.grid_rowconfigure(4, weight=0)  # 버튼 영역 (고정)

# 새 레이아웃
self.grid_rowconfigure(0, weight=0)  # 상단 카드 (고정)
self.grid_rowconfigure(1, weight=0)  # 옵션 섹션 (고정)
self.grid_rowconfigure(2, weight=5)  # 결과 테이블 + 프로그레스 (최대 확장)
self.grid_rowconfigure(3, weight=0)  # 버튼 영역 (고정)
```

### 로깅 아키텍처

```python
# PipelineLogger 설정 (GUI 모드)
logger = PipelineLogger(
    log_level="INFO",
    log_dir=Path("logs"),
    log_filename="wnap.log",
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5,
    console_output=False  # GUI 모드에서는 콘솔 출력 비활성화
)
```

## Components and Interfaces

### 1. 테마 딕셔너리 (Theme Dictionary)

```python
# 새로운 고대비 테마 상수
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
    "table_border": "#505050",
    
    # 툴팁 색상
    "tooltip_bg": "#1e1e1e",
    "tooltip_text": "#FFFFFF",
    "tooltip_border": "#4A90D9",
}
```

### 2. Treeview 스타일 설정

```python
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
        borderwidth=1,
        relief="solid"
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
        background=[("selected", THEME["accent_blue"])],
        foreground=[("selected", THEME["text_primary"])]
    )
    
    # 행 구분을 위한 태그 설정
    self.result_tree.tag_configure("oddrow", background=THEME["table_row_odd"])
    self.result_tree.tag_configure("evenrow", background=THEME["table_row_even"])
```

### 3. TooltipManager 클래스

```python
class TooltipManager:
    """비차단 툴팁 관리자"""
    
    def __init__(self, widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self.scheduled_id = None
        
        widget.bind("<Enter>", self._schedule_show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)
    
    def _schedule_show(self, event):
        """지연 후 툴팁 표시 예약"""
        self._hide()
        self.scheduled_id = self.widget.after(self.delay, self._show)
    
    def _show(self):
        """툴팁 표시"""
        if self.tooltip_window:
            return
        
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        frame = tk.Frame(
            self.tooltip_window,
            background=THEME["tooltip_bg"],
            borderwidth=1,
            relief="solid",
            highlightbackground=THEME["tooltip_border"],
            highlightthickness=1
        )
        frame.pack()
        
        label = tk.Label(
            frame,
            text=self.text,
            background=THEME["tooltip_bg"],
            foreground=THEME["tooltip_text"],
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            padx=8,
            pady=4,
            wraplength=300,
            justify="left"
        )
        label.pack()
    
    def _hide(self, event=None):
        """툴팁 숨기기"""
        if self.scheduled_id:
            self.widget.after_cancel(self.scheduled_id)
            self.scheduled_id = None
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
```

### 4. WindowStateManager 클래스

```python
class WindowStateManager:
    """윈도우 상태 저장/복원 관리자"""
    
    STATE_FILE = Path("config/gui_state.json")
    DEFAULT_GEOMETRY = "1200x900"
    
    @classmethod
    def load_state(cls) -> dict:
        """저장된 윈도우 상태 로드"""
        try:
            if cls.STATE_FILE.exists():
                with open(cls.STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}
    
    @classmethod
    def save_state(cls, window: ctk.CTk):
        """현재 윈도우 상태 저장"""
        try:
            cls.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "geometry": window.geometry(),
                "x": window.winfo_x(),
                "y": window.winfo_y(),
                "width": window.winfo_width(),
                "height": window.winfo_height()
            }
            with open(cls.STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except IOError:
            pass
    
    @classmethod
    def restore_state(cls, window: ctk.CTk):
        """윈도우 상태 복원 (화면 범위 검증 포함)"""
        state = cls.load_state()
        if not state:
            window.geometry(cls.DEFAULT_GEOMETRY)
            return
        
        # 화면 범위 검증
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        x = state.get("x", 0)
        y = state.get("y", 0)
        width = state.get("width", 1200)
        height = state.get("height", 900)
        
        # 최소 100px는 화면에 보이도록 보정
        x = max(0, min(x, screen_width - 100))
        y = max(0, min(y, screen_height - 100))
        width = min(width, screen_width)
        height = min(height, screen_height)
        
        window.geometry(f"{width}x{height}+{x}+{y}")
```

### 5. 더블클릭 폴더 열기 핸들러

```python
def _on_treeview_double_click(self, event):
    """Treeview 행 더블클릭 시 폴더 열기"""
    selection = self.result_tree.selection()
    if not selection:
        return
    
    item = selection[0]
    values = self.result_tree.item(item, "values")
    
    # 원본 파일명에서 경로 추출 시도
    if not values:
        return
    
    # 태스크에서 실제 경로 찾기
    original_name = values[0]
    file_path = self._find_file_path_by_name(original_name)
    
    if not file_path:
        messagebox.showwarning("경고", "파일 경로를 찾을 수 없습니다.")
        return
    
    folder_path = file_path.parent
    if not folder_path.exists():
        messagebox.showwarning("경고", f"폴더가 존재하지 않습니다:\n{folder_path}")
        return
    
    # OS별 폴더 열기 (파일 선택 포함)
    self._open_folder_and_select_file(folder_path, file_path)

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
    except Exception as e:
        messagebox.showerror("오류", f"폴더를 열 수 없습니다:\n{e}")
```

### 6. 동적 프로그레스 바 색상

```python
def _update_progress_bar_color(self, dry_run: bool):
    """실행 모드에 따른 프로그레스 바 색상 변경"""
    if dry_run:
        color = THEME["progress_dryrun"]  # 하늘색
    else:
        color = THEME["progress_execute"]  # 초록색
    
    self.progress_bar.configure(progress_color=color)
```

## Data Models

### GUI State JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "geometry": {
      "type": "string",
      "description": "Window geometry string (WxH+X+Y)"
    },
    "x": {
      "type": "integer",
      "description": "Window X position"
    },
    "y": {
      "type": "integer",
      "description": "Window Y position"
    },
    "width": {
      "type": "integer",
      "description": "Window width"
    },
    "height": {
      "type": "integer",
      "description": "Window height"
    }
  }
}
```

### Tooltip Configuration

```python
TOOLTIP_TEXTS = {
    "dry_run": "Dry-run 모드: 실제 파일을 이동하지 않고 미리보기만 수행합니다.\n결과를 확인한 후 실제 실행을 진행하세요.",
    "log_level": "로그 레벨: 기록할 로그의 상세 수준을 설정합니다.\n- DEBUG: 모든 상세 정보\n- INFO: 일반 정보\n- WARNING: 경고만\n- ERROR: 오류만",
    "confirm_dialog": "실행 전 확인: 파이프라인 실행 전에 확인 대화상자를 표시합니다.\n실수로 인한 파일 이동을 방지합니다.",
    "save_settings": "현재 설정을 저장합니다.\n다음 실행 시 자동으로 불러옵니다."
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Log File Writing

*For any* log message generated during pipeline execution, the message SHALL be written to 'logs/wnap.log' file with proper timestamp and level formatting.

**Validates: Requirements 1.2**

### Property 2: Text Color Consistency

*For any* text widget in the Main_Window, the text color SHALL be either pure white (#FFFFFF) or very light gray (#E0E0E0) to ensure high contrast against the dark background.

**Validates: Requirements 2.2**

### Property 3: Dialog Font Size Increase

*For any* font used in the Genre_Dialog, the font size SHALL be 10-20% larger than the corresponding base font size used in the Main_Window.

**Validates: Requirements 3.1**

### Property 4: Double-Click Folder Opening

*For any* row in the Treeview with a valid file path, double-clicking the row SHALL trigger the operating system's file explorer to open the containing folder.

**Validates: Requirements 4.1**

### Property 5: Progress Bar Mode Color

*For any* execution mode (dry-run or actual), the Progress_Bar color SHALL match the mode-specific color: sky blue (#87CEEB) for dry-run, green (#4ade80) for actual execution.

**Validates: Requirements 5.1, 5.2**

### Property 6: Tooltip Display on Hover

*For any* help icon in the settings section, hovering over the icon SHALL display a tooltip with explanation text within 500ms.

**Validates: Requirements 6.2**

### Property 7: Window State Round-Trip

*For any* valid window position and size, saving the state on close and restoring on next launch SHALL result in the same window geometry (within screen bounds).

**Validates: Requirements 7.1, 7.2**

### Property 8: Window Position Bounds Validation

*For any* restored window position, the position SHALL be validated to ensure at least 100 pixels of the window are visible on the screen.

**Validates: Requirements 7.4**

## Error Handling

### 파일 시스템 오류

| 오류 상황 | 처리 방법 |
|----------|----------|
| 로그 디렉토리 생성 실패 | 콘솔에 경고 출력, 로깅 비활성화 |
| gui_state.json 읽기 실패 | 기본 윈도우 크기 사용 |
| gui_state.json 쓰기 실패 | 무시 (다음 실행 시 기본값 사용) |
| 폴더 열기 실패 | 사용자에게 오류 메시지 표시 |

### UI 오류

| 오류 상황 | 처리 방법 |
|----------|----------|
| 더블클릭 시 파일 경로 없음 | 경고 메시지 표시 |
| 폴더가 존재하지 않음 | 경고 메시지 표시 |
| 툴팁 생성 실패 | 무시 (기능 저하 허용) |

## Testing Strategy

### Unit Tests

단위 테스트는 개별 컴포넌트의 동작을 검증합니다:

1. **WindowStateManager 테스트**
   - 상태 저장/로드 기능
   - 잘못된 JSON 처리
   - 화면 범위 검증

2. **TooltipManager 테스트**
   - 툴팁 표시/숨김 타이밍
   - 다중 툴팁 관리

3. **테마 적용 테스트**
   - 색상 상수 유효성
   - 스타일 설정 적용

### Property-Based Tests

속성 기반 테스트는 Hypothesis 라이브러리를 사용하여 구현합니다:

1. **Property 1**: 로그 파일 쓰기 검증
   - 임의의 로그 메시지 생성
   - 파일에 기록 확인

2. **Property 5**: 프로그레스 바 색상 검증
   - dry_run True/False에 따른 색상 확인

3. **Property 7**: 윈도우 상태 라운드트립
   - 임의의 위치/크기 생성
   - 저장 후 복원 시 동일성 확인

4. **Property 8**: 위치 범위 검증
   - 화면 밖 위치 생성
   - 보정 후 화면 내 위치 확인

### Integration Tests

통합 테스트는 GUI 컴포넌트 간 상호작용을 검증합니다:

1. 전체 레이아웃 렌더링
2. 이벤트 바인딩 동작
3. 설정 저장/로드 흐름

### Testing Framework

- **Framework**: pytest + hypothesis
- **Minimum iterations**: 100 per property test
- **Tag format**: `Feature: gui-ux-overhaul, Property {number}: {property_text}`
