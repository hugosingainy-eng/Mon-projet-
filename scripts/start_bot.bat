@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
echo Quantum Edge AI - MODE DEMO. Ferme cette fenetre pour arreter le bot.
python -m quantum_edge run
pause
