# Requirements Document

## Introduction

WNAP(Web Novel Archive Pipeline) GUI의 시인성과 UX를 프로페셔널한 수준으로 개선하는 기능입니다. 타이포그래피, 레이아웃, 시각적 피드백, 장르 확인 다이얼로그 등 전반적인 UI/UX를 현대적이고 세련되게 개편합니다.

## Glossary

- **Main_Window**: WNAP의 메인 GUI 윈도우 (gui/main_window.py)
- **Genre_Dialog**: 장르 확인을 위한 모달 다이얼로그 (gui/genre_confirm_dialog.py)
- **Dashboard_Widget**: 실행 결과 요약을 표시하는 카드 형태의 위젯
- **Card_Style**: 경계선과 배경색으로 구분되는 섹션 스타일
- **Treeview**: 처리 결과를 표시하는 테이블 위젯
- **Font_Fallback**: 폰트 우선순위 전략 (NanumGothic -> Segoe UI -> Malgun Gothic -> sans-serif)

## Requirements

### Requirement 1: 타이포그래피 및 가독성 개선

**User Story:** As a user, I want improved typography and readability, so that I can easily read and understand the interface without eye strain.

#### Acceptance Criteria

1. THE Main_Window SHALL use a base font size of 14pt for standard labels and 18pt or larger for section titles with bold weight
2. THE Main_Window SHALL apply Font_Fallback strategy: NanumGothic -> Segoe UI -> Malgun Gothic -> sans-serif
3. THE Log_Textbox SHALL use 13pt Consolas monospace font with clear background-text contrast
4. THE Treeview SHALL use system Gothic font with increased row height (30px) for readability
5. WHEN displaying text content, THE Main_Window SHALL maintain high contrast between text and background colors

### Requirement 2: 레이아웃 구조 개편 및 반응형 설계

**User Story:** As a user, I want a well-organized layout with clear visual separation and responsive behavior, so that I can quickly locate features and resize the window freely.

#### Acceptance Criteria

1. THE Main_Window SHALL display folder settings and execution options sections at the top with Card_Style borders and subtle background differentiation
2. THE Main_Window SHALL display a Dashboard_Widget in the upper-right area with statistics numbers in 20pt+ bold font
3. THE Main_Window SHALL keep top settings sections at fixed height while Treeview and log sections expand flexibly
4. THE Treeview SHALL have optimized column widths and increased height allocation
5. WHEN window is resized, THE Main_Window SHALL expand Treeview and log sections using proper sticky and weight configurations

### Requirement 3: 장르 확인 다이얼로그 고도화

**User Story:** As a user, I want a refined genre confirmation dialog, so that I can easily confirm or select genres with clear visual guidance.

#### Acceptance Criteria

1. THE Genre_Dialog SHALL display a prominent warning icon in the title section
2. THE Genre_Dialog SHALL display the filename in a highlighted emphasis box with distinct background color
3. THE Genre_Dialog SHALL use enlarged combo box (width 250px+) for genre selection
4. THE Genre_Dialog SHALL use enlarged buttons (height 45px+) for easy clicking
5. WHEN displaying the dialog, THE Genre_Dialog SHALL center itself on the parent window with proper modal behavior

### Requirement 4: 시각적 피드백 및 제어 로직

**User Story:** As a user, I want adequate spacing, modern button designs, and proper control states, so that the interface feels spacious and prevents accidental operations.

#### Acceptance Criteria

1. THE Main_Window SHALL use padding of 10-15 pixels between widgets for visual breathing room
2. THE Main_Window SHALL display run button in green and preview button in blue with rounded corners
3. WHEN hovering over buttons, THE Main_Window SHALL provide visual feedback through color change
4. WHILE pipeline is running, THE Main_Window SHALL disable source/target browse buttons and save settings button
5. WHEN pipeline completes, THE Main_Window SHALL re-enable all previously disabled controls
