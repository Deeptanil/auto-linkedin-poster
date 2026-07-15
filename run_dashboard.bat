@echo off
title LinkedIn AI Content Dashboard Launcher

echo ========================================================
echo   Starting LinkedIn Content Dashboard Local Server...
echo ========================================================
echo.

:: Navigate to script directory
cd /d "%~dp0"

:: Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo [OK] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [!] No virtual environment found. Running in default Python context.
)

:: Verify dependencies
echo [OK] Verifying Flask installation...
python -c "import flask" >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Flask is missing. Installing requirements...
    pip install -r requirements.txt
)

:: Run dashboard server
echo [OK] Launching server on http://localhost:5000/
echo.
echo Press Ctrl+C in this window to stop the dashboard.
echo.

python dashboard.py

pause
