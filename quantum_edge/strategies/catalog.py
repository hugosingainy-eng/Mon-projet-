"""Catalogue des familles de stratégies qui entrent en compétition.

Chaque famille traduit un PRINCIPE de recherche d'un grand trader en une hypothèse
testable (on ne copie aucun trade). Toutes sont à l'achat, sans levier, avec un
ratio gain/risque d'au moins 2:1 (règle du risk manager).
"""
from __future__ import annotations

import pandas as pd

from .. import indicators as ind
from .base import Family, frame

RR = [2.0, 3.0]


class TrendFollowing(Family):
    def __init__(self):
        super().__init__(
            "trend_following",
            "Une cassure du plus haut de N jours dans une tendance haussière tend à se prolonger.",
            "Ed Seykota / Turtle Traders : suivi de tendance systématique",
            {"n": [20, 55], "stop_atr": [2.0, 3.0], "rr": RR},
        )

    def signals(self, df, p, ctx):
        c = df["close"]
        hh = df["high"].rolling(p["n"]).max().shift(1)
        trend = ind.ema(c, 50) > ind.ema(c, 200)
        return frame(df, (c > hh) & trend, p["stop_atr"] * ind.atr(df, 20), p["rr"])


class Momentum(Family):
    def __init__(self):
        super().__init__(
            "momentum",
            "Un actif en forte hausse sur 3-6 mois qui reprend après un repli continue de surperformer.",
            "Stanley Druckenmiller / momentum de séries temporelles",
            {"lookback": [63, 126], "stop_atr": [1.5, 2.5], "rr": RR},
        )

    def signals(self, df, p, ctx):
        c = df["close"]
        e20 = ind.ema(c, 20)
        strong = (c / c.shift(p["lookback"]) - 1) > 0.10
        pullback = df["low"].rolling(5).min() <= e20 * 1.01
        trigger = (c > df["high"].shift(1)) & (c > e20) & (c > ind.sma(c, 50))
        return frame(df, strong & pullback & trigger, p["stop_atr"] * ind.atr(df, 14), p["rr"])


class MeanReversion(Family):
    def __init__(self):
        super().__init__(
            "mean_reversion",
            "Un excès de vente de court terme dans une tendance de fond haussière se corrige.",
            "Jim Simons (anomalies statistiques) / Larry Connors (RSI-2)",
            {"rsi_thr": [5, 10], "stop_atr": [1.5, 2.5], "rr": RR},
        )

    def signals(self, df, p, ctx):
        c = df["close"]
        bb = ind.bollinger(c, 20, 2.0)
        oversold = (ind.rsi(c, 2) < p["rsi_thr"]) | (c < bb["lower"])
        return frame(df, (c > ind.sma(c, 200)) & oversold, p["stop_atr"] * ind.atr(df, 14), p["rr"])


class VolatilityBreakout(Family):
    def __init__(self):
        super().__init__(
            "volatility_breakout",
            "Après une compression de volatilité, la sortie du range par le haut amorce un mouvement.",
            "Paul Tudor Jones (asymétrie) / squeeze de Bollinger",
            {"squeeze_q": [0.10, 0.20], "stop_atr": [1.5, 2.5], "rr": RR},
        )

    def signals(self, df, p, ctx):
        c = df["close"]
        bb = ind.bollinger(c, 20, 2.0)
        q = bb["width"].rolling(120, min_periods=60).quantile(p["squeeze_q"])
        squeeze = (bb["width"] <= q).shift(1).rolling(5).max().astype(bool)
        entry = squeeze & (c > bb["upper"]) & (c > ind.sma(c, 200))
        return frame(df, entry, p["stop_atr"] * ind.atr(df, 14), p["rr"])


class MultiTimeframe(Family):
    def __init__(self):
        super().__init__(
            "multi_timeframe",
            "Un signal journalier n'est fiable que s'il va dans le sens de la tendance hebdomadaire.",
            "Confirmation multi-unités de temps (pratique des desks systématiques)",
            {"weekly_ema": [10, 20], "stop_atr": [1.5, 2.5], "rr": RR},
        )

    def signals(self, df, p, ctx):
        c = df["close"]
        wk = c.resample("W-FRI").last().dropna()
        wk_up = (wk > ind.ema(wk, p["weekly_ema"])).astype(float)
        # valeur hebdo connue seulement à la clôture du vendredi : pas de biais du futur
        weekly_trend = wk_up.reindex(df.index, method="ffill").fillna(0).astype(bool)
        e9, e21 = ind.ema(c, 9), ind.ema(c, 21)
        cross = (e9 > e21) & (e9.shift(1) <= e21.shift(1))
        entry = weekly_trend & cross & (ind.macd(c)["hist"] > 0)
        return frame(df, entry, p["stop_atr"] * ind.atr(df, 14), p["rr"])


class RelativeStrength(Family):
    def __init__(self):
        super().__init__(
            "relative_strength",
            "Les actifs qui battent le marché sur 3 mois et touchent un plus haut continuent de mener.",
            "Druckenmiller / O'Neil : acheter les leaders quand le marché est sain",
            {"thr": [0.0, 0.05], "stop_atr": [2.0, 3.0], "rr": RR},
        )

    def signals(self, df, p, ctx):
        c = df["close"]
        bench = ctx.get("bench")
        if bench is None:
            return frame(df, pd.Series(False, index=df.index), ind.atr(df, 14), p["rr"])
        b = bench["close"].reindex(df.index).ffill()
        rs = (c / c.shift(63)) - (b / b.shift(63))
        healthy = b > ind.sma(b, 200)
        at_high = c >= df["high"].rolling(20).max().shift(1)
        return frame(df, (rs > p["thr"]) & healthy & at_high, p["stop_atr"] * ind.atr(df, 14), p["rr"])


FAMILIES: list[Family] = [
    TrendFollowing(), Momentum(), MeanReversion(), VolatilityBreakout(), MultiTimeframe(), RelativeStrength(),
]
FAMILY_BY_NAME = {f.name: f for f in FAMILIES}


def compute_signals(spec, df: pd.DataFrame, ctx: dict) -> pd.DataFrame:
    return FAMILY_BY_NAME[spec.family].signals(df, spec.p, ctx)


def all_specs() -> list:
    return [s for f in FAMILIES for s in f.specs()]

