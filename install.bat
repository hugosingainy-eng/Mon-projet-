@echo off
cd /d "%~dp0"
echo Installing Quantum Edge AI (paper trading only)...
py -3 -m venv .venv || python -m venv .venv
if errorlevel 1 (echo Python 3.11+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (echo Installation failed. & pause & exit /b 1)
echo.
echo Done. Next: selfcheck.bat, then start.bat
pause
