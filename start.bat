@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run install.bat first. & pause & exit /b 1)
start "Quantum Edge AI" /min .venv\Scripts\python -m quantum_edge
timeout /t 6 /nobreak >nul
start "" http://127.0.0.1:8000
echo Quantum Edge AI is running in its own window (minimized). Dashboard: http://127.0.0.1:8000
echo It keeps running until you run stop.bat or shut the computer down.
