@echo off
echo SKCC Awards Calculator - Windows Setup
echo =====================================
echo.

REM Detect a usable Python command (prefer python, fallback to Windows launcher py -3)
set "PYCMD="
python --version >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD (
    py -3 --version >nul 2>&1 && set "PYCMD=py -3"
)
if not defined PYCMD (
    echo ERROR: Python is not installed or not in PATH
    echo - If you have Python installed, enable the Windows launcher during install OR add Python to PATH.
    echo - Otherwise, install Python from https://www.python.org/downloads/
    echo   (Check "Add python.exe to PATH" and "Install launcher for all users")
    pause
    exit /b 1
)

echo Python found: 
%PYCMD% --version
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install requirements
echo Installing required packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    pause
    exit /b 1
)

echo.
echo Setup complete! You can now run the program:
echo.
echo 1. GUI Mode (recommended):
echo    run_gui.bat
echo.
echo 2. Debug mode:
echo    run_debug.bat
echo.
echo 3. Manual command:
echo    .venv\Scripts\activate
echo    python scripts\gui.py
echo.
pause
