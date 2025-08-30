@echo off
echo SKCC Awards Calculator
echo =====================
echo.
echo Select an option:
echo 1. Run GUI Application
echo 2. Run Debug Mode
echo 3. Setup/Install Dependencies
echo 4. Exit
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    echo Starting GUI...
    call run_gui.bat
) else if "%choice%"=="2" (
    echo Starting Debug Mode...
    call run_debug.bat
) else if "%choice%"=="3" (
    echo Running Setup...
    call setup.bat
) else if "%choice%"=="4" (
    echo Goodbye!
    exit /b 0
) else (
    echo Invalid choice. Please try again.
    pause
    goto :eof
)
