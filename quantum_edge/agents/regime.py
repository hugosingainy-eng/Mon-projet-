"""Agent 1 — Analyste du régime de marché."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from .base import NEUTRAL, OPPOSE, SUPPORT, Agent


def classify(df: pd.DataFrame) -> str:
    c = df["close"]
    if len(c) < 210:
        return "unknown"
    s50, s200 = ind.sma(c, 50).iloc[-1], ind.sma(c, 200).iloc[-1]
    if c.iloc[-1] > s200 and s50 > s200:
        return "bull"
    if c.iloc[-1] < s200 and s50 < s200:
        return "bear"
    return "sideways"


class RegimeAgent(Agent):
    name = "1_regime"
    role = "Analyste du régime de marché"

    def analyze(self, symbol: str, df: pd.DataFrame, bench: pd.DataFrame | None, allowed: list[str]):
        market = classify(bench) if bench is not None else "unknown"
        asset = classify(df)
        prev = classify(bench.iloc[:-10]) if bench is not None and len(bench) > 220 else market
        atrp = (ind.atr(df, 14) / df["close"]).dropna()
        pct = float((atrp.iloc[-252:] < atrp.iloc[-1]).mean()) if len(atrp) > 60 else 0.5
        vol_state = "high" if pct > 0.85 else "low" if pct < 0.15 else "normal"
        dollar_vol = float((df["close"] * df["volume"]).iloc[-20:].mean())
        liquidity = "unknown" if dollar_vol <= 0 else "low" if dollar_vol < 20e6 else "ok"
        adx = float(ind.adx(df).iloc[-1]) if len(df) > 50 else np.nan
        transition = market != prev
        details = {"market_regime": market, "asset_regime": asset, "volatility_state": vol_state,
                   "atr_percentile": pct, "transition_last_10d": transition, "avg_dollar_volume_20d": dollar_vol,
                   "liquidity": liquidity, "adx": adx, "strategy_allowed_regimes": allowed}
        if liquidity == "low":
            return self.report(symbol, OPPOSE, "liquidité insuffisante", 0.8, df.index[-1], **details)
        if allowed and market not in allowed:
            return self.report(symbol, OPPOSE, f"régime {market} : la stratégie n'a pas d'avantage prouvé dans ce "
                               f"régime (autorisé : {allowed})", 0.7, df.index[-1], **details)
        if vol_state == "high" or transition:
            return self.report(symbol, NEUTRAL, f"régime {market}, mais volatilité {vol_state}"
                               + (" et transition récente" if transition else ""), 0.5, df.index[-1], **details)
        return self.report(symbol, SUPPORT, f"régime {market} compatible, volatilité {vol_state}", 0.6,
                           df.index[-1], **details)
