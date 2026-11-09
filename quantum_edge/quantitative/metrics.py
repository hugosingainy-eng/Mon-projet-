"""Statistiques de performance sur une liste de trades (en multiples de R)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def trade_metrics(trades: pd.DataFrame, risk_per_trade: float = 0.005, seed: int = 0) -> dict:
    if trades is None or len(trades) == 0:
        return {"n": 0, "ev_r": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "sharpe": 0.0, "sortino": 0.0,
                "max_dd_r": 0.0, "max_dd_pct": 0.0, "avg_win_r": 0.0, "avg_loss_r": 0.0, "std_r": 0.0,
                "tstat": 0.0, "ci_low": 0.0, "ci_high": 0.0, "trades_per_year": 0.0}
    r = trades["r"].to_numpy(float)
    n = len(r)
    wins, losses = r[r > 0], r[r <= 0]
    std = r.std(ddof=1) if n > 1 else 0.0
    span_years = max((pd.Timestamp(trades["exit_date"].max()) - pd.Timestamp(trades["entry_date"].min())).days
                     / 365.25, 0.25)
    tpy = n / span_years
    down = r[r < 0]
    dstd = np.sqrt((down ** 2).mean()) if len(down) else 0.0
    eq = np.cumsum(r[np.argsort(trades["exit_date"].to_numpy())])
    dd_r = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    rng = np.random.default_rng(seed)
    boots = rng.choice(r, size=(2000, n), replace=True).mean(1) if n > 1 else np.array([r.mean()])
    return {
        "n": int(n),
        "ev_r": float(r.mean()),
        "win_rate": float((r > 0).mean()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "avg_win_r": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss_r": float(losses.mean()) if len(losses) else 0.0,
        "std_r": float(std),
        "tstat": float(r.mean() / (std / np.sqrt(n))) if std > 0 else 0.0,
        "ci_low": float(np.percentile(boots, 5)),       # IC 90 % bootstrap de l'espérance
        "ci_high": float(np.percentile(boots, 95)),
        "sharpe": float(r.mean() / std * np.sqrt(tpy)) if std > 0 else 0.0,
        "sortino": float(r.mean() / dstd * np.sqrt(tpy)) if dstd > 0 else 0.0,
        "max_dd_r": dd_r,
        "max_dd_pct": dd_r * risk_per_trade,
        "trades_per_year": float(tpy),
    }


def clean(d: dict) -> dict:
    """Valeurs JSON-compatibles (inf -> grand nombre)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, float) and not np.isfinite(v):
            v = 999.0 if v > 0 else -999.0
        out[k] = v
    return out
