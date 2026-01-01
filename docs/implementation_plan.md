# PyInstaller Build System Setup

## Goal Description
Establish a robust build system using PyInstaller to package WNAP as a standalone executable (folder-based). This ensures the application can run independently without Python installed, preserving all UI themes and core logic.

## User Review Required
> [!IMPORTANT]
> **Build Mode**: Switched from `--onefile` to `--onedir` (folder output) for better stability and faster startup, as requested. The single file mode can be enabled later if strictly needed, but folder mode is preferred for development/debugging.
> **Environment Variables**: `.env` file will be included in the build. Ensure it doesn't contain sensitive production secrets if distributing widely.

## Proposed Changes

### Build Configuration
#### [MODIFY] [build_exe.py](file:///c:/Users/hwity/Cursor_Work/WebNovelManager/build_exe.py)
- Change `__version__` to `1.3.2`.
- Remove `--onefile` flag (defaulting to onedir).
- Add `--add-data .env;.` command argument.
- Ensure `--noconsole` is maintained.

### UI Entry Point
#### [MODIFY] [main_gui.py](file:///c:/Users/hwity/Cursor_Work/WebNovelManager/main_gui.py)
- Already contains `_setup_paths` logic.
- Will verify if `ctk.set_default_color_theme` needs explicit path handling if the default "blue" theme fails. (Usually `collect-all` handles this, but we'll monitor).

## Verification Plan

### Automated Build Verification
1. Run `python build_exe.py --clean`.
2. Check if `dist/WNAP_Manager_v1.3.2/WNAP_Manager_v1.3.2.exe` exists.
3. Check if `dist/.../config` and `.env` exist (if not packed inside binary in onedir mode, they might be in the folder). Note: `--add-data` puts them *inside* the internal structure. For onedir, they standardly appear in the folder or inside `_internal`.

### Manual Testing
1. Execute the built EXE.
2. Verify UI loads (Dark theme, Blue accents).
3. Run a "Dry Run" on the test folder.
4. Check `logs/` folder creation in the exe execution directory.
