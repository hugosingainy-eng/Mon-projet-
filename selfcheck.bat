@echo off
cd /d "%~dp0"
.venv\Scripts\python -m quantum_edge selfcheck
pause
