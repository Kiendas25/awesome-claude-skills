@echo off
REM ============================================================
REM  QTMS - launcher for PHONE access (same Wi-Fi network)
REM  Binds to all interfaces so your phone can reach this PC.
REM ============================================================
cd /d "%~dp0"
echo.
echo  Your PC's IP addresses (look for IPv4, e.g. 192.168.x.x):
echo ------------------------------------------------------------
ipconfig | findstr /C:"IPv4"
echo ------------------------------------------------------------
echo.
echo  On your PHONE (same Wi-Fi), open:  http://YOUR-IPv4:8000
echo  e.g.  http://192.168.1.20:8000
echo  Then use your browser menu -> "Add to Home Screen".
echo.
echo  Press CTRL+C here to stop.
echo ============================================================
echo.
py -m uvicorn qtms.app.main:app --host 0.0.0.0 --port 8000
echo.
echo  QTMS stopped.
pause
