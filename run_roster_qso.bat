@echo off
echo SKCC QSO Logger with Roster Integration
echo ========================================
echo.
echo Starting QSO Logger with live SKCC roster...
echo.
python test_roster_qso.py
if errorlevel 1 (
    echo.
    echo Error starting QSO Logger!
    pause
)
