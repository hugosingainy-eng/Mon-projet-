"""Faux serveur Capital.com (aucun réseau). Les réponses imitent la collection
Postman officielle de Capital.com."""
import datetime as dt
import json
import uuid

from faux_mt5 import AUJOURD_HUI, serie

MARCHES = {
    "US500": ("USD", 5000, 0.0007, 0.008, 1, 0.01),
    "US100": ("USD", 18000, 0.0008, 0.011, 2, 0.01),
    "DE40": ("EUR", 17000, 0.0005, 0.009, 3, 0.01),
    "GOLD": ("USD", 2000, 0.0006, 0.007, 4, 0.01),
    "EURUSD": ("USD", 1.08, -0.0002, 0.004, 5, 100),
    "USDJPY": ("JPY", 150, 0.0003, 0.005, 6, 100),
}


class Rep:
    def __init__(self, statut=200, corps=None, entetes=None):
        self.status_code = statut
        self._corps = corps if corps is not None else {}
        self.headers = entetes or {}
        self.text = json.dumps(self._corps)
        self.content = self.text.encode()

    def json(self):
        return self._corps


class FauxCapital:
    def __init__(self, solde=10000.0):
        self.series = {e: serie(p, t, v, graine=g) for e, (_, p, t, v, g, _m) in MARCHES.items()}
        self.solde = solde
        self.positions = {}
        self.confirms = {}
        self.ordres = []
        self.fermetures = []
        self.sessions = 0
        self.url = None
        self.expirer_session = False
        self.prix_force = {}

    def dernier(self, epic):
        return self.prix_force.get(epic, self.series[epic][-1][3])

    # --- requests.Session ---------------------------------------------------
    def post(self, url, json=None, headers=None, timeout=None):
        self.url = url
        assert url.endswith("/session") and headers.get("X-CAP-API-KEY")
        if json.get("password") != "secret":
            return Rep(401, {"errorCode": "error.invalid.details"})
        self.sessions += 1
        return Rep(200, {"currencyIsoCode": "EUR", "currentAccountId": "ACC1",
                         "accountType": "CFD"},
                   {"CST": "cst%d" % self.sessions, "X-SECURITY-TOKEN": "tok"})

    def request(self, methode, url, params=None, json=None, headers=None, timeout=None):
        assert "demo-api-capital" in url
        if self.expirer_session:
            self.expirer_session = False
            return Rep(401, {"errorCode": "error.invalid.session.token"})
        chemin = url.split("/api/v1", 1)[1]
        if chemin == "/session":
            return Rep(200, {"accountId": "ACC1", "currency": "EUR"})
        if chemin == "/accounts":
            return Rep(200, {"accounts": [{"accountId": "ACC1", "preferred": True,
                                           "currency": "EUR",
                                           "balance": {"balance": self.solde, "deposit": 10000,
                                                       "profitLoss": 0, "available": self.solde}}]})
        if chemin.startswith("/markets/"):
            epic = chemin.split("/")[-1]
            if epic not in MARCHES:
                return Rep(404, {"errorCode": "error.not-found.epic"})
            devise, *_r, mini = MARCHES[epic]
            p = self.dernier(epic)
            return Rep(200, {"instrument": {"epic": epic, "currency": devise},
                             "dealingRules": {"minDealSize": {"value": mini},
                                              "minNormalStopOrLimitDistance": {"value": 0.01}},
                             "snapshot": {"marketStatus": "TRADEABLE", "bid": p * 0.9999,
                                          "offer": p * 1.0001, "decimalPlacesFactor": 2}})
        if chemin.startswith("/prices/"):
            epic = chemin.split("/")[-1]
            s = self.series[epic][-int(params["max"]):]
            n = len(s)
            prix = []
            for i, (o, h, l, c) in enumerate(s):
                jour = AUJOURD_HUI - dt.timedelta(days=n - i)
                prix.append({"snapshotTimeUTC": jour.isoformat() + "T00:00:00",
                             "openPrice": {"bid": o, "ask": o}, "highPrice": {"bid": h, "ask": h},
                             "lowPrice": {"bid": l, "ask": l}, "closePrice": {"bid": c, "ask": c}})
            return Rep(200, {"prices": prix})
        if chemin == "/positions" and methode == "GET":
            return Rep(200, {"positions": list(self.positions.values())})
        if chemin == "/positions" and methode == "POST":
            self.ordres.append(json)
            deal = str(uuid.uuid4())
            ref = "o_" + deal
            p = self.dernier(json["epic"])
            self.positions[deal] = {
                "position": {"dealId": deal, "size": json["size"], "direction": "BUY",
                             "level": p * 1.0001, "upl": 0.0,
                             "currency": MARCHES[json["epic"]][0],
                             "stopLevel": json["stopLevel"]},
                "market": {"epic": json["epic"], "bid": p, "offer": p}}
            self.confirms[ref] = {"dealStatus": "ACCEPTED", "dealId": deal,
                                  "affectedDeals": [{"dealId": deal, "status": "OPENED"}]}
            return Rep(200, {"dealReference": ref})
        if chemin.startswith("/positions/") and methode == "DELETE":
            deal = chemin.split("/")[-1]
            self.fermetures.append(deal)
            self.positions.pop(deal, None)
            ref = "p_" + deal
            self.confirms[ref] = {"dealStatus": "ACCEPTED", "dealId": deal}
            return Rep(200, {"dealReference": ref})
        if chemin.startswith("/confirms/"):
            return Rep(200, self.confirms[chemin.split("/")[-1]])
        return Rep(404, {"errorCode": "inconnu"})

    # --- aides de test --------------------------------------------------------
    def position_perso(self, epic, taille=1.0):
        deal = "perso-" + epic
        p = self.dernier(epic)
        self.positions[deal] = {"position": {"dealId": deal, "size": taille, "direction": "BUY",
                                             "level": p, "upl": 0.0, "currency": "USD"},
                                "market": {"epic": epic, "bid": p, "offer": p}}
        return deal

    def fixer_upl(self, deal, upl):
        self.positions[deal]["position"]["upl"] = upl

    def toucher_stop(self, deal):
        self.positions.pop(deal)
