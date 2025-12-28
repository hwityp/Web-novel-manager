# Requirements Document

## Introduction

WNAP GUI의 전면적인 UX 고도화 기능입니다. 사용자 피드백을 반영하여 '전문적인 상용 소프트웨어' 수준의 시인성과 편의성을 확보합니다. 로그 시스템 개편, 색상 대비 개선, 다이얼로그 미적 개선, 사용자 편의 기능 추가를 포함합니다.

## Glossary

- **Main_Window**: WNAP의 메인 GUI 윈도우 (gui/main_window.py)
- **Genre_Dialog**: 장르 확인을 위한 모달 다이얼로그 (gui/genre_confirm_dialog.py)
- **Pipeline_Logger**: 파이프라인 로깅 모듈 (core/pipeline_logger.py)
- **Treeview**: 처리 결과를 표시하는 테이블 위젯
- **Progress_Bar**: 진행 상황을 표시하는 프로그레스 바 위젯
- **Tooltip**: 마우스 호버 시 표시되는 도움말 팝업

## Requirements

### Requirement 1: 로그 시스템 및 레이아웃 개편

**User Story:** As a user, I want the log area removed from the main screen and the result table expanded, so that I can see more processing results at a glance while logs are saved to a file.

#### Acceptance Criteria

1. THE Main_Window SHALL completely remove the log textbox section from the main screen layout
2. THE Pipeline_Logger SHALL write detailed logs to 'logs/wnap.log' file instead of displaying on screen
3. THE Main_Window SHALL expand the Treeview height to fill the space previously occupied by the log section
4. THE Main_Window SHALL adjust grid row weights so that Treeview receives maximum vertical expansion (weight 5+)
5. WHEN the window is resized, THE Treeview SHALL expand proportionally to utilize available space

### Requirement 2: 시인성 및 색상 대비 개선

**User Story:** As a user, I want improved color contrast and readability, so that I can easily read text without eye strain in the dark theme.

#### Acceptance Criteria

1. THE Main_Window SHALL use a lighter dark gray background color (#2b2b2b or similar) instead of the current dark blue
2. THE Main_Window SHALL use pure white (#FFFFFF) or very light gray (#E0E0E0) for all text colors to maximize contrast
3. THE Treeview SHALL display clear header styling with distinct background color and bold text
4. THE Treeview SHALL display visible row separators or alternating row colors for clear row distinction
5. WHEN displaying status text, THE Main_Window SHALL use high-contrast colors that are easily distinguishable

### Requirement 3: 장르 확인 다이얼로그 미적 개선

**User Story:** As a user, I want a more spacious and readable genre confirmation dialog, so that I can quickly understand and respond to genre confirmation requests.

#### Acceptance Criteria

1. THE Genre_Dialog SHALL use font sizes 10-20% larger than the main window base font size
2. THE Genre_Dialog SHALL use increased vertical spacing (pady) between components (warning icon, title, AI recommendation, selection box)
3. THE Genre_Dialog SHALL use high contrast between background color and emphasis box color for immediate recognition of "confirmation needed" message
4. THE Genre_Dialog SHALL display the warning icon and title prominently with adequate spacing
5. WHEN displaying the dialog, THE Genre_Dialog SHALL provide a visually comfortable and spacious layout

### Requirement 4: 테이블 행 더블클릭 폴더 열기 기능

**User Story:** As a user, I want to double-click a table row to open the file's folder, so that I can quickly navigate to processed files.

#### Acceptance Criteria

1. WHEN a user double-clicks a row in the Treeview, THE Main_Window SHALL open the folder containing the corresponding file
2. THE Main_Window SHALL use the operating system's default file explorer to open the folder
3. IF the file path is not available or folder does not exist, THEN THE Main_Window SHALL display an appropriate warning message
4. THE Main_Window SHALL highlight or select the specific file in the opened folder when possible

### Requirement 5: 동적 프로그레스 바 색상

**User Story:** As a user, I want the progress bar color to change based on the current operation mode, so that I can immediately recognize whether I'm in dry-run or actual execution mode.

#### Acceptance Criteria

1. WHILE in dry-run mode, THE Progress_Bar SHALL display in sky blue color (#87CEEB or similar)
2. WHILE in actual execution mode, THE Progress_Bar SHALL display in green color (#4ade80 or similar)
3. WHEN the operation mode changes, THE Progress_Bar SHALL update its color immediately before processing starts
4. THE Progress_Bar color SHALL be clearly distinguishable between the two modes

### Requirement 6: 도움말 툴팁 기능

**User Story:** As a user, I want to see help tooltips when hovering over options, so that I can understand what each setting does without consulting documentation.

#### Acceptance Criteria

1. THE Main_Window SHALL display a help icon (?) next to each option in the settings section
2. WHEN a user hovers over a help icon or option label, THE Main_Window SHALL display a tooltip with explanation text
3. THE Tooltip SHALL appear within 500ms of hover and disappear when mouse moves away
4. THE Tooltip SHALL display clear, concise explanation text for each option (dry-run mode, log level, confirmation dialog toggle)
5. THE Tooltip SHALL have readable styling with appropriate background color and text contrast

### Requirement 7: 윈도우 상태 보존

**User Story:** As a user, I want the application to remember my window position and size, so that I don't have to resize and reposition the window every time I start the application.

#### Acceptance Criteria

1. WHEN the application closes, THE Main_Window SHALL save the current window position (x, y) and size (width, height) to 'config/gui_state.json'
2. WHEN the application starts, THE Main_Window SHALL restore the previously saved window position and size from 'config/gui_state.json'
3. IF 'config/gui_state.json' does not exist or is invalid, THEN THE Main_Window SHALL use default window dimensions (1200x900)
4. THE Main_Window SHALL validate that the restored position is within visible screen bounds before applying
5. WHEN the window is moved or resized, THE Main_Window SHALL NOT save state until application closes (to avoid excessive file writes)

