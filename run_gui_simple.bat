@echo off
echo Starting SKCC Awards Calculator...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please run install_simple.bat first
    pause
    exit /b 1
)

REM Try to import required modules
python -c "import httpx, bs4" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Required packages not installed
    echo Please run install_simple.bat first
    pause
    exit /b 1
)

REM Run the GUI
python scripts\gui.py
