"""Lecture et normalisation des réponses eToro.

Toutes les fonctions acceptent plusieurs noms de champs possibles et
convertissent les unités selon config.yaml. Rien ici ne fait d'appel réseau.
"""
import datetime as dt

from .unites import en_decimal, nombre, unite


def champ(d, *noms, defaut=None):
    if not isinstance(d, dict):
        return defaut
    for n in noms:
        if n in d and d[n] is not None:
            return d[n]
    # insensible à la casse en dernier recours
    bas = {k.lower(): v for k, v in d.items()}
    for n in noms:
        v = bas.get(n.lower())
        if v is not None:
            return v
    return defaut


def lire_jour(valeur):
    """Date (datetime.date) à partir d'un timestamp texte ou numérique."""
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        sec = valeur / 1000 if valeur > 1e11 else valeur
        return dt.datetime.fromtimestamp(sec, dt.timezone.utc).date()
    texte = str(valeur).strip()
    try:
        return dt.datetime.fromisoformat(texte.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return dt.date.fromisoformat(texte[:10])
    except ValueError:
        return None


# --- Traders ------------------------------------------------------------
def normaliser_trader(row, cfg):
    gain = en_decimal(champ(row, "gain", "Gain"), unite(cfg, "gain_classement"))
    ptv = en_decimal(champ(row, "peakToValley", "PeakToValley"), unite(cfg, "peak_to_valley"))
    mois = en_decimal(champ(row, "profitableMonthsPct", "ProfitableMonthsPct"),
                      unite(cfg, "mois_gagnants"))
    return {
        "cid": champ(row, "cid", "CID", "customerId", "CustomerId", "parentCID"),
        "username": champ(row, "username", "userName", "UserName", defaut=""),
        "type": champ(row, "type", "Type", "accountType", defaut=""),
        "popular_investor": champ(row, "popularInvestor", "isPopularInvestor", defaut=None),
        "gain": gain,
        "risque": nombre(champ(row, "riskScore", "RiskScore")),
        "pic_risque": nombre(champ(row, "maxMonthlyRiskScore", "MaxMonthlyRiskScore")),
        "chute": abs(ptv) if ptv is not None else None,
        "mois_gagnants": mois,
        "copieurs": nombre(champ(row, "copiers", "Copiers"), 0),
        "trades": nombre(champ(row, "trades", "Trades"), 0),
    }


def gains_mensuels(data, cfg):
    """Liste triée de (date, rendement décimal) depuis /gain -> monthly[]."""
    lignes = champ(data, "monthly", "Monthly", defaut=[]) or []
    u = unite(cfg, "gain_mensuel")
    out = []
    for l in lignes:
        jour = lire_jour(champ(l, "timestamp", "Timestamp", "date", "start"))
        g = en_decimal(champ(l, "gain", "Gain"), u)
        if jour and g is not None:
            out.append((jour, g))
    out.sort()
    return out


def rendements_journaliers(liste, cfg):
    """dict date -> rendement décimal depuis /daily-gain."""
    u = unite(cfg, "gain_journalier")
    out = {}
    for l in liste or []:
        jour = lire_jour(champ(l, "timestamp", "Timestamp", "date", "Date"))
        g = en_decimal(champ(l, "gain", "Gain", "dailyGain"), u)
        if jour and g is not None:
            out[jour] = g
    return out


def stats_tradeinfo(data, cfg):
    u = unite(cfg, "tradeinfo_pct")
    derniere = lire_jour(champ(data, "lastActivity", "LastActivity"))
    return {
        "levier_fort": en_decimal(champ(data, "highLeveragePct"), u),
        "copie_autres": en_decimal(champ(data, "copyInvestmentPct"), u),
        "semaines_actives": en_decimal(champ(data, "activeWeeksPct"), u),
        "derniere_activite": derniere,
        "risque": nombre(champ(data, "riskScore", "RiskScore")),
        "chute_jour": en_decimal(champ(data, "dailyDd", "DailyDD"), u),
    }


# --- Portefeuille en direct d'un trader ---------------------------------
def analyser_portefeuille_live(data, cfg):
    """Poids par instrument (somme = 1) et parts levier / vente à découvert."""
    positions = champ(data, "positions", "Positions", defaut=[]) or []
    u = unite(cfg, "portefeuille_pct")
    poids = {}
    levier = decouvert = total = 0.0
    levier_moyen_num = 0.0
    for p in positions:
        w = en_decimal(champ(p, "investmentPct", "InvestmentPct"), u, 0.0) or 0.0
        if w <= 0:
            continue
        iid = champ(p, "instrumentId", "InstrumentID", "instrumentID")
        if iid is None:
            continue
        lev = nombre(champ(p, "leverage", "Leverage"), 1.0) or 1.0
        achat = champ(p, "isBuy", "IsBuy", defaut=True)
        poids[iid] = poids.get(iid, 0.0) + w
        total += w
        levier_moyen_num += w * lev
        if lev > 1:
            levier += w
        if achat is False or str(achat).lower() == "false":
            decouvert += w
    if total <= 0:
        return {"poids": {}, "part_levier": 0.0, "part_decouvert": 0.0,
                "position_max": 0.0, "levier_moyen": 1.0, "nb_positions": 0}
    poids = {k: v / total for k, v in poids.items()}
    return {
        "poids": poids,
        "part_levier": levier / total,
        "part_decouvert": decouvert / total,
        "position_max": max(poids.values()),
        "levier_moyen": levier_moyen_num / total,
        "nb_positions": len(poids),
    }


# --- Notre portefeuille ---------------------------------------------------
def mirrors(portefeuille):
    return champ(portefeuille, "mirrors", "Mirrors", defaut=[]) or []


def mirror_id(m):
    v = champ(m, "mirrorID", "mirrorId", "MirrorID")
    return None if v is None else str(v)


def valeur_mirror(m):
    """Valeur actuelle d'une copie = cash disponible + positions + gains latents."""
    valeur = nombre(champ(m, "availableAmount", "AvailableAmount"), 0.0) or 0.0
    for p in champ(m, "positions", "Positions", defaut=[]) or []:
        valeur += nombre(champ(p, "amount", "Amount"), 0.0) or 0.0
        pnl = champ(p, "unrealizedPnL", "UnrealizedPnL")
        if isinstance(pnl, dict):
            valeur += nombre(champ(pnl, "pnL", "pnl", "PnL"), 0.0) or 0.0
        else:
            valeur += nombre(pnl, 0.0) or 0.0
    return valeur


# --- Bougies ---------------------------------------------------------------
def clotures(bougies):
    """Liste triée (date, cours de clôture) ; les prix arrivent en texte."""
    out = []
    for b in bougies or []:
        jour = lire_jour(champ(b, "fromDate", "date", "timestamp", "time", "FromDate"))
        c = nombre(champ(b, "close", "Close"))
        if jour and c:
            out.append((jour, c))
    out.sort()
    return out
