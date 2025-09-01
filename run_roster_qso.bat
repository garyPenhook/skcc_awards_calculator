@echo off
echo SKCC QSO Logger with Roster Integration
echo ========================================
echo.
echo Starting W4GNS SKCC Logger with roster integration...
echo.
python w4gns_skcc_logger.py
if errorlevel 1 (
    echo.
    echo Error starting QSO Logger!
    pause
)
