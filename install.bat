@echo off
echo ============================================
echo  Meshtastic Python Client - Windows Setup
echo ============================================
echo.

REM Check Python version
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo Using Python:
python -c "import sys; print(' ', sys.executable)"
echo.
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install dependencies.
    echo Make sure you are using the correct Python installation.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Installation complete!
echo  Run the app with:  python main.py
echo  Or double-click:   run.bat
echo ============================================
pause
