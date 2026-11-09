"""Backtest "walk-forward" du bot complet, jour par jour, sans regarder le futur.

À chaque date, les agents ne voient que les données disponibles à cette date
(les occurrences historiques d'un setup ne sont utilisées qu'une fois leur
issue connue). On simule exactement le même pipeline que le bot en direct.
"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd

from .agents.committee import Committee, find_candidates
from .agents.history import SetupLibrary
from .bot import execute_decisions
from .broker import Ledger, PaperBroker
from .config import BotConfig
from .strategies import get_strategies

WARMUP = 300


def run_backtest(cfg: BotConfig, data: dict, verbose: bool = False) -> dict:
    t0 = time.time()
    costs = {s: cfg.cost_for(s) for s in data}
    lib = SetupLibrary(data, get_strategies(cfg.risk.allow_short), cfg.sim.horizon_bars, costs)
    dates = sorted(set().union(*[df.index for df in data.values()]))
    dates = dates[WARMUP:]
    closes = pd.DataFrame({s: df["close"] for s, df in data.items()}).sort_index()
    ffilled = closes.ffill()

    broker = PaperBroker(Ledger(cfg.risk.starting_capital))
    led = broker.ledger
    curve = []
    n_reviewed = n_approved = 0
    log = print if verbose else (lambda *_: None)

    with Committee(lib, cfg) as com:
        for t in dates:
            today = closes.loc[t].dropna().to_dict()
            prices = ffilled.loc[t].dropna().to_dict()
            when = str(pd.Timestamp(t).date())
            # 1) gestion des positions (stop / objectif / temps)
            broker.check_exits(today, when)
            for p in list(led.positions):
                if p["symbol"] in today:
                    p["bars_held"] += 1
                    if p["bars_held"] >= cfg.sim.horizon_bars:
                        broker.close(p, today[p["symbol"]], "temps écoulé", when)
            led.mark(prices, pd.Timestamp(t).to_pydatetime())
            # 2) nouveaux trades
            open_syms = {p["symbol"] for p in led.positions}
            cands = [c for c in find_candidates(lib, cfg, t) if c.symbol not in open_syms]
            if cands:
                decisions = com.review(cands)
                n_reviewed += len(decisions)
                n_approved += sum(d.approved for d in decisions)
                execute_decisions(decisions, broker, prices, cfg, when=when, log=log)
            curve.append((t, led.equity(prices)))
        total_paths = com.total_paths

    # clôture de fin de test
    last = ffilled.iloc[-1].dropna().to_dict()
    for p in list(led.positions):
        broker.close(p, last[p["symbol"]], "fin du backtest", str(dates[-1]))

    eq = pd.Series([v for _, v in curve], index=[d for d, _ in curve])
    return summarize(cfg, led, eq, closes, dates, n_reviewed, n_approved, total_paths, time.time() - t0)


def summarize(cfg, led, eq, closes, dates, n_reviewed, n_approved, total_paths, secs) -> dict:
    closed = led.d["closed"]
    pnl = np.array([c["pnl"] for c in closed]) if closed else np.zeros(0)
    rets = eq.pct_change().dropna()
    dd = (eq / eq.cummax() - 1).min() if len(eq) else 0.0
    by_strat = defaultdict(list)
    for c in closed:
        by_strat[c["strategy"]].append(c["pnl"])
    bench = None
    if cfg.benchmark in closes:
        b = closes[cfg.benchmark].loc[dates[0]:dates[-1]].dropna()
        bench = float(b.iloc[-1] / b.iloc[0] - 1) if len(b) > 1 else None
    final = led.cash
    years = max(1e-9, (pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days / 365.25)
    return {
        "start": str(pd.Timestamp(dates[0]).date()), "end": str(pd.Timestamp(dates[-1]).date()),
        "starting_capital": cfg.risk.starting_capital,
        "final_equity": round(final, 2),
        "total_return": final / cfg.risk.starting_capital - 1,
        "cagr": (final / cfg.risk.starting_capital) ** (1 / years) - 1,
        "max_drawdown": float(dd),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0,
        "trades": len(closed),
        "win_rate": float((pnl > 0).mean()) if len(pnl) else 0.0,
        "profit_factor": float(pnl[pnl > 0].sum() / -pnl[pnl < 0].sum()) if (pnl < 0).any() else float("inf"),
        "avg_r": float(np.mean([c["r"] for c in closed])) if closed else 0.0,
        "candidates_reviewed": n_reviewed,
        "candidates_approved": n_approved,
        "monte_carlo_paths": total_paths,
        "by_strategy": {k: {"trades": len(v), "pnl": round(sum(v), 2)} for k, v in by_strat.items()},
        "benchmark_return": bench,
        "seconds": round(secs, 1),
        "equity_curve": eq,
        "closed_trades": closed,
    }


def print_report(r: dict):
    pct = lambda x: f"{x:+.1%}" if x is not None else "n/a"
    print("\n================ RÉSULTAT DU BACKTEST ================")
    print(f"Période              : {r['start']} -> {r['end']}")
    print(f"Capital              : {r['starting_capital']:.2f}$ -> {r['final_equity']:.2f}$ ({pct(r['total_return'])})")
    print(f"Rendement annualisé  : {pct(r['cagr'])}")
    print(f"Drawdown maximal     : {r['max_drawdown']:.1%}")
    print(f"Sharpe               : {r['sharpe']:.2f}")
    print(f"Trades               : {r['trades']} | gagnants {r['win_rate']:.0%} | PF {r['profit_factor']:.2f} | moyenne {r['avg_r']:+.2f}R")
    print(f"Setups examinés      : {r['candidates_reviewed']} | validés par le comité : {r['candidates_approved']}")
    print(f"Simulations MC       : {r['monte_carlo_paths']:,} trajectoires")
    print(f"Référence (buy&hold) : {pct(r['benchmark_return'])}")
    for k, v in sorted(r["by_strategy"].items()):
        print(f"   {k:24s} {v['trades']:4d} trades  {v['pnl']:+8.2f}$")
    print(f"(calculé en {r['seconds']}s)")
    print("======================================================")
