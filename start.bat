@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\streamlit.exe" (
    echo [오류] setup.bat 을 먼저 실행하세요.
    pause
    exit /b 1
)

set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

echo.
echo  실행 중... 브라우저에서 http://localhost:8501 열립니다
echo  종료: 이 창에서 Ctrl+C
echo.

start "" "http://localhost:8501"
".venv\Scripts\streamlit.exe" run app.py --server.port 8501

pause
