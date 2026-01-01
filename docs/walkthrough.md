# WNAP v1.3.7 Hotfix: Normalization Order

## 1. "Side Story + Epilogue" Extraction Fix (Completed)
- **Root Cause Analysis**: 
    - The Main GUI uses `TitleAnchorExtractor` (in `core/title_anchor_extractor.py`), **NOT** legacy `rename_normalize.py`.
    - `TitleAnchorExtractor` failed to handle multiple side story markers (e.g., "Epilogue AND Side Story") because it used a single check instead of a loop.
    - It also lacked logic to remove connectors like "및" (and) or "포함" (include), preventing parsing of "에필 및 외전".
- **Fix**: 
    - **Global Noise Removal**: Added pre-cleaning step in `_parse_residual` to remove "및", "포함", "comp", "only".
    - **Loop Extraction**: Converted single-check side story extraction to a `while` loop to capture ALL markers (e.g., "에필", "외전").
- **Verification**: `check_title_extractor.py` confirmed that "회귀했더니 입대 전날 1-529 完 에필 및 외전 포함.txt" is parsed as **"Side Story: '에필, 외전'"**.


---


## 1. Windows Path Handling Fix (Verified)
- **Problem**: `shutil.copy2` failed with `FileNotFoundError` for filenames with trailing spaces (e.g., `"file .txt"`), as Windows APIs strip them by default.
- **Fix**: Implemented robust path handling in `PipelineOrchestrator._move_file`.
- **Method**: Automatically prepends `\\?\` to absolute paths on Windows (e.g., `\\?\C:\Path\To\file .txt`), which forces the API to use the exact raw path without normalization.

---


## 1. Normalization Logic Refinement (Verified)
- **Objective**: Ensure "외전", "에필로그" are preserved even with noise like "및", "포함".
- **Test Case**: `회귀했더니 입대 전날 1-529 完 에필 및 외전 포함.txt`
- **Result Log**:
  ```
  Testing: 회귀했더니 입대 전날 1-529 完 에필 및 외전 포함.txt
  Result: [현판] 회귀했더니 입대 전날 1-529 (완) + 외전,  에필.txt
  SUCCESS: Both '에필' and '외전' preserved.
  ```
- **Fix**: Added regex preprocessing to clean `및` and `포함` before extraction.

## 2. Genre Preservation (Optimized)
- **Objective**: Skip API search if `[Genre]` tag exists.
- **Implementation**: `GenreClassifierAdapter` now checks for tags like `[선협]` and maps them using `GENRE_WHITELIST`.

## 3. CSV Path Fixed
- **Objective**: Save `mapping_*.csv` to Main Program Root.
- **Implementation**: Uses `get_base_path()` in `pipeline_orchestrator.py`.
- **Verification**: `Base Path Check: C:\Users\hwity\Cursor_Work\WebNovelManager`

---
# WNAP v1.3.2 Update

GUI layout optimized and CLI options integrated for advanced control.

## New Features (v1.3.2)

### 1. CLI / Terminal Integration
GUI를 터미널에서 실행할 때 `log-level`을 제어할 수 있습니다.
- **Command**: `python main_gui.py --log-level DEBUG`
- **Benefit**: 터미널에서 상세한 디버그 로그를 실시간으로 확인하며 트러블슈팅 가능.

### 2. GUI Layout Refactoring
- **Expanded Table**: 상단의 '실행 옵션' 프레임을 제거하고, 확보된 공간만큼 **결과 테이블을 확장**했습니다.
- **Enhanced Visibility**:
    - **Font Size**: 테이블 폰트 크기를 **1.2배 확대**하여 가독성 강화.
    - **Maximized Column**: '정규화 파일명' 컬럼이 남은 공간을 모두 차지하여 긴 제목도 잘림 없이 표시됩니다.
- **Button Styling**:
    - **[▶️ 실행 (Rename)]**: **녹색(Green)** + Bold 텍스트로 변경하여 "최종 실행"임을 명확히 강조.
    - **[⚡ 일괄 처리]**: **청색(Blue)** 계열로 변경하여 실행 버튼과 시각적 구분.

## New Features (v1.3.3)

### 3. Batch Processing Real-time Updates
일괄 처리 시 답답했던 UI 멈춤 현상을 해결했습니다.
- **실시간 테이블 갱신**: 장르 추론이 끝날 때마다 테이블의 장르/신뢰도/판단근거가 즉시 채워집니다.
- **상태별 컬러링(Coloring)**:
    - **성공(Renamed)**: 짙은 녹색 배경 (#1E3A2A)으로 성공 여부 직관적 확인.
    - **건너뜀(Skipped)**: 회색 배경 (#404040)으로 처리 제외 항목 구분.
- **안전 팝업(Safety Popup)**: '일괄 처리' 중이라도 실제 파일 변경 직전에 "총 N개 파일을 변경하시겠습니까?" 팝업을 띄워 실수를 방지합니다.

## New Features (v1.3.4)

### 4. Dual Logging System
목적에 따라 로그 파일을 이원화했습니다.
- **`wnap.log`**: 핵심 요약용 (항상 INFO 레벨 고정). 이전 기록과 간단한 실행 이력을 확인하기 좋습니다.
- **`wnap_YYYYMMDD.log`**: 상세 분석용. `--log-level DEBUG` 등으로 설정한 상세 로그가 여기에 모두 기록됩니다.

## Usage Guide (Updated)
1.  **[1. 폴더 정리]**: 파일 스캔.
2.  **[2. 파일명 정규화]**: 제목 파싱.
3.  **[3. 장르 추론]**: AI 검색 수행 (테이블 갱신).
4.  **[▶️ 실행 (Rename)]**: 녹색 버튼 클릭 -> 최종 파일 이름 변경.

### Advanced
- 디버깅이 필요한 경우 터미널에서 `--log-level DEBUG` 옵션을 사용하세요.
