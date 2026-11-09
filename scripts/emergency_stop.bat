@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python -m quantum_edge emergency-stop --reason "arret manuel (script)"
pause
