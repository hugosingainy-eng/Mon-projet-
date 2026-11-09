"""Veille X (réseau social X/Twitter), via la recherche X intégrée à Grok.

Active seulement si ia.fournisseur = grok et qu'une clé XAI_API_KEY existe.
Cherche ce qui se dit sur les traders et sur leurs grosses lignes ces 48 h.
Comme les actualités, elle ne peut que donner un malus : jamais de bonus.
"""
import json
import logging

from ..ia import extraire_json

log = logging.getLogger("veille_x")

SYSTEME = (
    "Tu fais une veille prudente sur X (Twitter) pour un bot de copy trading eToro. "
    "Pour chaque trader eToro et chaque action listés, cherche sur X les dernières {h} "
    "heures : rumeurs graves, scandales, fraudes, paniques, enquêtes. Ignore le bruit "
    "ordinaire. Réponds UNIQUEMENT en JSON : "
    '{{"alertes": [{{"cible": "username ou ticker", "gravite": "faible|moyenne|forte", '
    '"resume": "..."}}]}}'
)

GRAVITE = {"faible": 0.25, "moyenne": 0.6, "forte": 1.0}


def veiller(client_ia, cfg, traders, tickers):
    """Renvoie dict cible -> {gravite, resume}. Vide si indisponible."""
    cv = cfg.get("veille_x", {})
    if not cv.get("actif", True) or client_ia is None or not getattr(
            client_ia, "sait_chercher_sur_x", False):
        return {}
    message = json.dumps({"traders_etoro": traders, "actions": sorted(tickers)[:40]},
                         ensure_ascii=False)
    try:
        brut = extraire_json(client_ia.demander(SYSTEME.format(h=cv.get("heures", 48)),
                                                message, recherche=False, recherche_x=True))
    except Exception as exc:  # noqa: BLE001
        log.warning("Veille X indisponible (%s)", exc)
        return {}
    out = {}
    for a in (brut or {}).get("alertes", []) or []:
        if isinstance(a, dict) and a.get("cible"):
            g = str(a.get("gravite", "faible")).lower()
            out[str(a["cible"])] = {"gravite": g if g in GRAVITE else "faible",
                                    "resume": str(a.get("resume", ""))[:300]}
    return out


def malus_x(trader, poids_par_ticker, alertes, cfg):
    """Malus de 0 à malus_max selon la gravité des alertes qui touchent le trader."""
    if not alertes:
        return 0.0
    mx = cfg.get("veille_x", {}).get("malus_max", 0.20)
    niveau = 0.0
    a = alertes.get(trader)
    if a:
        niveau = max(niveau, GRAVITE[a["gravite"]])
    for t, w in poids_par_ticker.items():
        a = alertes.get(t) or alertes.get(t.upper())
        if a:
            niveau = max(niveau, GRAVITE[a["gravite"]] * min(1.0, w * 2))
    return mx * niveau
