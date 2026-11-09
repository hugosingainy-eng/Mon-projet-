"""Outils de validation : découpage temporel, walk-forward, biais du futur,
sensibilité aux coûts / retards, stabilité des paramètres, régimes."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from ..strategies.catalog import compute_signals


def market_regimes(bench: pd.DataFrame) -> pd.Series:
    c = bench["close"]
    s50, s200 = ind.sma(c, 50), ind.sma(c, 200)
    reg = pd.Series("sideways", index=bench.index)
    reg[(c > s200) & (s50 > s200)] = "bull"
    reg[(c < s200) & (s50 < s200)] = "bear"
    reg[s200.isna()] = "unknown"
    return reg


def split_dates(dates: pd.DatetimeIndex, train_frac: float, valid_frac: float):
    n = len(dates)
    return dates[0], dates[int(n * train_frac)], dates[int(n * (train_frac + valid_frac))], dates[-1]


def in_window(trades: pd.DataFrame, start, end) -> pd.DataFrame:
    """Trades entièrement contenus dans [start, end) : aucune fuite entre périodes."""
    if len(trades) == 0:
        return trades
    m = (trades["entry_date"] >= start) & (trades["exit_date"] < end)
    return trades[m]


def walk_forward_windows(dates: pd.DatetimeIndex, train_bars: int, test_bars: int):
    out = []
    start = train_bars
    while start + test_bars // 2 < len(dates):
        end = min(start + test_bars, len(dates) - 1)
        out.append((dates[start - train_bars], dates[start], dates[end]))
        start += test_bars
    return out


def lookahead_check(spec, data: dict, ctx: dict, n_dates: int = 6, seed: int = 0) -> tuple[bool, str]:
    """Recalcule les signaux sur des données TRONQUÉES et compare : toute différence
    à une date donnée prouve que la stratégie utilise des données futures."""
    rng = np.random.default_rng(seed)
    syms = list(data)[:3]
    for sym in syms:
        df = data[sym]
        full = compute_signals(spec, df, ctx)
        idx = rng.choice(np.arange(260, len(df) - 5), size=min(n_dates, max(1, len(df) - 270)), replace=False)
        for i in idx:
            d = df.index[i]
            cut_ctx = {k: (v.loc[:d] if isinstance(v, pd.DataFrame) else v) for k, v in ctx.items()}
            part = compute_signals(spec, df.loc[:d], cut_ctx)
            a, b = full.loc[d], part.loc[d]
            if bool(a["entry"]) != bool(b["entry"]):
                return False, f"{sym} {d.date()}: signal différent avec données tronquées"
            if bool(a["entry"]) and not np.isclose(a["stop_dist"], b["stop_dist"], rtol=1e-6):
                return False, f"{sym} {d.date()}: stop différent avec données tronquées"
    return True, "aucun biais du futur détecté"


def regime_breakdown(trades: pd.DataFrame) -> dict:
    if len(trades) == 0:
        return {}
    g = trades.groupby("regime")["r"]
    return {k: {"n": int(v.count()), "ev_r": float(v.mean())} for k, v in g}


SURVIVORSHIP_WARNING = (
    "Biais du survivant NON corrigé : l'univers est composé d'actifs qui existent et "
    "sont populaires AUJOURD'HUI. Les données gratuites n'incluent pas les sociétés "
    "disparues. Les performances historiques sont donc probablement surestimées."
)
