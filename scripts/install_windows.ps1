# Installation de Quantum Edge AI sous Windows (PowerShell).
# Usage : clic droit > "Exécuter avec PowerShell", ou dans PowerShell :
#   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python introuvable. Installe Python 3.11+ depuis https://www.python.org/downloads/ (coche 'Add python.exe to PATH')." -ForegroundColor Red
    exit 1
}
python --version
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Write-Host "Fichier .env créé (mode simulé, gratuit)." }
& .\.venv\Scripts\python.exe -m pytest -q
Write-Host ""
Write-Host "Installation terminée." -ForegroundColor Green
Write-Host "Étapes suivantes :"
Write-Host "  1) scripts\run_research.bat   (cherche et valide les stratégies, ~5-15 min)"
Write-Host "  2) scripts\start_dashboard.bat (puis ouvre http://127.0.0.1:8000)"
Write-Host "  3) scripts\start_bot.bat       (le bot tourne du lundi au vendredi)"
