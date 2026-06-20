@echo off
python3 main.py
if %errorlevel% neq 0 (
    echo.
    echo Application exited with error.
    echo If packages are missing, run:  python -m pip install -r requirements.txt
    pause
)
