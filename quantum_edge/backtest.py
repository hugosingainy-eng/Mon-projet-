"""Backtest PORTEFEUILLE strictement hors échantillon.

1. La compétition est lancée sur les données AVANT le début de la période de test
   (train + validation). Seules les familles qui passent tous les critères sont retenues.
2. Le portefeuille de 100 $ est simulé jour par jour sur la période de test (jamais vue),
   avec les vraies règles du risk manager : 0,50 $ de risque par trade, coûts inclus,
   3 positions max, corrélation <= 0,7, limites jour / semaine / drawdown -> coupe-circuit
   (sans reprise automatique : il faudrait une autorisation humaine).

Limites honnêtes : l'analyse technique intraday, la macro et le sentiment ne peuvent
pas être rejoués sur le passé avec des données gratuites ; ce backtest valide la
couche statistique + risque + exécution, pas les agents d'actualité.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd

from .config import SLIPPAGE_PER_SIDE, Settings
from .marketdata.sources import make_source
from .quantitative.competition import run_competition
from .quantitative.validation import split_dates
from .risk.manager import evaluate_trade, limit_breaches
from .risk.portfolio import max_correlation
from .strategies.base import StrategySpec
from .strategies.catalog import compute_signals


def run_portfolio_backtest(s: Settings, data: dict | None = None, log=print) -> dict:
    t0 = time.time()
    src = make_source(s.data_source, s)
    data = data or src.load_daily(list(s.universe), s.research.history_years)
    dates = pd.DatetimeIndex(sorted(set().union(*[df.index for df in data.values()])))
    _, _, d_test, d_end = split_dates(dates, s.research.train_frac, s.research.valid_frac)
    past = {k: v.loc[:d_test - pd.Timedelta(days=1)] for k, v in data.items()}
    log(f"[backtest] sélection des stratégies sur les données < {d_test.date()} (le test n'est jamais vu)")
    comp = run_competition(past, s, workers=max(1, (os.cpu_count() or 2) - 1), log=log, simulated=src.simulated)
    chosen = [r for r in comp["leaderboard"] if "chosen_spec" in r and not r["failed"]]
    specs = [(StrategySpec(r["family"], tuple(sorted(r["chosen_spec"]["params"].items()))), r) for r in chosen]
    log(f"[backtest] stratégies retenues : {[r['family'] for r in chosen] or 'aucune'}")

    lim = s.risk
    ctx = {"bench": data.get(s.benchmark)}
    sigs = {(sp.id, sym): compute_signals(sp, df, ctx) for sp, _ in specs for sym, df in data.items()}
    test_days = dates[dates >= d_test]
    cash = lim.starting_capital
    acc = {"starting_capital": cash, "cash": cash, "peak_equity": cash, "day_start_equity": cash,
           "week_start_equity": cash}
    positions, closed, curve = [], [], []
    tripped_at, week = None, None
    rejected = {"risk": 0, "regime": 0}
    for t in test_days:
        bar = {sym: df.loc[t] for sym, df in data.items() if t in df.index}
        # sorties : stop / objectif / temps
        for p in list(positions):
            b = bar.get(p["symbol"])
            if b is None:
                continue
            p["bars"] += 1
            exit_px, reason = None, None
            if b["low"] <= p["stop"]:
                exit_px, reason = min(b["open"], p["stop"]), "stop"
            elif b["high"] >= p["target"]:
                exit_px, reason = max(b["open"], p["target"]), "target"
            elif p["bars"] >= s.sim.horizon_bars:
                exit_px, reason = b["close"], "time"
            if exit_px is not None:
                proceeds = p["units"] * exit_px * (1 - SLIPPAGE_PER_SIDE)
                fee = proceeds * p["cost"] / 2
                pnl = proceeds - fee - p["amount"] - p["entry_fee"]
                cash += proceeds - fee
                positions.remove(p)
                closed.append({**p, "exit_date": t, "exit": exit_px, "reason": reason, "pnl": pnl,
                               "r": pnl / p["risk_usd"]})
        prices = {sym: float(b["close"]) for sym, b in bar.items()}
        eq = cash + sum(p["units"] * prices.get(p["symbol"], p["entry"]) for p in positions)
        wk = t.isocalendar()[1]
        if week != wk:
            week, acc["week_start_equity"] = wk, eq
        acc["day_start_equity"] = curve[-1][1] if curve else eq
        acc["peak_equity"] = max(acc["peak_equity"], eq)
        acc["cash"] = cash
        if tripped_at is None and limit_breaches(acc, eq, lim):
            tripped_at = t
            log(f"[backtest] COUPE-CIRCUIT le {t.date()} : {limit_breaches(acc, eq, lim)}")
        # entrées
        for sp, rep in specs:
            for sym in data:
                sig = sigs[(sp.id, sym)]
                if t not in sig.index or not bool(sig.at[t, "entry"]):
                    continue
                price = prices.get(sym)
                if price is None:
                    continue
                stop_pct = float(sig.at[t, "stop_dist"]) / price
                tgt_pct = float(sig.at[t, "target_dist"]) / price
                cost = s.cost_for(sym)
                hist = {k: v.loc[:t] for k, v in data.items()}
                corr, _ = max_correlation(hist, sym, [p["symbol"] for p in positions])
                open_risk = sum(max(0.0, p["units"] * (prices.get(p["symbol"], p["entry"]) - p["stop"]))
                                for p in positions)
                v = evaluate_trade(symbol=sym, direction=1, leverage=1, price=price, stop_pct=stop_pct,
                                   target_pct=tgt_pct, cost_pct=cost, acc=acc, equity=eq, cash=cash,
                                   open_positions=positions, open_risk_usd=open_risk, max_corr=corr,
                                   entries_allowed=(tripped_at is None, "coupe-circuit"), lim=lim)
                if not v.approved:
                    rejected["risk"] += 1
                    continue
                fill = price * (1 + SLIPPAGE_PER_SIDE)
                entry_fee = v.amount * cost / 2
                cash -= v.amount + entry_fee
                acc["cash"] = cash
                positions.append({"symbol": sym, "strategy": sp.family, "entry": fill, "units": v.amount / fill,
                                  "amount": v.amount, "stop": fill * (1 - stop_pct), "target": fill * (1 + tgt_pct),
                                  "cost": cost, "entry_fee": entry_fee, "risk_usd": v.risk_usd, "bars": 0,
                                  "entry_date": t})
        eq = cash + sum(p["units"] * prices.get(p["symbol"], p["entry"]) for p in positions)
        curve.append((t, eq))
    for p in positions:   # clôture finale à la dernière clôture
        px = float(data[p["symbol"]]["close"].iloc[-1])
        proceeds = p["units"] * px
        pnl = proceeds * (1 - p["cost"] / 2) - p["amount"] - p["entry_fee"]
        cash += proceeds * (1 - p["cost"] / 2)
        closed.append({**p, "exit_date": d_end, "exit": px, "reason": "fin", "pnl": pnl, "r": pnl / p["risk_usd"]})
    eqs = pd.Series([e for _, e in curve], index=[d for d, _ in curve])
    pnl = np.array([c["pnl"] for c in closed])
    rets = eqs.pct_change().dropna()
    bench = data.get(s.benchmark)
    bh = float(bench["close"].loc[d_test:].iloc[-1] / bench["close"].loc[d_test:].iloc[0] - 1) if bench is not None else None
    return {
        "simulated_data": src.simulated, "period": f"{d_test.date()} -> {d_end.date()}",
        "strategies": [r["family"] for r in chosen], "start": lim.starting_capital, "final": round(cash, 2),
        "return": cash / lim.starting_capital - 1, "max_dd": float((1 - eqs / eqs.cummax()).max()) if len(eqs) else 0,
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0,
        "trades": len(closed), "win_rate": float((pnl > 0).mean()) if len(pnl) else 0.0,
        "profit_factor": float(pnl[pnl > 0].sum() / -pnl[pnl < 0].sum()) if (pnl < 0).any() else float("inf"),
        "avg_r": float(np.mean([c["r"] for c in closed])) if closed else 0.0,
        "breaker_tripped": str(tripped_at.date()) if tripped_at is not None else None,
        "rejected_by_risk": rejected["risk"], "buy_and_hold_benchmark": bh, "seconds": round(time.time() - t0, 1),
        "equity_curve": eqs,
    }


def print_report(r: dict):
    pct = lambda x: f"{x:+.2%}" if x is not None else "n/a"
    tag = "  ⚠️ DONNÉES SIMULÉES — SANS VALEUR" if r["simulated_data"] else ""
    print(f"\n========== BACKTEST PORTEFEUILLE HORS ÉCHANTILLON{tag} ==========")
    print(f"Période de test (jamais vue) : {r['period']}")
    print(f"Stratégies retenues          : {r['strategies'] or 'aucune -> aucun trade'}")
    print(f"Capital                      : {r['start']:.2f} $ -> {r['final']:.2f} $ ({pct(r['return'])})")
    print(f"Drawdown max                 : {r['max_dd']:.2%} | Sharpe {r['sharpe']:.2f}")
    print(f"Trades                       : {r['trades']} | gagnants {r['win_rate']:.0%} | PF {r['profit_factor']:.2f} "
          f"| moyenne {r['avg_r']:+.2f}R")
    print(f"Refusés par le risk manager  : {r['rejected_by_risk']}")
    print(f"Coupe-circuit                : {r['breaker_tripped'] or 'jamais déclenché'}")
    print(f"Référence buy & hold SPY     : {pct(r['buy_and_hold_benchmark'])}")
    print("=" * 66)
