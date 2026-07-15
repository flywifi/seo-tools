@echo off
REM Double-click this file to open the Creator OS setup wizard in your web browser.
REM No terminal knowledge needed. If Windows SmartScreen warns, click "More info"
REM then "Run anyway" (this is a plain text script from the Creator OS repository).

cd /d "%~dp0"
echo Starting Creator OS setup...

where py >nul 2>nul
if %errorlevel%==0 (
  py tools\wizard.py
  goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
  python tools\wizard.py
  goto :eof
)

echo.
echo Python is not installed on this PC.
echo Install it from https://www.python.org/downloads/windows/ then double-click
echo this file again. On the first installer screen, check "Add python.exe to PATH".
echo.
pause
