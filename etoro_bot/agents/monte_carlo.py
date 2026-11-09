"""Agent Monte-Carlo : rejoue le trade candidat des dizaines de milliers de fois.

Trois familles de trajectoires sont mélangées :
  1. Trajectoires CONDITIONNELLES : ce qui s'est réellement passé après ce même
     setup dans le passé (actif + univers), remises à l'échelle de la volatilité
     actuelle, avec une volatilité perturbée aléatoirement (±15 %).
  2. Trajectoires "SANS EDGE" (part = `shrinkage`) : bootstrap par blocs des
     rendements de l'actif, moyenne retirée. Elles supposent que le setup n'a
     aucun pouvoir prédictif : c'est le garde-fou anti sur-optimisation.
  3. Chocs de queue : 2 % des trajectoires reçoivent un gap de 3 à 6 écarts-types
     contre la position (annonces, résultats, krach).
Le trade n'est validé que s'il reste rentable malgré ce scénario pessimiste.
"""
from __future__ import annotations

import numpy as np

from ..config import OVERNIGHT_FEE_PER_DAY
from .base import Candidate, MonteCarloReport
from .exits import simulate_exits

BLOCK = 5
TAIL_SHOCK_P = 0.02


def _block_bootstrap(z: np.ndarray, n: int, h: int, rng) -> np.ndarray:
    z = z - z.mean()
    nb = int(np.ceil(h / BLOCK))
    starts = rng.integers(0, max(1, len(z) - BLOCK), size=(n, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(n, -1)[:, :h]
    return z[np.clip(idx, 0, len(z) - 1)]


def run_monte_carlo(
    cand: Candidate,
    own_z: np.ndarray,
    pool_z: np.ndarray,
    uncond_z: np.ndarray,
    n_paths: int,
    horizon: int,
    shrinkage: float,
    leverage: int = 1,
    rng: np.random.Generator | None = None,
) -> MonteCarloReport:
    rng = rng or np.random.default_rng()
    h = horizon
    cond = np.concatenate([own_z, own_z, pool_z]) if len(own_z) + len(pool_z) else np.empty((0, h))
    if len(cond) == 0 or len(uncond_z) < 50:
        return MonteCarloReport()

    n_null = int(n_paths * shrinkage)
    n_cond = n_paths - n_null
    paths_z = np.empty((n_paths, h))
    paths_z[:n_cond] = cond[rng.integers(0, len(cond), n_cond)]
    paths_z[n_cond:] = _block_bootstrap(uncond_z, n_null, h, rng)

    # incertitude sur la volatilité future
    vol_jitter = np.exp(rng.normal(0.0, 0.15, size=(n_paths, 1)))
    paths = paths_z * cand.vol * vol_jitter

    # chocs de queue contre la position
    shock = rng.random(n_paths) < TAIL_SHOCK_P
    if shock.any():
        day = rng.integers(0, h, shock.sum())
        size = rng.uniform(3, 6, shock.sum()) * cand.vol
        paths[np.flatnonzero(shock), day] -= cand.direction * size

    ret, bars, kind = simulate_exits(paths, cand.direction, cand.stop_pct, cand.target_pct)
    fees = cand.cost_pct
    if cand.direction < 0 or leverage > 1:
        fees = fees + OVERNIGHT_FEE_PER_DAY * bars
    net = ret - fees
    r = net / cand.stop_pct

    var = net.var()
    tail = np.sort(r)[: max(1, int(0.05 * len(r)))]
    batches = np.array_split(rng.permutation(r), 20)
    return MonteCarloReport(
        paths=int(n_paths),
        p_win=float((net > 0).mean()),
        p_stop=float((kind == 1).mean()),
        p_target=float((kind == 2).mean()),
        p_big_loss=float((r < -1.5).mean()),
        expected_return=float(net.mean()),
        expected_r=float(r.mean()),
        cvar5_r=float(tail.mean()),
        median_bars=float(np.median(bars)),
        kelly=float(net.mean() / var) if var > 0 else 0.0,
        batch_agreement=float(np.mean([b.mean() > 0 for b in batches])),
    )
