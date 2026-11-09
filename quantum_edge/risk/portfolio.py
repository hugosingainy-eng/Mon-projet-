"""Moteur de risque de portefeuille : exposition, corrélation, concentration,
exposition ajustée de la volatilité, VaR et risque agrégé jusqu'aux stops."""
from __future__ import annotations

import numpy as np
import pandas as pd


def returns_matrix(data: dict, symbols: list[str], window: int = 60) -> pd.DataFrame:
    cols = {s: np.log(data[s]["close"]).diff() for s in symbols if s in data}
    return pd.DataFrame(cols).dropna().iloc[-window:]


def max_correlation(data: dict, candidate: str, open_symbols: list[str], window: int = 60) -> tuple[float, str]:
    others = [s for s in open_symbols if s != candidate]
    if not others or candidate not in data:
        return 0.0, ""
    rets = returns_matrix(data, [candidate] + others, window)
    if len(rets) < 20:
        return 1.0, "données insuffisantes pour la corrélation (prudence)"
    corr = rets.corr()[candidate].drop(candidate)
    worst = corr.idxmax()
    return float(corr.max()), str(worst)


def portfolio_risk(positions: list[dict], prices: dict, data: dict, equity: float) -> dict:
    if not positions:
        return {"exposure": 0.0, "exposure_pct": 0.0, "concentration": 0.0, "vol_adjusted_exposure": 0.0,
                "risk_to_stops": 0.0, "var95_1d": 0.0, "correlations": {}, "n": 0}
    vals = {p["symbol"]: p["units"] * prices.get(p["symbol"], p["entry"]) for p in positions}
    expo = sum(vals.values())
    syms = list(vals)
    rets = returns_matrix(data, syms, 60)
    vols = rets.std() if len(rets) else pd.Series(0.02, index=syms)
    vol_adj = float(sum(vals[s] * vols.get(s, 0.02) for s in syms))
    risk_stops = float(sum(max(0.0, p["units"] * (prices.get(p["symbol"], p["entry"]) - p["stop"]))
                           for p in positions))
    w = np.array([vals[s] for s in syms])
    if len(rets) >= 20 and len(syms) == rets.shape[1]:
        cov = rets[syms].cov().to_numpy()
        var95 = float(1.645 * np.sqrt(max(w @ cov @ w, 0.0)))
        corr = rets[syms].corr().round(2).to_dict()
    else:
        var95 = float(1.645 * vol_adj)
        corr = {}
    return {
        "exposure": expo, "exposure_pct": expo / equity if equity else 0.0,
        "concentration": max(vals.values()) / equity if equity else 0.0,
        "vol_adjusted_exposure": vol_adj, "risk_to_stops": risk_stops, "var95_1d": var95,
        "correlations": corr, "n": len(positions),
    }
