"""Agent "historien" : retrouve toutes les fois où un setup est apparu dans le passé
(sur l'actif lui-même ET sur tout l'univers) et mesure ce qui s'est passé ensuite.

Les trajectoires qui ont suivi chaque setup sont normalisées par la volatilité du
moment, ce qui permet de les ré-utiliser pour simuler le trade d'aujourd'hui.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..config import OVERNIGHT_FEE_PER_DAY
from .. import indicators as ind
from ..strategies import Strategy
from .base import HistoryReport
from .exits import simulate_exits

CLUSTER_GAP = 5  # un même setup répété plusieurs jours de suite = une seule occurrence


def first_in_cluster(entry: pd.Series, gap: int = CLUSTER_GAP) -> pd.Series:
    prior = entry.shift(1, fill_value=False).astype(int).rolling(gap, min_periods=1).max().astype(bool)
    return entry & ~prior


@dataclass
class SetupRecords:
    entry_dates: np.ndarray
    avail_dates: np.ndarray    # date à laquelle l'issue du trade est connue
    z_paths: np.ndarray        # (M, H) rendements normalisés par la vol
    outcome_r: np.ndarray      # (M,) résultat net en multiples de R


def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["vol"] = ind.realized_vol(df["close"], 20)
    return df


class SetupLibrary:
    def __init__(self, data: dict, strategies: list[Strategy], horizon: int, costs: dict):
        self.h = horizon
        self.strategies = {s.name: s for s in strategies}
        self.records: dict[tuple, SetupRecords] = {}
        self.signals: dict[tuple, pd.DataFrame] = {}
        self.uncond: dict[str, tuple] = {}
        self.frames: dict[str, pd.DataFrame] = {}
        for sym, raw in data.items():
            df = prepare_frame(raw)
            self.frames[sym] = df
            lr = np.log(df["close"]).diff()
            z = (lr / df["vol"].shift(1)).to_numpy()
            ok = np.isfinite(z)
            self.uncond[sym] = (df.index.to_numpy()[ok], z[ok])
            for s in strategies:
                sig = s.signals(df)
                sig["entry"] = first_in_cluster(sig["entry"])
                self.signals[(sym, s.name)] = sig
                self.records[(sym, s.name)] = self._build(df, sig, s, costs.get(sym, 0.0015))

    def _build(self, df, sig, strat, cost) -> SetupRecords:
        close = df["close"].to_numpy(dtype=float)
        vol = df["vol"].to_numpy(dtype=float)
        lr = np.diff(np.log(close))
        idx = np.flatnonzero(sig["entry"].to_numpy())
        idx = idx[(idx + self.h < len(df)) & np.isfinite(vol[idx]) & (vol[idx] > 0)]
        h = self.h
        if len(idx) == 0:
            empty = np.empty(0, dtype=df.index.dtype)
            return SetupRecords(empty, empty, np.empty((0, h)), np.empty(0))
        fwd = np.stack([lr[i:i + h] for i in idx])
        stop = (sig["stop_dist"].to_numpy()[idx] / close[idx])
        tgt = (sig["target_dist"].to_numpy()[idx] / close[idx])
        ret, bars, _ = simulate_exits(fwd, strat.direction, stop, tgt)
        fees = cost + (OVERNIGHT_FEE_PER_DAY * bars if strat.direction < 0 else 0.0)
        dates = df.index.to_numpy()
        return SetupRecords(
            entry_dates=dates[idx],
            avail_dates=dates[idx + h],
            z_paths=fwd / vol[idx][:, None],
            outcome_r=(ret - fees) / stop,
        )

    # ------------------------------------------------------------------ requêtes
    def query(self, symbol: str, strategy: str, asof) -> tuple:
        """Occurrences dont l'issue était connue à la date `asof` (pas de biais du futur)."""
        asof = np.datetime64(pd.Timestamp(asof))
        own_z, own_r, pool_z, pool_r = [], [], [], []
        for (sym, strat), rec in self.records.items():
            if strat != strategy or len(rec.outcome_r) == 0:
                continue
            m = rec.avail_dates <= asof
            if sym == symbol:
                own_z.append(rec.z_paths[m]); own_r.append(rec.outcome_r[m])
            else:
                pool_z.append(rec.z_paths[m]); pool_r.append(rec.outcome_r[m])
        h = self.h
        cat = lambda xs, shape: np.concatenate(xs) if xs else np.empty(shape)
        return (cat(own_z, (0, h)), cat(own_r, (0,)), cat(pool_z, (0, h)), cat(pool_r, (0,)))

    def unconditional(self, symbol: str, asof) -> np.ndarray:
        dates, z = self.uncond[symbol]
        return z[dates <= np.datetime64(pd.Timestamp(asof))]


def history_report(own_r: np.ndarray, pool_r: np.ndarray) -> HistoryReport:
    allr = np.concatenate([own_r, own_r, pool_r])  # l'actif lui-même compte double
    n = len(own_r) + len(pool_r)
    if n == 0:
        return HistoryReport()
    gains = allr[allr > 0].sum()
    losses = -allr[allr < 0].sum()
    std = allr.std(ddof=1) if len(allr) > 1 else np.inf
    return HistoryReport(
        n_own=int(len(own_r)),
        n_pool=int(len(pool_r)),
        win_rate=float((allr > 0).mean()),
        profit_factor=float(gains / losses) if losses > 0 else float("inf"),
        mean_r=float(allr.mean()),
        tstat=float(allr.mean() / (std / np.sqrt(n))) if std > 0 else 0.0,
    )
