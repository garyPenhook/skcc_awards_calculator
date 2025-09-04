@echo off
echo Running dependency check...
echo.
REM Detect a usable Python command (prefer python, fallback to Windows launcher py -3)
set "PYCMD="
python --version >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD (
	py -3 --version >nul 2>&1 && set "PYCMD=py -3"
)
if not defined PYCMD (
	echo ERROR: Python is not installed or not in PATH
	pause
	exit /b 1
)

%PYCMD% check_dependencies.py
pause
