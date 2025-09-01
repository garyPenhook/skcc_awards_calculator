@echo off
echo Starting SKCC QSO Logger...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python first
    pause
    exit /b 1
)

REM Run the W4GNS SKCC Logger GUI
python w4gns_skcc_logger.py
pause
