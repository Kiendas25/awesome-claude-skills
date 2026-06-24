@echo off
REM ============================================================
REM  QTMS - one-click launcher (local / this PC only)
REM  Opens the dashboard at http://127.0.0.1:8000
REM ============================================================
cd /d "%~dp0"
echo.
echo  Starting QTMS dashboard...
echo  When it says "Application startup complete", open:
echo.
echo       http://127.0.0.1:8000
echo.
echo  Press CTRL+C in this window to stop.
echo ============================================================
echo.
py -m uvicorn qtms.app.main:app --reload
echo.
echo  QTMS stopped.
pause
