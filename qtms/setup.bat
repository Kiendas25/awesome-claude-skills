@echo off
REM ============================================================
REM  QTMS - one-time setup. Installs Python dependencies.
REM  Run this once before the first launch.
REM ============================================================
cd /d "%~dp0"
echo Installing QTMS dependencies (numpy, pandas, fastapi, ...)...
py -m pip install -r requirements.txt
echo.
echo  Done. Now run start.bat (this PC) or start-phone.bat (phone access).
pause
