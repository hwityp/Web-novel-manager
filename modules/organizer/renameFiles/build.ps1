# 파일명 정규화 도구 빌드 스크립트
# PyInstaller를 사용하여 Windows 실행 파일 생성

# UTF-8 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "파일명 정규화 도구 빌드 시작" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 현재 위치 저장
$originalLocation = Get-Location

# renameFiles 디렉토리로 이동
Set-Location -Path "renameFiles"

# 이전 빌드 결과 삭제
if (Test-Path "dist") {
    Write-Host "이전 빌드 결과 삭제 중..." -ForegroundColor Yellow
    Remove-Item -Path "dist" -Recurse -Force
}

if (Test-Path "build") {
    Remove-Item -Path "build" -Recurse -Force
}

Get-ChildItem -Filter "*.spec" | Remove-Item -Force

Write-Host ""
Write-Host "PyInstaller로 빌드 중..." -ForegroundColor Green
Write-Host ""

# PyInstaller 실행
pyinstaller --name="FileNameNormalizer" `
    --onefile `
    --windowed `
    --add-data="rename_normalize.py;." `
    --hidden-import=tkinter `
    --hidden-import=tkinter.ttk `
    --hidden-import=tkinter.filedialog `
    --hidden-import=tkinter.messagebox `
    --clean `
    rename_normalize_gui.py

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "빌드 완료!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "실행 파일 위치: dist\FileNameNormalizer.exe" -ForegroundColor Yellow
Write-Host ""

# 원래 위치로 복귀
Set-Location -Path $originalLocation

Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
