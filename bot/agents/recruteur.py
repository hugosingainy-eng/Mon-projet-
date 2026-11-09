"""Agent 1 - Recruteur (chaque semaine).

Lit le classement eToro, applique les filtres prudents, classe les traders
selon  gain / max(chute, 3 %) x % de mois gagnants,  puis vérifie en détail
les 15 premiers (historique mensuel et façon de trader).
"""
import datetime as dt
import logging

from ..donnees import gains_mensuels, normaliser_trader, stats_tradeinfo
from ..unites import unite, verifier_echelle

log = logging.getLogger("recruteur")


def score(t, cfg_r):
    plancher = float(cfg_r.get("chute_plancher_score", 0.03))
    return t["gain"] / max(t["chute"] or 0.0, plancher) * (t["mois_gagnants"] or 0.0)


def filtrer(t, cfg_r):
    """Renvoie None si le trader passe, sinon la raison du rejet (en français)."""
    types_refuses = [s.lower() for s in cfg_r.get("types_refuses", [])]
    typ = str(t.get("type") or "").lower()
    if any(s in typ for s in types_refuses):
        return "Smart Portfolio / fonds (type %s)" % t.get("type")
    if cfg_r.get("popular_investor_seulement", True) and t.get("popular_investor") is False:
        return "pas Popular Investor"
    for cle, nom in (("gain", "gain"), ("risque", "risque"), ("chute", "chute maximale"),
                     ("mois_gagnants", "% de mois gagnants")):
        if t.get(cle) is None:
            return "donnée manquante : %s" % nom
    if t["risque"] > cfg_r["risque_max"]:
        return "risque %.0f > %s" % (t["risque"], cfg_r["risque_max"])
    if t.get("pic_risque") is not None and t["pic_risque"] > cfg_r["pic_risque_mensuel_max"]:
        return "pic de risque mensuel %.0f > %s" % (t["pic_risque"],
                                                    cfg_r["pic_risque_mensuel_max"])
    if t["gain"] < cfg_r["gain_min"]:
        return "gain %.1f %% < %.0f %%" % (100 * t["gain"], 100 * cfg_r["gain_min"])
    if t["gain"] > cfg_r["gain_max"]:
        return "gain %.1f %% > %.0f %% (trop beau, souvent trop risqué)" % (
            100 * t["gain"], 100 * cfg_r["gain_max"])
    if t["chute"] > cfg_r["chute_max"]:
        return "chute maximale %.1f %% > %.0f %%" % (100 * t["chute"], 100 * cfg_r["chute_max"])
    if t["mois_gagnants"] < cfg_r["mois_gagnants_min"]:
        return "mois gagnants %.0f %% < %.0f %%" % (100 * t["mois_gagnants"],
                                                    100 * cfg_r["mois_gagnants_min"])
    if t["copieurs"] < cfg_r["copieurs_min"]:
        return "%d copieurs < %d" % (t["copieurs"], cfg_r["copieurs_min"])
    if t["trades"] < cfg_r["trades_min"]:
        return "%d trades < %d" % (t["trades"], cfg_r["trades_min"])
    return None


def verifier_historique(mensuels, cfg_r):
    if len(mensuels) < cfg_r["mois_historique_min"]:
        return "seulement %d mois d'historique (< %d)" % (len(mensuels),
                                                          cfg_r["mois_historique_min"])
    douze = [g for _, g in mensuels[-12:]]
    pire = min(douze)
    if pire < cfg_r["pire_mois_min"]:
        return "un mois à %.1f %% sur les 12 derniers (< %.0f %%)" % (
            100 * pire, 100 * cfg_r["pire_mois_min"])
    return None


