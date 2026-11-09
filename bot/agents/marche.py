"""Agent 4 - Marché (chaque jour + contrôle rapide à chaque cycle).

SPX500 et NSDQ100 décident du climat ; GOLD et BTC servent d'information.
Indicateurs : moyenne mobile 200 jours, baisse depuis le plus haut sur 1 an,
volatilité 20 jours comparée à 1 an, variation sur 5 jours.

Climat : calme -> 100 % du budget exposé, tendu -> 70 %, stress -> 40 %.
Une chute de -3 % dans la journée fait passer en stress immédiatement.
"""
import datetime as dt
import logging
import math

from ..donnees import champ, clotures
from ..unites import nombre

log = logging.getLogger("marche")

ORDRE = {"calme": 0, "tendu": 1, "stress": 2}


def pire(*climats):
    return max(climats, key=lambda c: ORDRE.get(c, 0))


def indicateurs(cl):
    """cl : liste de cours de clôture du plus ancien au plus récent."""
    if len(cl) < 30:
        return None
    dernier = cl[-1]
    mm200 = sum(cl[-200:]) / len(cl[-200:])
    an = cl[-252:]
    plus_haut = max(an)
    rend = [cl[i] / cl[i - 1] - 1 for i in range(1, len(cl))]

    def vol(r):
        if len(r) < 2:
            return 0.0
        m = sum(r) / len(r)
        return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))

    vol20 = vol(rend[-20:])
    vol1a = vol(rend[-252:])
    return {
        "dernier": dernier,
        "mm200": mm200,
        "sous_mm200": dernier < mm200,
        "baisse_plus_haut": 1 - dernier / plus_haut if plus_haut else 0.0,
        "ratio_vol": vol20 / vol1a if vol1a else 1.0,
        "variation_5j": dernier / cl[-6] - 1 if len(cl) >= 6 else 0.0,
    }


def climat_indice(ind, cfg_m):
    s = cfg_m["seuils"]
    points = 0
    raisons = []
    if ind["sous_mm200"]:
        points += 1
        raisons.append("sous la moyenne 200 j")
    if ind["baisse_plus_haut"] >= s["baisse_depuis_plus_haut_stress"]:
        points += 2
        raisons.append("-%.0f %% depuis le plus haut" % (100 * ind["baisse_plus_haut"]))
    elif ind["baisse_plus_haut"] >= s["baisse_depuis_plus_haut_tendu"]:
        points += 1
        raisons.append("-%.0f %% depuis le plus haut" % (100 * ind["baisse_plus_haut"]))
    if ind["ratio_vol"] >= s["ratio_vol_stress"]:
        points += 2
        raisons.append("volatilité x%.1f" % ind["ratio_vol"])
    elif ind["ratio_vol"] >= s["ratio_vol_tendu"]:
        points += 1
        raisons.append("volatilité x%.1f" % ind["ratio_vol"])
    if ind["variation_5j"] <= s["variation_5j_tendu"]:
        points += 1
        raisons.append("%.1f %% sur 5 jours" % (100 * ind["variation_5j"]))
    if points >= cfg_m["points_stress"]:
        c = "stress"
    elif points >= cfg_m["points_tendu"]:
        c = "tendu"
    else:
        c = "calme"
    return c, points, raisons


def trouver_ids(api, symboles):
    ids = {}
    try:
        for ins in api.instruments(symboles=symboles):
            sym = str(champ(ins, "symbol", "Symbol", "symbolFull", defaut="")).upper()
            iid = champ(ins, "instrumentId", "instrumentID", "InstrumentID")
            if sym and iid is not None:
                ids[sym] = iid
    except Exception as exc:  # noqa: BLE001
        log.warning("Marché : instruments introuvables (%s)", exc)
    return ids


