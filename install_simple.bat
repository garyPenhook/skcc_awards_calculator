@echo off
echo SKCC Awards Calculator - Simple Installation
echo ===========================================
echo.
echo This will install the required packages for SKCC Awards Calculator.
echo Only 2 packages are needed: httpx and beautifulsoup4
echo.

REM Detect a usable Python command (prefer python, fallback to Windows launcher py -3)
set "PYCMD="
python --version >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD (
    py -3 --version >nul 2>&1 && set "PYCMD=py -3"
)
if not defined PYCMD (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" and "Install launcher" during installation
    pause
    exit /b 1
)

echo Python found: 
%PYCMD% --version
echo.

echo Installing required packages...
echo - httpx (for downloading SKCC roster)
echo - beautifulsoup4 (for parsing web pages)
echo.

%PYCMD% -m pip install httpx==0.27.0 beautifulsoup4==4.12.3

if errorlevel 1 (
    echo ERROR: Failed to install packages
    echo Try running as administrator or check your internet connection
    pause
    exit /b 1
)

echo.
echo ✅ Installation complete!
echo.
echo You can now run the SKCC Awards Calculator:
echo.
echo 1. Double-click: run_gui_simple.bat
echo 2. Or run manually: python scripts\gui.py
echo.
pause
