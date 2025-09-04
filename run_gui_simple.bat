@echo off
echo Starting SKCC Awards Calculator...
echo.

REM Detect a usable Python command (prefer python, fallback to Windows launcher py -3)
set "PYCMD="
python --version >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD (
    py -3 --version >nul 2>&1 && set "PYCMD=py -3"
)
if not defined PYCMD (
    echo ERROR: Python is not installed or not in PATH
    echo Please run install_simple.bat first
    pause
    exit /b 1
)

REM Try to import required modules
%PYCMD% -c "import httpx, bs4" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Required packages not installed
    echo Please run install_simple.bat first
    pause
    exit /b 1
)

REM Run the GUI
%PYCMD% scripts\gui.py
