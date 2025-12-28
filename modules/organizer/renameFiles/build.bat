@echo off
REM 파일명 정규화 도구 빌드 스크립트
REM PyInstaller를 사용하여 Windows 실행 파일 생성

echo ============================================================
echo 파일명 정규화 도구 빌드 시작
echo ============================================================
echo.

REM 이전 빌드 결과 삭제
if exist "dist" (
    echo 이전 빌드 결과 삭제 중...
    rmdir /s /q dist
)

if exist "build" (
    rmdir /s /q build
)

if exist "*.spec" (
    del /q *.spec
)

echo.
echo PyInstaller로 빌드 중...
echo.

REM PyInstaller 실행
pyinstaller --name="파일명정규화도구" ^
    --onefile ^
    --windowed ^
    --icon=NONE ^
    --add-data="rename_normalize.py;." ^
    --hidden-import=tkinter ^
    --hidden-import=tkinter.ttk ^
    --hidden-import=tkinter.filedialog ^
    --hidden-import=tkinter.messagebox ^
    --clean ^
    rename_normalize_gui.py

echo.
echo ============================================================
echo 빌드 완료!
echo ============================================================
echo.
echo 실행 파일 위치: dist\파일명정규화도구.exe
echo.
pause
