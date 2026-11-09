"""Règles de sécurité CODÉES EN DUR. Aucun agent, ni l'IA, ni le chat ne peut
les contourner. config.yaml peut seulement les rendre plus strictes.
"""
import logging

log = logging.getLogger("securite")

PERTE_MAX_ABSOLUE = 0.05      # jamais plus de 5 % de perte, quoi que dise la config
EXPOSITION_MAX_ABSOLUE = 1.0  # jamais plus que le budget


class RefusSecurite(Exception):
    """Une action a été bloquée par une règle de sécurité."""


def perte_max(cfg):
    return min(float(cfg.get("securite", {}).get("perte_max_pct", PERTE_MAX_ABSOLUE)),
               PERTE_MAX_ABSOLUE)


def capital(cfg, etat):
    """Argent que le bot a le droit d'engager.

    = budget, diminué des pertes réalisées. Les gains réalisés ne s'ajoutent que
    si `copie.reinvestir_gains: true`.
    """
    budget = float(cfg["budget"])
    realise = float(etat.data.get("pnl_realise", 0.0))
    if realise < 0:
        return max(0.0, budget + realise)
    if cfg.get("copie", {}).get("reinvestir_gains", False):
        return budget + realise
    return budget


def seuil_arret(cfg):
    return -perte_max(cfg) * float(cfg["budget"])


def doit_arreter(cfg, etat):
    """True si la perte totale (réalisée + latente) atteint -5 % du budget."""
    return etat.pnl_total() <= seuil_arret(cfg)


def nb_et_part(montant_total, nb_max, minimum):
    """Partage à parts égales ; si une part tombe sous le minimum eToro, on copie
    moins de traders (voire aucun = reste en cash)."""
    n = int(nb_max)
    while n > 0 and montant_total / n < minimum:
        n -= 1
    return (n, montant_total / n) if n else (0, 0.0)


def engage(etat):
    """Argent engagé : copies ouvertes + ordres en attente."""
    attente = sum(max(0.0, float(o.get("montant", 0)))
                  for o in etat.data.get("ordres_en_attente", {}).values())
    return etat.investi_total() + attente


def verifier_ajout(cfg, etat, montant):
    """Lève RefusSecurite si ajouter `montant` dépasserait le capital autorisé."""
    if montant <= 0:
        return
    if etat.arret_actif:
        raise RefusSecurite("arrêt d'urgence actif : aucun nouvel investissement")
    if etat.data.get("pause"):
        raise RefusSecurite("bot en pause : aucun nouvel investissement")
    limite = capital(cfg, etat) * EXPOSITION_MAX_ABSOLUE
    if engage(etat) + montant > limite + 0.01:
        raise RefusSecurite("budget dépassé : %.2f $ engagés + %.2f $ > %.2f $ autorisés"
                            % (engage(etat), montant, limite))


def verifier_proprietaire(etat, mirror_id):
    """Le bot ne touche JAMAIS une copie qu'il n'a pas créée."""
    if str(mirror_id) not in etat.mirror_ids_du_bot():
        raise RefusSecurite("la copie %s n'a pas été créée par le bot : on n'y touche pas"
                            % mirror_id)
