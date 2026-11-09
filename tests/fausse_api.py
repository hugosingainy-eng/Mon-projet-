"""Fausse API eToro pour les tests : aucune connexion réseau.

Elle imite les méthodes de bot.etoro_client.EtoroClient et garde la trace de
chaque appel (pour vérifier qu'aucun ordre n'est passé en dry-run, que les
copies personnelles ne sont jamais touchées, etc.).
"""
import datetime as dt

import numpy as np

AUJOURD_HUI = dt.date(2026, 11, 9)
INDICES = {"SPX500": 1, "NSDQ100": 2, "GOLD": 3, "BTC": 4}


def fabrique_trader(username, cid, instruments=None, graine=0, moyenne=0.08, ecart=0.5,
                    **surcharges):
    """Un trader « bon élève » par défaut. Les surcharges modifient la ligne du classement
    (row), l'historique (monthly), le style (tradeinfo) ou le portefeuille (positions)."""
    rng = np.random.default_rng(graine)
    instruments = instruments or [cid * 10 + i for i in range(5)]
    row = {"cid": cid, "username": username, "type": "PopularInvestor", "gain": 0.30,
           "riskScore": 3, "maxMonthlyRiskScore": 4, "peakToValley": -10.0,
           "profitableMonthsPct": 70.0, "copiers": 1500, "trades": 300}
    row.update(surcharges.pop("row", {}))
    mois = []
    d = dt.date(2023, 1, 1)
    for i in range(46):
        mois.append({"timestamp": d.isoformat() + "T00:00:00Z", "gain": 2.0})
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    if "monthly" in surcharges:
        mois = surcharges.pop("monthly")
    jours = {}
    for k in range(800):
        jour = AUJOURD_HUI - dt.timedelta(days=800 - k)
        jours[jour.isoformat()] = float(rng.normal(moyenne, ecart))
    jours.update(surcharges.pop("daily", {}))
    info = {"highLeveragePct": 2.0, "copyInvestmentPct": 0.0, "activeWeeksPct": 92.0,
            "lastActivity": (AUJOURD_HUI - dt.timedelta(days=1)).isoformat() + "T10:00:00Z",
            "riskScore": 3, "dailyDd": -1.0}
    info.update(surcharges.pop("tradeinfo", {}))
    n = len(instruments)
    positions = [{"instrumentId": iid, "investmentPct": 100.0 / n, "isBuy": True,
                  "leverage": 1, "stopLossRate": 0} for iid in instruments]
    if "positions" in surcharges:
        positions = surcharges.pop("positions")
    assert not surcharges, "surcharges inconnues : %s" % surcharges
    return {"row": row, "monthly": mois, "daily": jours, "tradeinfo": info,
            "positions": positions}


