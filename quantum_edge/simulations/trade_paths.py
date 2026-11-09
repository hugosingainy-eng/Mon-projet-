"""Monte-Carlo au niveau du TRADE candidat (10 000 à 100 000 trajectoires de prix).

Mélange de trajectoires :
  1. conditionnelles : ce qui a suivi ce même setup dans le passé (actif + univers),
     normalisé par la volatilité puis remis à l'échelle de la volatilité actuelle ;
  2. "sans edge" (part = shrinkage) : bootstrap par blocs des rendements de l'actif,
     moyenne retirée — garde-fou contre les illusions statistiques ;
  3. chocs : 2 % de gaps de 3 à 6 écarts-types contre la position ;
  + incertitude de volatilité (±15 %) et slippage aléatoire.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

BLOCK = 5


@dataclass
class PathReport:
    paths: int = 0
    p_win: float = 0.0
    p_stop: float = 0.0
    p_target: float = 0.0
    p_big_loss: float = 0.0
    expected_r: float = 0.0
    r_p05: float = 0.0
    r_p50: float = 0.0
    r_p95: float = 0.0
    cvar5_r: float = 0.0
    batch_agreement: float = 0.0
    n_conditional_sources: int = 0

    def to_dict(self):
        return asdict(self)


def simulate_exits(logret: np.ndarray, stop_pct, target_pct):
    """Sorties (achat) sur trajectoires de clôtures : 0=temps 1=stop 2=objectif."""
    n, h = logret.shape
    ret = np.expm1(np.cumsum(logret, axis=1))
    stop_pct = np.broadcast_to(np.asarray(stop_pct, float), (n,))
    target_pct = np.broadcast_to(np.asarray(target_pct, float), (n,))
    hs, ht = ret <= -stop_pct[:, None], ret >= target_pct[:, None]
    big = h + 1
    fs = np.where(hs.any(1), hs.argmax(1), big)
    ft = np.where(ht.any(1), ht.argmax(1), big)
    out = ret[:, -1].copy()
    kind = np.zeros(n, np.int8)
    s_first = (fs < big) & (fs <= ft)
    t_first = (ft < big) & (ft < fs)
    idx = np.arange(n)
    out[s_first] = ret[idx[s_first], fs[s_first]]
    kind[s_first] = 1
    out[t_first] = target_pct[t_first]
    kind[t_first] = 2
    return out, kind


def _block_bootstrap(z, n, h, rng):
    z = z - z.mean()
    nb = int(np.ceil(h / BLOCK))
    starts = rng.integers(0, max(1, len(z) - BLOCK), size=(n, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(n, -1)[:, :h]
    return z[np.clip(idx, 0, len(z) - 1)]


def run_trade_paths(stop_pct: float, target_pct: float, vol: float, cost_pct: float,
                    cond_z: np.ndarray, uncond_z: np.ndarray, n_paths: int = 50_000, horizon: int = 15,
                    shrinkage: float = 0.4, seed=None) -> PathReport:
    rng = np.random.default_rng(seed)
    if len(cond_z) == 0 or len(uncond_z) < 100 or vol <= 0:
        return PathReport()
    h = horizon
    n_null = int(n_paths * shrinkage)
    n_cond = n_paths - n_null
    z = np.empty((n_paths, h))
    z[:n_cond] = cond_z[rng.integers(0, len(cond_z), n_cond)][:, :h]
    z[n_cond:] = _block_bootstrap(uncond_z, n_null, h, rng)
    paths = z * vol * np.exp(rng.normal(0, 0.15, (n_paths, 1)))
    shock = rng.random(n_paths) < 0.02
    if shock.any():
        paths[np.flatnonzero(shock), rng.integers(0, h, shock.sum())] -= rng.uniform(3, 6, shock.sum()) * vol
    ret, kind = simulate_exits(paths, stop_pct, target_pct)
    slip = np.abs(rng.normal(0, 0.0005, n_paths)) * 2
    risk = stop_pct + cost_pct
    r = (ret - cost_pct - slip) / risk
    tail = np.sort(r)[: max(1, n_paths // 20)]
    batches = np.array_split(rng.permutation(r), 20)
    return PathReport(
        paths=n_paths, p_win=float((r > 0).mean()), p_stop=float((kind == 1).mean()),
        p_target=float((kind == 2).mean()), p_big_loss=float((r < -1.5).mean()),
        expected_r=float(r.mean()), r_p05=float(np.percentile(r, 5)), r_p50=float(np.median(r)),
        r_p95=float(np.percentile(r, 95)), cvar5_r=float(tail.mean()),
        batch_agreement=float(np.mean([b.mean() > 0 for b in batches])),
        n_conditional_sources=int(len(cond_z)),
    )
