@echo off
cd /d "%~dp0"

echo Python 가상환경 생성 및 패키지 설치 중...
python -m venv .venv
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다. python.org 에서 설치하세요.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

if not exist .env copy .env.example .env

echo.
echo  설치 완료. start.bat 을 더블클릭하세요.
pause