def verifier_style(s, cfg_r, aujourd_hui):
    if s["levier_fort"] is not None and s["levier_fort"] > cfg_r["levier_fort_max"]:
        return "%.0f %% de trades à fort levier (> %.0f %%)" % (100 * s["levier_fort"],
                                                               100 * cfg_r["levier_fort_max"])
    if s["copie_autres"] is not None and s["copie_autres"] > cfg_r["copie_autres_max"]:
        return "copie surtout d'autres traders (%.0f %%)" % (100 * s["copie_autres"])
    if s["semaines_actives"] is not None and s["semaines_actives"] < cfg_r["semaines_actives_min"]:
        return "actif seulement %.0f %% des semaines (< %.0f %%)" % (
            100 * s["semaines_actives"], 100 * cfg_r["semaines_actives_min"])
    if s["derniere_activite"] is not None:
        jours = (aujourd_hui - s["derniere_activite"]).days
        if jours > cfg_r["inactivite_max_jours"]:
            return "inactif depuis %d jours" % jours
    return None


def lire_classement(api, cfg):
    cfg_r = cfg["recruteur"]
    total = int(cfg_r.get("nb_traders_lus", 300))
    taille = min(int(cfg_r.get("taille_page", 100)), 100)
    lignes, page = [], 1
    while len(lignes) < total:
        lot = api.classement(page=page, taille=taille, periode=cfg_r.get("periode", "OneYearAgo"),
                             riskScoreMax=cfg_r["risque_max"], copiersMin=cfg_r["copieurs_min"],
                             popularInvestor=True if cfg_r.get("popular_investor_seulement",
                                                               True) else None,
                             sort=cfg_r.get("tri"))
        if not lot:
            break
        lignes.extend(lot)
        if len(lot) < taille:
            break
        page += 1
    return lignes[:total]


def recruter(api, cfg, etat=None, aujourd_hui=None):
    """Renvoie (candidats triés, rejets[{username, raison}])."""
    cfg_r = cfg["recruteur"]
    aujourd_hui = aujourd_hui or dt.date.today()
    lignes = lire_classement(api, cfg)
    traders = [normaliser_trader(r, cfg) for r in lignes]
    verifier_echelle([t["gain"] for t in traders], unite(cfg, "gain_classement"), "gain")
    log.info("Recruteur : %d traders lus dans le classement", len(traders))

    rejets, retenus, vus = [], [], set()
    for t in traders:
        if not t["username"] or t["username"] in vus:
            continue
        vus.add(t["username"])
        if etat is not None and etat.est_banni(t["username"]):
            rejets.append({"username": t["username"], "agent": "Recruteur",
                           "raison": "banni (comportement passé)"})
            continue
        raison = filtrer(t, cfg_r)
        if raison:
            rejets.append({"username": t["username"], "agent": "Recruteur", "raison": raison})
            continue
        t["score"] = score(t, cfg_r)
        retenus.append(t)
    retenus.sort(key=lambda t: t["score"], reverse=True)

    candidats = []
    for t in retenus[:int(cfg_r.get("nb_verifies_en_detail", 15))]:
        try:
            mensuels = gains_mensuels(api.gains(t["username"]), cfg)
            raison = verifier_historique(mensuels, cfg_r)
            if not raison:
                s = stats_tradeinfo(api.trade_info(t["username"], cfg_r.get("periode")), cfg)
                t["style"] = s
                raison = verifier_style(s, cfg_r, aujourd_hui)
        except Exception as exc:  # noqa: BLE001 - un trader illisible est simplement écarté
            raison = "données indisponibles (%s)" % exc
        if raison:
            rejets.append({"username": t["username"], "agent": "Recruteur", "raison": raison})
            continue
        t["mensuels"] = [(d.isoformat(), g) for d, g in mensuels]
        candidats.append(t)
    for t in retenus[int(cfg_r.get("nb_verifies_en_detail", 15)):]:
        rejets.append({"username": t["username"], "agent": "Recruteur",
                       "raison": "hors des %d meilleurs scores" % cfg_r.get(
                           "nb_verifies_en_detail", 15)})
    log.info("Recruteur : %d candidats après vérification détaillée", len(candidats))
    return candidats, rejets
