# WNAP v1.3.1 Tasks

- [x] Refactor GUI: `run_with_existing_tasks`
- [x] Fix `GoogleGenreExtractor`: Circuit Breaker & Syntax
- [x] Verify Fixes
- [x] Refactor Pipeline Order (Normalize -> Search)
- [x] Finalize Dialog UI (Dynamic Height)
- [x] WNAP v1.3.0 GUI Refactor
    - [x] Update `PipelineOrchestrator` for Granular Execution (Stage 1, 1.5, 2+3)
    - [x] Update `main_window.py`: Remove Old Buttons
    - [x] Add 5 New Buttons (Folder, Normalize, Genre, Batch, Reset)
    - [x] Implement State Management Logic
    - [x] Implement Editable Treeview Logic
    - [x] Implement Smart Batch Filtering
    - [x] Verify End-to-End Workflow & Release
- [x] WNAP v1.3.1 GUI Refactor (UX Polish)
    - [x] Pre-filled Dialog for Editing
    - [x] Split Genre/Execute Button (State Machine)
    - [x] Remove `[미분류]` Tag in Table
    - [x] Real-time Data Binding in Progress
    - [x] Optimize Dialog Layout (Auto Height)
- [x] Logic Restoration & Logging (v1.3.1 Hotfix)
    - [x] Restore NovelNet (ssn.so) Filtering (Blacklist/Whitelist)
    - [x] Implement Date-based Logging (`wnap_YYYYMMDD.log`)
    - [x] Verify Log Encoding (UTF-8)
- [x] WNAP v1.3.2 GUI Refactor & CLI Integration
    - [x] CLI Integration (`--log-level`)
    - [x] GUI Refactoring (Remove Options, Layout, Table, Buttons)
    - [x] Verification
- [x] WNAP v1.3.2 Hotfix
    - [x] Button Visibility (Bright Text)
    - [x] Table Adjustment (Column Widths 1.5x)
- [x] WNAP v1.3.3 Tasks
    - [x] Batch Processing Real-time Updates
    - [x] Verification
- [x] WNAP v1.3.4 Tasks
    - [x] Dual Logging System
    - [x] `wnap.log`: Concise/Simple Log (INFO fixed)
    - [x] `wnap_YYYYMMDD.log`: Detailed Daily Log (Fixed to DEBUG to capture terminal details)
    - [x] Update `PipelineLogger` to use dual handlers
    - [x] Capture `GenreClassifier` terminal output in daily logs
    - [x] Capture Terminal Output (Re-verified & Formatted)
    - [x] Sync Links in Log vs Terminal (NaverExtractor Instrumented)
- [x] WNAP v1.3.5 Hotfix
    - [x] Fix Startup Crash (AttributeError)
        - [x] Move `tag_configure` after Treeview init
    - [x] Fix Batch Runtime Crash (AttributeError)
        - [x] Instantiate `orchestrator` locally in `_execute_batch`

# WNAP v1.3.6 Hotfix [current]
- [x] Fix NameError (formatter undefined)
    - [x] Restore `formatter` definition in `PipelineLogger._setup_logger`
- [x] Code Integrity Check
    - [x] Verify imports and variable definitions in `main_window.py`
    - [x] Verify imports and variable definitions in `pipeline_orchestrator.py`
- [x] Implement Last Used Folder Memory
    - [x] Auto-save config on exit in `_on_closing`
    - [x] Verify `_update_config_from_ui` captures paths correcty

# WNAP v1.3.7 Mission: Rules Optimization & Stability
- [x] Genre Inference Optimization
    - [x] Detect existing tags (e.g. `[선협]`) to skip API search
    - [x] Implementation in `GenreClassifierAdapter`
- [x] Normalization Logic Refinement
    - [x] Preserve '외전', '에필로그' keywords in regex
    - [x] Test case: "회귀했더니 입대 전날 1-529 完 에필 및 외전 포함"
- [x] Fix CSV Mapping Path
    - [x] Force save to Main Program Root (`os.path.abspath`)
- [x] System Stability & UI
    - [x] Re-verify `NameError` in `pipeline_logger.py`
    - [x] Verify Real-time Table Redraw
- [x] Final Verification
    - [x] Report CSV location & Normalization logs

# WNAP v1.3.7 Hotfix: Windows Path Handling
- [x] Fix `FileNotFoundError` in `PipelineOrchestrator._move_file`
    - [x] Handle filenames with trailing spaces (e.g., `abc .txt`)
    - [x] Implement `\\?\` prefix logic for Windows `shutil.copy2`
    - [x] Verify fix

# WNAP v1.3.7: Code Integrity & Normalization Robustness
- [x] Fix "Side Story" missing issue (moved cleanup to global scope)
- [x] Replace fragile `\b` regex with explicit boundaries
- [x] Run Global Code Integrity Check (`check_integrity.py`)
    - [x] Verify Syntax (py_compile)
    - [x] Verify NameError (`formatter`)
    - [x] Verify Normalization Logic
- [x] Cleanup Workspace (Moved temp files to `_cleanup_temp`)
- [x] Commit & Push to GitHub (`20081c9`)

# WNAP v1.3.4: PyInstaller Build System
- [x] Requirements Check (`pyinstaller`, `requirements.txt`)
- [x] Configure `build_exe.py`
    - [x] Update version to 1.3.4
    - [x] Switch to `--onedir`
    - [x] Add `.env` external copy logic
- [x] Verify `sys._MEIPASS` logic in `main_gui.py`
- [x] Build Executable (`python build_exe.py`)
- [x] Final Verification (UI, Logs, Functionality)

# WNAP v1.3.5: Normalization Refinement & Rebuild
- [x] Update Version to 1.3.5 (Core, Build Script, Changelog)
- [x] Rebuild Executable (`python build_exe.py --clean`)
- [x] Verify Output (`dist/WNAP_Manager_v1.3.5`)
