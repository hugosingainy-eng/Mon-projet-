"""Monte-Carlo au niveau STRATÉGIE : rejoue des séquences de trades.

On ré-échantillonne les trades hors échantillon réellement observés, puis on les
dégrade (stress) : moins de gains, gains plus petits, spread plus large,
slippage, retards d'exécution, gaps brutaux. On en tire la distribution des
rendements, des drawdowns et le risque de toucher le coupe-circuit (-5 %).

⚠️ Les simulations ré-utilisent les MÊMES trades historiques : elles ne créent pas
de nouvelle preuve. La taille d'échantillon réelle reste `n_real_trades`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SCENARIOS = {
    "base":               dict(win_cut=0.00, reward_mult=1.00, extra_cost_r=0.00, gap_p=0.00),
    "moins_de_gains":     dict(win_cut=0.15, reward_mult=1.00, extra_cost_r=0.00, gap_p=0.00),
    "gains_reduits":      dict(win_cut=0.00, reward_mult=0.80, extra_cost_r=0.00, gap_p=0.00),
    "spread_x2_slippage": dict(win_cut=0.00, reward_mult=1.00, extra_cost_r=0.08, gap_p=0.00),
    "retard_execution":   dict(win_cut=0.05, reward_mult=0.90, extra_cost_r=0.04, gap_p=0.00),
    "chocs_brutaux":      dict(win_cut=0.00, reward_mult=1.00, extra_cost_r=0.00, gap_p=0.03),
    "pire_cas_combine":   dict(win_cut=0.15, reward_mult=0.80, extra_cost_r=0.08, gap_p=0.03),
}


@dataclass
class SequenceReport:
    scenario: str
    n_real_trades: int
    sims: int
    horizon_trades: int
    final_return_p05: float
    final_return_p50: float
    final_return_p95: float
    p_loss: float
    max_dd_p50: float
    max_dd_p95: float
    risk_of_ruin: float        # P(drawdown >= seuil du coupe-circuit)
    worst_case_p01: float
    longest_losing_streak_p95: float


def simulate_sequences(r: np.ndarray, sims: int = 20_000, horizon: int = 100, risk_per_trade: float = 0.005,
                       ruin_dd: float = 0.05, scenario: str = "base", seed: int = 0,
                       chunk: int = 5_000) -> SequenceReport:
    r = np.asarray(r, float)
    if len(r) == 0:
        return SequenceReport(scenario, 0, 0, horizon, *([0.0] * 9))
    sc = SCENARIOS[scenario]
    rng = np.random.default_rng(seed)
    finals, dds, streaks = [], [], []
    for start in range(0, sims, chunk):
        m = min(chunk, sims - start)
        x = rng.choice(r, size=(m, horizon), replace=True)
        win = x > 0
        if sc["win_cut"]:
            flip = win & (rng.random(x.shape) < sc["win_cut"])
            x = np.where(flip, -1.0, x)
            win = x > 0
        x = np.where(win, x * sc["reward_mult"], x) - sc["extra_cost_r"]
        if sc["gap_p"]:
            x = np.where(rng.random(x.shape) < sc["gap_p"], -2.0, x)
        eq = np.cumprod(1 + x * risk_per_trade, axis=1)       # risque fixe en % du capital
        peak = np.maximum.accumulate(np.concatenate([np.ones((m, 1)), eq], axis=1), axis=1)[:, 1:]
        dds.append((1 - eq / peak).max(1))
        finals.append(eq[:, -1] - 1)
        lose = (x <= 0).astype(np.int8)
        run = np.zeros(m, int)
        best = np.zeros(m, int)
        for t in range(horizon):
            run = (run + 1) * lose[:, t]
            best = np.maximum(best, run)
        streaks.append(best)
    f, d, s = np.concatenate(finals), np.concatenate(dds), np.concatenate(streaks)
    return SequenceReport(
        scenario=scenario, n_real_trades=len(r), sims=sims, horizon_trades=horizon,
        final_return_p05=float(np.percentile(f, 5)), final_return_p50=float(np.median(f)),
        final_return_p95=float(np.percentile(f, 95)), p_loss=float((f < 0).mean()),
        max_dd_p50=float(np.median(d)), max_dd_p95=float(np.percentile(d, 95)),
        risk_of_ruin=float((d >= ruin_dd).mean()), worst_case_p01=float(np.percentile(f, 1)),
        longest_losing_streak_p95=float(np.percentile(s, 95)),
    )


def stress_suite(r, sims=20_000, horizon=100, risk_per_trade=0.005, ruin_dd=0.05, seed=0) -> dict:
    return {name: simulate_sequences(r, sims, horizon, risk_per_trade, ruin_dd, name, seed + i).__dict__
            for i, name in enumerate(SCENARIOS)}
