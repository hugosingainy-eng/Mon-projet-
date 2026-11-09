"""Agent "régime de marché" : ne jamais nager contre le courant (Paul Tudor Jones :
"don't be a hero"). Analyse la tendance de l'actif et du marché global."""
from __future__ import annotations

import pandas as pd

from .. import indicators as ind
from .base import RegimeReport


def classify(df: pd.DataFrame) -> str:
    c = df["close"]
    if len(c) < 200:
        return "neutral"
    s50, s200 = ind.sma(c, 50).iloc[-1], ind.sma(c, 200).iloc[-1]
    last = c.iloc[-1]
    if last > s200 and s50 > s200:
        return "bull"
    if last < s200 and s50 < s200:
        return "bear"
    return "neutral"


def high_volatility(df: pd.DataFrame) -> bool:
    atrp = (ind.atr(df, 14) / df["close"]).dropna()
    if len(atrp) < 120:
        return False
    window = atrp.iloc[-252:]
    return bool(atrp.iloc[-1] > window.quantile(0.90))


def regime_report(df: pd.DataFrame, bench: pd.DataFrame | None, direction: int, strategy: str) -> RegimeReport:
    asset = classify(df)
    market = classify(bench) if bench is not None else "neutral"
    hv = high_volatility(df)
    rep = RegimeReport(asset_regime=asset, market_regime=market, high_volatility=hv)

    if direction > 0 and asset == "bear" and strategy != "connors_rsi2":
        rep.allowed, rep.reason = False, "achat refusé : actif en tendance baissière"
    elif direction < 0 and (asset != "bear" or market == "bull"):
        rep.allowed, rep.reason = False, "short refusé : pas de tendance baissière confirmée"

    mult = 1.0
    if direction > 0 and market == "bear":
        mult *= 0.5
    if direction < 0 and market == "bear":
        mult *= 1.0
    if hv:
        mult *= 0.5
    rep.risk_multiplier = mult
    return rep
