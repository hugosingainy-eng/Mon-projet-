"""Logs en français, avec rotation du fichier data/bot.log."""
import logging
import logging.handlers
import os

FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configurer_logs(chemin="data/bot.log", niveau=logging.INFO, console=True):
    racine = logging.getLogger()
    racine.setLevel(niveau)
    for h in list(racine.handlers):
        racine.removeHandler(h)
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    fichier = logging.handlers.RotatingFileHandler(
        chemin, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    fichier.setFormatter(logging.Formatter(FORMAT))
    racine.addHandler(fichier)
    if console:
        ecran = logging.StreamHandler()
        ecran.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s",
                                             "%H:%M:%S"))
        racine.addHandler(ecran)
    # Les bibliothèques réseau sont trop bavardes
    for nom in ("urllib3", "httpx", "anthropic"):
        logging.getLogger(nom).setLevel(logging.WARNING)
    return racine
