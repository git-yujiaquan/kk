@echo off
setlocal

:: Go to the parent directory of the script
cd /d "%~dp0"

:: Run app.py
python -m app

endlocal