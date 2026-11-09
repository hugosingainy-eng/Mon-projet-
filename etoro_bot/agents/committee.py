"""Le comité d'investissement : orchestre tous les sous-agents.

Pour chaque trade candidat :
  1. Agents stratégies   -> détectent les setups (Turtle, Minervini, Connors, ...)
  2. Agent historien     -> le setup a-t-il un edge prouvé dans le passé ?
  3. Agent régime        -> le contexte de marché est-il favorable ?
  4. Agent Monte-Carlo   -> 50 000 simulations du trade : espérance, risque de queue
  5. Comité              -> vote ; un seul "non" bloquant suffit à rejeter
  6. Risk manager        -> taille de position (fait par le bot, avec l'état du portefeuille)

Les candidats sont évalués en parallèle dans des processus séparés (sous-agents).
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from ..config import BotConfig
from .base import Candidate, Decision
from .history import SetupLibrary, history_report
from .monte_carlo import run_monte_carlo
from .regime import regime_report


def find_candidates(lib: SetupLibrary, cfg: BotConfig, asof=None) -> list[Candidate]:
    """asof=None : dernière barre disponible de chaque actif (mode live)."""
    out = []
    for (sym, sname), sig in lib.signals.items():
        if len(sig) == 0:
            continue
        asof_ = sig.index[-1] if asof is None else pd.Timestamp(asof)
        if asof_ not in sig.index or not bool(sig.at[asof_, "entry"]):
            continue
        df = lib.frames[sym]
        price = float(df.at[asof_, "close"])
        vol = float(df.at[asof_, "vol"])
        if not np.isfinite(vol) or vol <= 0:
            continue
        s = lib.strategies[sname]
        out.append(Candidate(
            symbol=sym, strategy=sname, inspired_by=s.inspired_by, direction=s.direction,
            price=price,
            stop_pct=float(sig.at[asof_, "stop_dist"]) / price,
            target_pct=float(sig.at[asof_, "target_dist"]) / price,
            vol=vol, cost_pct=cfg.cost_for(sym), date=str(pd.Timestamp(asof_).date()),
        ))
    return out


def evaluate(cand: Candidate, lib: SetupLibrary, cfg: BotConfig, seed=None) -> Decision:
    sim = cfg.sim
    asof = pd.Timestamp(cand.date)
    own_z, own_r, pool_z, pool_r = lib.query(cand.symbol, cand.strategy, asof)
    hist = history_report(own_r, pool_r)

    df = lib.frames[cand.symbol].loc[:asof]
    bench = lib.frames.get(cfg.benchmark)
    bench = bench.loc[:asof] if bench is not None else None
    reg = regime_report(df, bench, cand.direction, cand.strategy)

    rng = np.random.default_rng(seed)
    mc = run_monte_carlo(
        cand, own_z, pool_z, lib.unconditional(cand.symbol, asof),
        n_paths=sim.mc_paths, horizon=sim.horizon_bars, shrinkage=sim.shrinkage,
        leverage=cfg.risk.leverage, rng=rng,
    )

    dec = Decision(candidate=cand, history=hist, mc=mc, regime=reg)
    r = dec.reasons
    if hist.n_own + hist.n_pool < sim.min_hist_trades:
        r.append(f"historique insuffisant ({hist.n_own + hist.n_pool} occurrences)")
    if hist.profit_factor < sim.min_profit_factor:
        r.append(f"profit factor historique {hist.profit_factor:.2f} < {sim.min_profit_factor}")
    if hist.tstat < sim.min_tstat:
        r.append(f"edge historique pas significatif (t={hist.tstat:.2f})")
    if not reg.allowed:
        r.append(reg.reason)
    if mc.expected_r < sim.min_expected_r:
        r.append(f"espérance Monte-Carlo {mc.expected_r:+.2f}R < {sim.min_expected_r}R")
    if mc.p_win < sim.min_p_win:
        r.append(f"proba de gain {mc.p_win:.0%} trop faible")
    if mc.p_big_loss > sim.max_p_big_loss:
        r.append(f"risque de grosse perte {mc.p_big_loss:.0%} trop élevé")
    if mc.batch_agreement < 0.9:
        r.append(f"simulations pas assez unanimes ({mc.batch_agreement:.0%})")

    dec.approved = not r
    dec.conviction = float(
        0.5 * np.clip(mc.expected_r / 0.5, 0, 1) + 0.5 * np.clip(hist.tstat / 3.0, 0, 1)
    )
    return dec


# ------------------------------------------------------------------ parallélisme
_LIB = None
_CFG = None


def _init_worker(lib, cfg):
    global _LIB, _CFG
    _LIB, _CFG = lib, cfg


def _eval_task(args):
    cand, seed = args
    return evaluate(cand, _LIB, _CFG, seed)


class Committee:
    def __init__(self, lib: SetupLibrary, cfg: BotConfig):
        self.lib, self.cfg = lib, cfg
        self._pool = None
        self.total_paths = 0

    def __enter__(self):
        if self.cfg.sim.workers > 1:
            self._pool = ProcessPoolExecutor(
                max_workers=self.cfg.sim.workers, initializer=_init_worker, initargs=(self.lib, self.cfg)
            )
        return self

    def __exit__(self, *exc):
        if self._pool:
            self._pool.shutdown()

    def review(self, candidates: list[Candidate]) -> list[Decision]:
        base = self.cfg.sim.seed
        tasks = [(c, None if base is None else base + i) for i, c in enumerate(candidates)]
        if self._pool and len(tasks) > 1:
            decisions = list(self._pool.map(_eval_task, tasks))
        else:
            decisions = [evaluate(c, self.lib, self.cfg, s) for c, s in tasks]
        self.total_paths += sum(d.mc.paths for d in decisions)
        # meilleures idées d'abord
        decisions.sort(key=lambda d: (d.approved, d.conviction, d.mc.expected_r), reverse=True)
        return decisions
