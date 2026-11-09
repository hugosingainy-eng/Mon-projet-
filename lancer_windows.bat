@echo off
REM Lance le bot et le relance automatiquement s'il plante.
REM Usage :  lancer_windows.bat            (boucle 24h/24)
REM          lancer_windows.bat --dry-run  (simulation, aucun ordre)
chcp 65001 > nul
cd /d "%~dp0"

if not exist ".venv" (
  echo Premiere installation : creation de l'environnement Python...
  python -m venv .venv || (echo Python introuvable. Installez-le depuis python.org & pause & exit /b 1)
  .venv\Scripts\pip install -r requirements.txt
)

if not exist ".env" (
  echo Fichier .env manquant : copiez .env.example en .env et remplissez vos cles.
  pause
  exit /b 1
)

:boucle
echo %date% %time% - demarrage du bot
.venv\Scripts\python -m bot.main %*
set CODE=%errorlevel%
if %CODE%==0 goto fin
if %CODE%==2 goto fin
echo %date% %time% - le bot a plante (code %CODE%). Relance dans 60 secondes...
timeout /t 60 /nobreak > nul
goto boucle

:fin
echo Le bot s'est arrete (code %CODE%).
pause
