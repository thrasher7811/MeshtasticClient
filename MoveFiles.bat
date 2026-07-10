@echo off
setlocal enabledelayedexpansion

REM Create output folder if it doesn't exist
if not exist "Copilot_Project" (
    mkdir "Copilot_Project"
)

REM Loop through all .py files in the same directory as this .bat file
for %%F in (*.py) do (
    echo Processing %%F...

    REM Extract filename without extension
    set "name=%%~nF"

    REM Copy .py file to .txt file in the subfolder
    copy "%%F" "Copilot_Project\!name!.txt" >nul
)

REM Loop through all .json files in the same directory as this .bat file
for %%F in (*.json) do (
    echo Processing %%F...

    REM Extract filename without extension
    set "name=%%~nF"

    REM Copy .py file to .txt file in the subfolder
    copy "%%F" "Copilot_Project\!name!.txt" >nul
)

REM Get the requirements.txt file and copy
for %%F in (requirements.txt) do (
    echo Processing %%F...

    REM Extract filename without extension
    set "name=%%~nF"

    REM Copy .py file to .txt file in the subfolder
    copy "%%F" "Copilot_Project\!name!.txt" >nul
)

echo Done.
pause
