"""Historique conditionnel d'un setup : trajectoires de prix qui ont suivi chaque
occurrence passée du signal (actif + univers), normalisées par la volatilité.
Sert au Monte-Carlo du trade candidat. Seules les occurrences dont l'issue est
connue à la date de décision sont utilisées."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from ..strategies.catalog import compute_signals


def first_in_cluster(entry: pd.Series, gap: int = 5) -> pd.Series:
    prior = entry.shift(1, fill_value=False).astype(int).rolling(gap, min_periods=1).max().astype(bool)
    return entry & ~prior


def conditional_paths(spec, data: dict, ctx: dict, symbol: str, horizon: int) -> tuple[np.ndarray, int, int]:
    own, pool = [], []
    for sym, df in data.items():
        sig = compute_signals(spec, df, ctx)
        e = first_in_cluster(sig["entry"]).to_numpy()
        vol = ind.realized_vol(df["close"], 20).to_numpy()
        lr = np.diff(np.log(df["close"].to_numpy(float)))
        idx = np.flatnonzero(e)
        idx = idx[(idx + horizon < len(df)) & np.isfinite(vol[idx]) & (vol[idx] > 0)]
        if len(idx) == 0:
            continue
        z = np.stack([lr[i:i + horizon] for i in idx]) / vol[idx][:, None]
        (own if sym == symbol else pool).append(z)
    own_z = np.concatenate(own) if own else np.empty((0, horizon))
    pool_z = np.concatenate(pool) if pool else np.empty((0, horizon))
    allz = np.concatenate([own_z, own_z, pool_z]) if len(own_z) + len(pool_z) else np.empty((0, horizon))
    return allz, len(own_z), len(pool_z)


def unconditional_z(df: pd.DataFrame) -> np.ndarray:
    lr = np.log(df["close"]).diff()
    z = (lr / ind.realized_vol(df["close"], 20).shift(1)).to_numpy()
    return z[np.isfinite(z)]
