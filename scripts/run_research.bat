@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python scripts\update_macro_calendar.py
python -m quantum_edge research
python -m quantum_edge backtest
pause
