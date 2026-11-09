"""Stratégies inspirées de méthodes publiques de grands traders.

Chaque stratégie calcule, pour CHAQUE barre, s'il y a un signal d'entrée et les
distances de stop / objectif. Les mêmes règles servent :
  * au signal en direct (dernière barre),
  * à l'historique du setup (backtest agent),
  * aux simulations Monte-Carlo.
=> cohérence totale entre ce qui est testé et ce qui est tradé.

Sorties uniformes : stop, objectif, ou sortie au bout de `horizon` barres.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind


@dataclass(frozen=True)
class Strategy:
    name: str
    inspired_by: str
    direction: int  # +1 achat, -1 vente à découvert

    def signals(self, df: pd.DataFrame) -> pd.DataFrame:  # pragma: no cover - interface
        raise NotImplementedError

    @staticmethod
    def _frame(df, entry, stop_dist, target_dist):
        out = pd.DataFrame(index=df.index)
        out["entry"] = entry.fillna(False).astype(bool)
        out["stop_dist"] = stop_dist
        out["target_dist"] = target_dist
        valid = out["stop_dist"].gt(0) & out["target_dist"].gt(0)
        out["entry"] &= valid
        return out


class TurtleBreakout(Strategy):
    """Richard Dennis / les Turtles : cassure du plus haut 55 jours, stop 2 ATR."""

    def __init__(self):
        super().__init__("turtle_breakout", "Richard Dennis (Turtle Traders)", +1)

    def signals(self, df):
        a = ind.atr(df, 20)
        hh = df["high"].rolling(55).max().shift(1)
        trend = ind.sma(df["close"], 50) > ind.sma(df["close"], 200)
        entry = (df["close"] > hh) & trend
        return self._frame(df, entry, 2.0 * a, 4.0 * a)


class TurtleBreakdownShort(Strategy):
    """Version short des Turtles : cassure du plus bas 55 jours en tendance baissière."""

    def __init__(self):
        super().__init__("turtle_breakdown_short", "Richard Dennis (Turtle Traders)", -1)

    def signals(self, df):
        a = ind.atr(df, 20)
        ll = df["low"].rolling(55).min().shift(1)
        bear = (ind.sma(df["close"], 50) < ind.sma(df["close"], 200)) & (
            df["close"] < ind.sma(df["close"], 200)
        )
        entry = (df["close"] < ll) & bear
        return self._frame(df, entry, 2.0 * a, 3.0 * a)


class MinerviniTrendTemplate(Strategy):
    """Mark Minervini (SEPA / VCP) : tendance de fond saine + contraction de volatilité
    + cassure. Stop serré (max ~8 %), objectif 3R."""

    def __init__(self):
        super().__init__("minervini_vcp", "Mark Minervini (SEPA / VCP)", +1)

    def signals(self, df):
        c = df["close"]
        s50, s150, s200 = ind.sma(c, 50), ind.sma(c, 150), ind.sma(c, 200)
        hi52 = df["high"].rolling(252, min_periods=200).max()
        lo52 = df["low"].rolling(252, min_periods=200).min()
        template = (
            (c > s50) & (s50 > s150) & (s150 > s200)
            & (s200 > s200.shift(20))
            & (c >= 0.75 * hi52) & (c >= 1.30 * lo52)
        )
        contraction = (ind.atr(df, 10) / ind.atr(df, 50)) < 0.85
        pivot = df["high"].rolling(20).max().shift(1)
        vol_ok = True
        if "volume" in df and df["volume"].fillna(0).gt(0).any():
            vol_ok = df["volume"] > 1.2 * df["volume"].rolling(50).mean()
        entry = template & contraction.shift(1) & (c > pivot) & vol_ok
        stop = np.minimum(1.5 * ind.atr(df, 14), 0.08 * c)
        return self._frame(df, entry, stop, 3.0 * stop)


class ConnorsRSI2(Strategy):
    """Larry Connors : RSI(2) en survente au-dessus de la MM200 -> rebond court terme."""

    def __init__(self):
        super().__init__("connors_rsi2", "Larry Connors (RSI-2)", +1)

    def signals(self, df):
        c = df["close"]
        a = ind.atr(df, 14)
        entry = (c > ind.sma(c, 200)) & (ind.rsi(c, 2) < 10)
        return self._frame(df, entry, 2.5 * a, 1.5 * a)


class MomentumPullback(Strategy):
    """Kristjan Kullamägi (Qullamaggie) : leader en forte hausse, consolidation sur
    les moyennes courtes, reprise au-dessus du plus haut de la veille."""

    def __init__(self):
        super().__init__("momentum_pullback", "Kristjan Kullamägi (Qullamaggie)", +1)

    def signals(self, df):
        c = df["close"]
        e10, e20 = ind.ema(c, 10), ind.ema(c, 20)
        a = ind.atr(df, 14)
        strong = c / c.shift(63) > 1.25
        near_ma = (df["low"].rolling(3).min() <= e20 * 1.02) & (c > e20)
        rising = (e10 > e20) & (e20 > e20.shift(5))
        trigger = c > df["high"].shift(1)
        entry = strong & near_ma & rising & trigger
        stop = np.maximum(c - df["low"].rolling(3).min(), 0.75 * a)
        return self._frame(df, entry, stop, 3.0 * stop)


ALL_STRATEGIES: list[Strategy] = [
    TurtleBreakout(),
    TurtleBreakdownShort(),
    MinerviniTrendTemplate(),
    ConnorsRSI2(),
    MomentumPullback(),
]


def get_strategies(allow_short: bool = True) -> list[Strategy]:
    return [s for s in ALL_STRATEGIES if allow_short or s.direction > 0]
