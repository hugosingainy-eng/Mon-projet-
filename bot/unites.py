"""Conversions d'unités et lecture prudente des nombres renvoyés par l'API.

eToro ne précise pas toujours si un nombre est en % (12.5) ou en décimal
(0.125). Chaque champ a son unité dans config.yaml (section `unites`).
"""
import logging
import math

log = logging.getLogger("unites")


def nombre(valeur, defaut=None):
    """Convertit en float (accepte le texte "12.5" ou "12,5"). Renvoie defaut si impossible."""
    if valeur is None:
        return defaut
    if isinstance(valeur, bool):
        return float(valeur)
    if isinstance(valeur, (int, float)):
        return defaut if (isinstance(valeur, float) and math.isnan(valeur)) else float(valeur)
    try:
        return float(str(valeur).replace(",", ".").replace("%", "").strip())
    except ValueError:
        return defaut


def en_decimal(valeur, unite, defaut=None):
    """Ramène une valeur en décimal (0.125 = 12,5 %)."""
    v = nombre(valeur, None)
    if v is None:
        return defaut
    if unite == "pourcent":
        return v / 100.0
    return v


def unite(cfg, champ):
    return cfg.get("unites", {}).get(champ, "decimal")


def verifier_echelle(valeurs, unite_cfg, champ, seuil_decimal=3.0):
    """Avertit si l'unité configurée semble fausse (médiane anormale)."""
    vals = sorted(abs(v) for v in valeurs if v is not None)
    if len(vals) < 5:
        return None
    mediane = vals[len(vals) // 2]
    msg = None
    if unite_cfg == "decimal" and mediane > seuil_decimal:
        msg = ("Unité suspecte pour %s : configurée en 'decimal' mais médiane = %.2f. "
               "Essayez 'pourcent' dans config.yaml (section unites)." % (champ, mediane))
    elif unite_cfg == "pourcent" and 0 < mediane < 0.05:
        msg = ("Unité suspecte pour %s : configurée en 'pourcent' mais médiane = %.4f. "
               "Essayez 'decimal' dans config.yaml (section unites)." % (champ, mediane))
    if msg:
        log.warning(msg)
    return msg