def analyser_marche(api, cfg, etat=None, aujourd_hui=None):
    """Analyse quotidienne. Renvoie un rapport et met à jour l'état."""
    cfg_m = cfg["marche"]
    aujourd_hui = aujourd_hui or dt.date.today()
    symboles = list(cfg_m["indices_decisifs"]) + list(cfg_m.get("indices_info", []))
    ids = trouver_ids(api, symboles)
    depuis = (aujourd_hui - dt.timedelta(days=420)).isoformat()
    rapport = {"indices": {}, "climat": "calme", "date": aujourd_hui.isoformat()}
    climats = []
    for sym in symboles:
        iid = ids.get(sym.upper())
        if iid is None:
            rapport["indices"][sym] = {"erreur": "instrument introuvable"}
            if sym in cfg_m["indices_decisifs"]:
                climats.append("tendu")  # sans données, on reste prudent
            continue
        try:
            serie = clotures(api.bougies(iid, "1d", depuis, 400))
            ind = indicateurs([c for _, c in serie])
        except Exception as exc:  # noqa: BLE001
            ind = None
            log.warning("Marché : bougies %s indisponibles (%s)", sym, exc)
        if ind is None:
            rapport["indices"][sym] = {"erreur": "historique insuffisant"}
            if sym in cfg_m["indices_decisifs"]:
                climats.append("tendu")
            continue
        c, pts, raisons = climat_indice(ind, cfg_m)
        ind.update({"climat": c, "points": pts, "raisons": raisons, "instrumentId": iid})
        rapport["indices"][sym] = ind
        if sym in cfg_m["indices_decisifs"]:
            climats.append(c)
    rapport["climat"] = pire("calme", *climats)
    rapport["exposition"] = cfg_m["exposition"][rapport["climat"]]
    if etat is not None:
        etat.data["marche"] = {
            "date": rapport["date"],
            "clotures": {s: v["dernier"] for s, v in rapport["indices"].items() if "dernier" in v},
            "ids": {s: v["instrumentId"] for s, v in rapport["indices"].items()
                    if "instrumentId" in v},
            "climat_jour": rapport["climat"],
        }
    log.info("Marché : climat %s (exposition %.0f %%)", rapport["climat"],
             100 * rapport["exposition"])
    return rapport


def controle_rapide(api, cfg, etat):
    """Compare les cours actuels à la dernière clôture.

    Renvoie (climat, alerte) ; alerte=True si une chute de -3 % vient d'être
    détectée (le Directeur doit alors réajuster).
    """
    cfg_m = cfg["marche"]
    m = etat.data.get("marche") or {}
    ids = {s: i for s, i in (m.get("ids") or {}).items() if s in cfg_m["indices_decisifs"]}
    ref = m.get("clotures") or {}
    climat_actuel = etat.data.get("climat", "calme")
    if not ids:
        return climat_actuel, False
    try:
        cours = api.cours(list(ids.values()))
    except Exception as exc:  # noqa: BLE001
        log.warning("Contrôle rapide du marché impossible (%s)", exc)
        return climat_actuel, False
    par_id = {}
    for c in cours:
        iid = champ(c, "instrumentId", "instrumentID", "InstrumentID")
        bid, ask = nombre(champ(c, "bid", "Bid")), nombre(champ(c, "ask", "Ask"))
        if iid is not None and bid and ask:
            par_id[str(iid)] = (bid + ask) / 2
    alerte = False
    for sym, iid in ids.items():
        prix, cloture = par_id.get(str(iid)), ref.get(sym)
        if prix and cloture:
            var = prix / cloture - 1
            if var <= cfg_m["chute_jour_stress"]:
                alerte = True
                etat.alerte("Chute de %.1f %% sur %s aujourd'hui : climat STRESS" % (
                    100 * var, sym))
    if alerte and climat_actuel != "stress":
        etat.data["climat"] = "stress"
        etat.data["exposition"] = cfg_m["exposition"]["stress"]
        return "stress", True
    return climat_actuel, False