class FausseAPI:
    def __init__(self, traders=None, prix_indices=None, cours_actuels=None):
        self.traders = {}
        for t in traders or []:
            self.traders[t["row"]["username"]] = t
        self.mirrors = {}
        self.prochain_mirror = 5000
        self.ordres = {}
        self.appels = []
        self.cours_actuels = cours_actuels or {}
        self.prix_indices = prix_indices or {s: [100.0 + 0.05 * i for i in range(420)]
                                             for s in INDICES}
        self.refuser_eligibilite = False
        self.mode = "demo"

    def _note(self, nom, *args):
        self.appels.append((nom, args))

    def appels_ordres(self):
        return [a for a in self.appels if a[0] in ("copie_ordre", "copie_fermer",
                                                    "copie_eligibilite")]

    # --- portefeuille ---------------------------------------------------
    def ajouter_mirror_perso(self, parent_cid, valeur=500.0):
        mid = self.prochain_mirror
        self.prochain_mirror += 1
        self.mirrors[mid] = {"mirrorID": mid, "parentCID": parent_cid,
                             "availableAmount": valeur, "positions": []}
        return mid

    def fixer_valeur(self, mid, valeur):
        m = self.mirrors[int(mid)]
        m["availableAmount"] = 0.0
        m["positions"] = [{"amount": valeur, "unrealizedPnL": {"pnL": 0.0}}]

    def portefeuille(self):
        self._note("portefeuille")
        return {"credit": 10000.0, "positions": [],
                "mirrors": [dict(m) for m in self.mirrors.values()]}

    # --- classement / traders ------------------------------------------
    def classement(self, page=1, taille=100, periode="OneYearAgo", **filtres):
        self._note("classement", page)
        lignes = [t["row"] for t in self.traders.values()]
        return lignes[(page - 1) * taille: page * taille]

    def gains(self, username):
        self._note("gains", username)
        return {"monthly": self.traders[username]["monthly"], "yearly": []}

    def gains_journaliers(self, username, date_min, date_max):
        self._note("gains_journaliers", username)
        return [{"date": d, "gain": g} for d, g in self.traders[username]["daily"].items()
                if date_min <= d <= date_max]

    def trade_info(self, username, periode="OneYearAgo"):
        self._note("trade_info", username)
        return dict(self.traders[username]["tradeinfo"])

    def portefeuille_live(self, username):
        self._note("portefeuille_live", username)
        return {"positions": self.traders[username]["positions"], "socialTrades": []}

    # --- marché -----------------------------------------------------------
    def instruments(self, symboles=None, ids=None):
        out = []
        for s in symboles or []:
            if s in INDICES:
                out.append({"instrumentId": INDICES[s], "symbol": s, "displayName": s})
        for i in ids or []:
            out.append({"instrumentId": i, "symbol": "TCK%s" % i, "displayName": "Action %s" % i})
        return out

    def bougies(self, instrument_id, intervalle="1d", depuis=None, limite=400):
        sym = {v: k for k, v in INDICES.items()}[instrument_id]
        prix = self.prix_indices[sym][-limite:]
        n = len(prix)
        return [{"fromDate": (AUJOURD_HUI - dt.timedelta(days=n - i)).isoformat()
                 + "T00:00:00Z", "close": "%.4f" % p} for i, p in enumerate(prix)]

    def cours(self, ids):
        out = []
        for s, iid in INDICES.items():
            if iid in ids and s in self.cours_actuels:
                p = self.cours_actuels[s]
                out.append({"instrumentId": iid, "bid": p - 0.01, "ask": p + 0.01})
        return out

    # --- copie ------------------------------------------------------------
    def copie_eligibilite(self, parent_cid, montant):
        self._note("copie_eligibilite", parent_cid, montant)
        return not self.refuser_eligibilite

    def copie_ordre(self, parent_cid, montant, reference_id):
        self._note("copie_ordre", parent_cid, montant, reference_id)
        assert len(reference_id) <= 35
        for mid, m in self.mirrors.items():
            if m["parentCID"] == parent_cid:
                m["availableAmount"] += montant
                self.ordres[reference_id] = {"isSuccess": True, "mirrorID": mid}
                return {"referenceID": reference_id}
        mid = self.prochain_mirror
        self.prochain_mirror += 1
        self.mirrors[mid] = {"mirrorID": mid, "parentCID": parent_cid,
                             "availableAmount": float(montant), "positions": []}
        self.ordres[reference_id] = {"isSuccess": True, "mirrorID": mid}
        return {"referenceID": reference_id}

    def copie_suivi(self, reference_id):
        return self.ordres.get(reference_id)

    def attendre_copie(self, reference_id, intervalle=0):
        return self.ordres.get(reference_id)

    def copie_fermer(self, mirror_id, client_request_id):
        self._note("copie_fermer", mirror_id)
        self.mirrors.pop(int(mirror_id), None)
        return {"isSuccess": True}


class FauxOutils:
    """Remplace les scripts trader-skill : `reponses` = script -> objet ou exception."""

    def __init__(self, reponses=None):
        self.reponses = reponses or {}
        self.appels = []

    def lancer(self, script, *args):
        self.appels.append((script, args))
        r = self.reponses.get(script)
        if isinstance(r, Exception):
            raise r
        if callable(r):
            return r(*args)
        return r


class FausseIA:
    sait_chercher_sur_x = False

    def __init__(self, reponse="{}", erreur=None, x=False):
        self.reponse = reponse
        self.erreur = erreur
        self.questions = []
        self.sait_chercher_sur_x = x

    def demander(self, systeme, message, recherche=True, recherche_x=False):
        self.questions.append((systeme, message, recherche_x))
        if self.erreur:
            raise self.erreur
        return self.reponse(systeme, message) if callable(self.reponse) else self.reponse
