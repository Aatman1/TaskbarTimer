@echo off
REM ─────────────────────────────────────────────────────────────────
REM  TaskbarTimer — Build Script
REM  Run this once to create a standalone .exe in the dist\ folder
REM ─────────────────────────────────────────────────────────────────

echo Installing dependencies...
pip install pystray pillow pyinstaller

echo.
echo Building TaskbarTimer.exe ...
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "TaskbarTimer" ^
    --icon NONE ^
    timer_app.py

echo.
echo ✓ Done! Your app is in:  dist\TaskbarTimer.exe
echo   Double-click it to run. It will appear in your system tray.
pause
