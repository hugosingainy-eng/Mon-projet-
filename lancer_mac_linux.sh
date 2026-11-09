#!/usr/bin/env bash
# Lance le bot et le relance automatiquement s'il plante.
# Usage :  ./lancer_mac_linux.sh            (boucle 24h/24)
#          ./lancer_mac_linux.sh --dry-run  (simulation, aucun ordre)
cd "$(dirname "$0")" || exit 1

if [ ! -d ".venv" ]; then
  echo "Première installation : création de l'environnement Python..."
  python3 -m venv .venv || { echo "Python 3 introuvable. Installez-le (voir README)."; exit 1; }
  .venv/bin/pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
  echo "Fichier .env manquant : copiez .env.example en .env et remplissez vos clés."
  exit 1
fi

while true; do
  echo "$(date '+%F %T') - démarrage du bot"
  .venv/bin/python -m bot.main "$@"
  code=$?
  if [ "$code" -eq 0 ] || [ "$code" -eq 2 ]; then
    echo "Le bot s'est arrêté normalement (code $code)."
    break
  fi
  echo "$(date '+%F %T') - le bot a planté (code $code). Relance dans 60 secondes..."
  sleep 60
done
