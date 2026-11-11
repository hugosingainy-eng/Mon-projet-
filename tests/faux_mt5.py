"""Faux module MetaTrader5 pour les tests : imite les fonctions du module officiel,
sans réseau et sans Windows."""
import datetime as dt
from collections import namedtuple

import numpy as np

Compte = namedtuple("Compte", "login server currency balance equity trade_mode")
Info = namedtuple("Info", "name volume_min volume_step volume_max digits filling_mode "
                          "trade_contract_size")
Tick = namedtuple("Tick", "bid ask")
Position = namedtuple("Position", "ticket symbol volume type price_open price_current sl tp "
                                  "profit magic comment")
Resultat = namedtuple("Resultat", "retcode order deal comment")
Deal = namedtuple("Deal", "position_id profit commission swap fee")
Sym = namedtuple("Sym", "name")

AUJOURD_HUI = dt.date(2026, 11, 11)


def serie(prix0=100.0, tendance=0.0006, vol=0.008, n=900, graine=0, krach_a=None):
    rng = np.random.default_rng(graine)
    p, out = prix0, []
    for i in range(n):
        r = rng.normal(tendance, vol)
        if krach_a is not None and i >= krach_a:
            r = -abs(r) - 0.004
        o = p
        p = p * (1 + r)
        h, l = max(o, p) * (1 + vol / 3), min(o, p) * (1 - vol / 3)
        out.append((o, h, l, p))
    return out


class FauxMT5:
    TIMEFRAME_D1 = 16408
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2

    def __init__(self, series=None, compte_reel=False, contrat=None):
        self.series = series or {
            "US500.cash": serie(5000, 0.0007, 0.008, graine=1),
            "US100.cash": serie(18000, 0.0008, 0.011, graine=2),
            "GER40": serie(17000, 0.0005, 0.009, graine=3),
            "XAUUSD": serie(2000, 0.0006, 0.007, graine=4),
            "EURUSD": serie(1.08, -0.0002, 0.004, graine=5),     # tendance baissière
            "USDJPY": serie(150, 0.0003, 0.005, graine=6),
        }
        self.contrat = contrat or {"US500.cash": 1, "US100.cash": 1, "GER40": 1,
                                   "XAUUSD": 100, "EURUSD": 100000, "USDJPY": 1000}
        self.compte_reel = compte_reel
        self.positions = {}
        self.fermees = {}
        self.prochain = 1000
        self.envois = []
        self.verifs = []
        self.initialise = False
        self.prix_force = {}

    # --- connexion ---------------------------------------------------------
    def initialize(self, **kw):
        self.initialise = True
        self.args = kw
        return True

    def shutdown(self):
        self.initialise = False

    def last_error(self):
        return (0, "ok")

    def terminal_info(self):
        return {"trade_allowed": True}

    def account_info(self):
        return Compte(12345, "Courtier-Demo", "EUR", 10000.0, 10000.0,
                      2 if self.compte_reel else 0)

    # --- marché ----------------------------------------------------------
    def symbols_get(self):
        return [Sym(n) for n in self.series]

    def symbol_select(self, sym, actif=True):
        return sym in self.series

    def symbol_info(self, sym):
        if sym not in self.series:
            return None
        pas = 0.01
        return Info(sym, 0.01, pas, 100.0, 2 if sym not in ("EURUSD",) else 5, 1,
                    self.contrat[sym])

    def dernier(self, sym):
        return self.prix_force.get(sym, self.series[sym][-1][3])

    def symbol_info_tick(self, sym):
        p = self.dernier(sym)
        return Tick(p * 0.9999, p * 1.0001)

    def copy_rates_from_pos(self, sym, tf, debut, nb):
        s = self.series[sym][-nb:]
        n = len(s)
        dtype = [("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                 ("close", "f8")]
        base = dt.datetime.combine(AUJOURD_HUI, dt.time(), dt.timezone.utc)
        return np.array([(int((base - dt.timedelta(days=n - i)).timestamp()), o, h, l, c)
                         for i, (o, h, l, c) in enumerate(s)], dtype=dtype)

    def order_calc_profit(self, action, sym, volume, prix_ouv, prix_ferm):
        return (prix_ferm - prix_ouv) * volume * self.contrat[sym]

    # --- ordres ------------------------------------------------------------
    def order_check(self, req):
        self.verifs.append(req)
        return Resultat(0, 0, 0, "Done")

    def order_send(self, req):
        self.envois.append(req)
        if "position" in req:
            p = self.positions.pop(req["position"])
            profit = (self.dernier(p.symbol) - p.price_open) * p.volume * self.contrat[p.symbol]
            self.fermees[p.ticket] = profit
            return Resultat(10009, self.prochain, self.prochain, "Done")
        t = self.prochain
        self.prochain += 1
        self.positions[t] = Position(t, req["symbol"], req["volume"], 0, req["price"],
                                     req["price"], req["sl"], 0.0, 0.0, req["magic"],
                                     req["comment"])
        return Resultat(10009, t, t, "Done")

    def ajouter_position_perso(self, sym, volume=1.0):
        t = self.prochain
        self.prochain += 1
        p = self.dernier(sym)
        self.positions[t] = Position(t, sym, volume, 0, p, p, 0.0, 0.0, 0.0, 0, "manuel")
        return t

    def fixer_profit(self, ticket, profit):
        self.positions[ticket] = self.positions[ticket]._replace(profit=profit)

    def toucher_stop(self, ticket, profit):
        """Le courtier ferme la position par son stop-loss."""
        self.positions.pop(ticket)
        self.fermees[ticket] = profit

    def positions_get(self):
        return tuple(self.positions.values())

    def history_deals_get(self, position=None, **kw):
        if position in self.fermees:
            return (Deal(position, self.fermees[position], -1.0, 0.0, 0.0),)
        return ()
