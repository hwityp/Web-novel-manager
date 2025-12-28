@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ============================================
echo   WNAP Git Commit Script
echo ============================================
echo.

:: 현재 상태 확인
echo [1/4] 현재 Git 상태 확인 중...
git status --short
echo.

:: 커밋 메시지 입력
set /p "COMMIT_MSG=커밋 메시지를 입력하세요: "

if "%COMMIT_MSG%"=="" (
    echo 오류: 커밋 메시지가 비어있습니다.
    pause
    exit /b 1
)

:: 모든 변경사항 스테이징
echo.
echo [2/4] 변경사항 스테이징 중...
git add -A
if errorlevel 1 (
    echo 오류: 스테이징 실패
    pause
    exit /b 1
)

:: 커밋 실행
echo.
echo [3/4] 커밋 실행 중...
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo 오류: 커밋 실패 (변경사항이 없거나 오류 발생)
    pause
    exit /b 1
)

:: 푸시 여부 확인
echo.
set /p "PUSH_YN=원격 저장소에 푸시하시겠습니까? (y/n): "

if /i "%PUSH_YN%"=="y" (
    echo.
    echo [4/4] 원격 저장소에 푸시 중...
    git push
    if errorlevel 1 (
        echo 오류: 푸시 실패
        pause
        exit /b 1
    )
    echo.
    echo ✅ 커밋 및 푸시 완료!
) else (
    echo.
    echo ✅ 커밋 완료! (푸시는 건너뜀)
)

echo.
echo ============================================
echo   최근 커밋 로그
echo ============================================
git log --oneline -3

echo.
pause
