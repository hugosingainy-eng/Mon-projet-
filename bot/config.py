"""Chargement de config.yaml et du fichier .env.

Le double verrou de l'argent réel est vérifié ici : il faut `mode: real`
dans config.yaml ET `I_ACCEPT_REAL_MONEY_RISK=oui` dans .env.
"""
import copy
import os

import yaml


class ErreurConfig(Exception):
    """La configuration est invalide ou dangereuse."""


SECRETS = ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER", "MT5_PATH",
           "ETORO_API_KEY", "ETORO_USER_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY",
           "SEC_USER_AGENT", "I_ACCEPT_REAL_MONEY_RISK", "TELEGRAM_BOT_TOKEN",
           "TELEGRAM_CHAT_ID")


def lire_env(chemin=".env"):
    """Lit un fichier .env simple (CLE=valeur). Ne plante pas s'il n'existe pas."""
    valeurs = {}
    if not chemin or not os.path.isfile(chemin):
        return valeurs
    with open(chemin, encoding="utf-8") as fh:
        for ligne in fh:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, val = ligne.split("=", 1)
            val = val.strip().strip('"').strip("'")
            valeurs[cle.strip()] = val
    return valeurs


def charger_config(chemin="config.yaml", chemin_env=".env", environ=None, surcharges=None):
    """Retourne un dict de configuration, avec les secrets dans cfg["_secrets"]."""
    if not os.path.isfile(chemin):
        raise ErreurConfig("Fichier de configuration introuvable : %s" % chemin)
    with open(chemin, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    if surcharges:
        cfg = fusionner(cfg, surcharges)
    environ = os.environ if environ is None else environ
    fichier = lire_env(chemin_env)
    secrets = {}
    for nom in SECRETS:
        # Une variable d'environnement réelle a priorité sur le fichier .env
        secrets[nom] = (environ.get(nom) or fichier.get(nom) or "").strip()
    cfg["_secrets"] = secrets
    valider(cfg)
    return cfg


def fusionner(base, ajout):
    """Fusion récursive de deux dict (ajout gagne)."""
    out = copy.deepcopy(base)
    for k, v in (ajout or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = fusionner(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def valider(cfg):
    if cfg.get("plateforme", "etoro") not in ("etoro", "mt5"):
        raise ErreurConfig("plateforme doit valoir 'mt5' ou 'etoro'")
    mode = cfg.get("mode", "demo")
    if mode not in ("demo", "real"):
        raise ErreurConfig("mode doit valoir 'demo' ou 'real' (actuellement %r)" % mode)
    if mode == "real":
        accord = cfg["_secrets"].get("I_ACCEPT_REAL_MONEY_RISK", "").lower()
        if accord != "oui":
            raise ErreurConfig(
                "ARGENT RÉEL REFUSÉ : config.yaml demande mode: real, mais .env ne contient "
                "pas I_ACCEPT_REAL_MONEY_RISK=oui. Les deux verrous sont obligatoires.")
    budget = float(cfg.get("budget", 0))
    if budget <= 0:
        raise ErreurConfig("Le budget doit être positif.")
    perte = float(cfg.get("securite", {}).get("perte_max_pct", 0.05))
    if not 0 < perte <= 0.05:
        raise ErreurConfig("securite.perte_max_pct doit être entre 0 et 0.05 (5 %% max).")
    return True


def chemin_data(cfg, nom_cle, dry_run=False):
    """Chemin d'un fichier de data/ (l'état est séparé en dry-run)."""
    f = cfg.get("fichiers", {})
    dossier = f.get("dossier_data", "data")
    if nom_cle == "etat" and dry_run:
        nom = f.get("etat_dry_run", "etat_dry_run.json")
    else:
        nom = f.get(nom_cle, nom_cle)
    # MetaTrader 5 et eToro ont chacun leur propre mémoire et leur propre rapport
    if cfg.get("plateforme", "etoro") == "mt5" and nom_cle in ("etat", "rapport", "backtest"):
        nom = "mt5_" + nom
    return os.path.join(dossier, nom)
