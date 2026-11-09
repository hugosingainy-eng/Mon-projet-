"""Moteur de compétition des stratégies (Partie 4).

Toutes les familles sont testées sur les MÊMES données, coûts et périodes :
  train (60 %) -> choix des paramètres
  validation (20 %) -> contrôle
  test (20 %) -> évaluation finale, regardée une seule fois
  + walk-forward glissant (3 ans d'apprentissage / 1 an hors échantillon)
  + stress coûts x2, retard d'exécution d'une barre, stabilité des paramètres,
    contrôle du biais du futur, performance par régime, Monte-Carlo de séquences.
Une stratégie n'est ÉLIGIBLE que si elle passe TOUS les critères.
"""
from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from ..config import SLIPPAGE_PER_SIDE, Settings
from ..simulations.sequences import stress_suite
from ..strategies.catalog import FAMILIES, compute_signals
from .metrics import clean, trade_metrics
from .trades import TradeCosts, simulate_trades
from .validation import (SURVIVORSHIP_WARNING, in_window, lookahead_check, market_regimes,
                         regime_breakdown, split_dates, walk_forward_windows)

MIN_SELECT_TRADES = 20


def _sim_symbol(args):
    sym, df, specs, ctx, cost, max_hold, regimes, mode = args
    costs = {"base": TradeCosts(cost, SLIPPAGE_PER_SIDE),
             "stress": TradeCosts(cost * 2, SLIPPAGE_PER_SIDE * 3)}[mode if mode != "delay" else "base"]
    delay = 1 if mode == "delay" else 0
    reg = regimes.reindex(df.index).ffill() if regimes is not None else None
    out = []
    for spec in specs:
        sig = compute_signals(spec, df, ctx)
        t = simulate_trades(df, sig, costs, max_hold, delay, sym, spec.id, reg)
        if len(t):
            out.append(t)
    return pd.concat(out) if out else pd.DataFrame()


def run_trades(data, specs, settings: Settings, mode="base", workers=None) -> pd.DataFrame:
    bench = data.get(settings.benchmark)
    ctx = {"bench": bench}
    regimes = market_regimes(bench) if bench is not None else None
    tasks = [(s, df, specs, ctx, settings.cost_for(s), settings.sim.horizon_bars, regimes, mode)
             for s, df in data.items()]
    workers = workers or 1
    if workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(workers) as ex:
            parts = list(ex.map(_sim_symbol, tasks))
    else:
        parts = [_sim_symbol(t) for t in tasks]
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["symbol", "strategy", "entry_date", "exit_date", "r", "regime"])


def _best(trades: pd.DataFrame, specs, start, end):
    best, best_score = None, -np.inf
    for s in specs:
        t = in_window(trades[trades["strategy"] == s.id], start, end)
        if len(t) < MIN_SELECT_TRADES:
            continue
        m = trade_metrics(t)
        if m["tstat"] > best_score:
            best, best_score = s, m["tstat"]
    return best


def composite_score(m_oos: dict, consistency: float, cost_ev: float, delay_ev: float) -> float:
    """Score de classement documenté (pas seulement le rendement)."""
    pf = min(m_oos["profit_factor"], 3.0)
    unc = max(0.0, m_oos["ev_r"] - m_oos["ci_low"])                       # incertitude statistique
    return float(
        0.25 * np.clip(m_oos["sharpe"], -2, 3) + 0.15 * np.clip(m_oos["sortino"], -2, 4)
        + 0.15 * (pf - 1) + 0.15 * np.clip(m_oos["ev_r"] * 4, -2, 2)
        - 0.10 * m_oos["max_dd_r"] / 10 + 0.10 * consistency
        + 0.10 * np.clip(min(cost_ev, delay_ev) * 4, -2, 2) - 0.10 * unc * 4
        + 0.05 * np.log1p(m_oos["n"]) / 5
    )


def run_competition(data: dict, settings: Settings, workers: int = 1, log=print, simulated: bool = False) -> dict:
    t0 = time.time()
    rc, risk = settings.research, settings.risk
    dates = pd.DatetimeIndex(sorted(set().union(*[df.index for df in data.values()])))
    d0, d_train, d_val, d_end = split_dates(dates, rc.train_frac, rc.valid_frac)
    log(f"[recherche] {len(data)} actifs, {len(dates)} jours ({d0.date()} -> {d_end.date()})")
    log(f"[recherche] train < {d_train.date()} <= validation < {d_val.date()} <= test")

    all_specs = [s for f in FAMILIES for s in f.specs()]
    raw = run_trades(data, all_specs, settings, "base", workers)
    # Seuls les trades RÉALISABLES avec 100 $ comptent : risque 0,50 $ et ordre minimum 10 $
    # => distance au stop + coûts <= 5 %. Les autres seraient refusés par le risk manager.
    max_risk_pct = risk.risk_per_trade * risk.starting_capital / risk.min_order_usd
    feasible = lambda t: t[t["risk_pct"] <= max_risk_pct] if len(t) else t
    base = feasible(raw)
    log(f"[recherche] {len(all_specs)} configurations x {len(data)} actifs -> {len(raw)} trades simulés, "
        f"{len(base)} réalisables avec {risk.starting_capital:.0f} $ (risque <= {max_risk_pct:.1%})")
    wf = walk_forward_windows(dates, rc.wf_train_bars, rc.wf_test_bars)

    results = []
    for fam in FAMILIES:
        specs = fam.specs()
        ft = base[base["strategy"].isin([s.id for s in specs])]
        # 1) sélection sur train+validation, contrôle sur test
        chosen = _best(ft, specs, d0, d_val)
        rep = {"family": fam.name, "hypothesis": fam.hypothesis, "inspired_by": fam.inspired_by,
               "configs_tested": len(specs)}
        if chosen is None:
            rep.update({"eligible": False, "status": "rejected", "failed": ["pas assez de trades pour choisir"],
                        "score": -99.0})
            results.append(rep)
            continue
        ct = ft[ft["strategy"] == chosen.id]
        m_train = trade_metrics(in_window(ct, d0, d_train))
        m_val = trade_metrics(in_window(ct, d_train, d_val))
        m_test = trade_metrics(in_window(ct, d_val, d_end + pd.Timedelta(days=1)))
        # 2) walk-forward : paramètres re-choisis à chaque pli, uniquement sur le passé
        oos_parts, fold_ev = [], []
        for a, b, c in wf:
            s = _best(ft, specs, a, b)
            if s is None:
                continue
            t = in_window(ft[ft["strategy"] == s.id], b, c)
            if len(t):
                oos_parts.append(t)
                if len(t) >= 3:
                    fold_ev.append(t["r"].mean())
        wf_trades = pd.concat(oos_parts) if oos_parts else ct.iloc[0:0]
        m_wf = trade_metrics(wf_trades, risk.risk_per_trade)
        consistency = float(np.mean([e > 0 for e in fold_ev])) if fold_ev else 0.0
        # 3) stabilité des paramètres : l'edge doit exister autour du point choisi
        in_s = [trade_metrics(in_window(ft[ft["strategy"] == s.id], d0, d_val)) for s in specs]
        stability = float(np.mean([m["ev_r"] > 0 for m in in_s if m["n"] >= 10])) if in_s else 0.0
        # 4) sensibilité aux coûts et au retard d'exécution (hors échantillon)
        stress = feasible(run_trades(data, [chosen], settings, "stress", workers))
        delay = feasible(run_trades(data, [chosen], settings, "delay", workers))
        raw_c = raw[raw["strategy"] == chosen.id]
        feas_frac = len(ct) / len(raw_c) if len(raw_c) else 0.0
        ev_cost = trade_metrics(in_window(stress, d_train, d_end + pd.Timedelta(days=1)))["ev_r"]
        ev_delay = trade_metrics(in_window(delay, d_train, d_end + pd.Timedelta(days=1)))["ev_r"]
        # 5) biais du futur
        la_ok, la_msg = lookahead_check(chosen, data, {"bench": data.get(settings.benchmark)})
        # 6) Monte-Carlo de séquences sur les trades hors échantillon
        mc = stress_suite(wf_trades["r"].to_numpy(), rc.mc_sequences, 100, risk.risk_per_trade,
                          risk.max_drawdown, rc.seed) if len(wf_trades) else {}
        ror = mc.get("base", {}).get("risk_of_ruin", 1.0)

        checks = {
            f"≥{rc.min_trades_oos} trades walk-forward": m_wf["n"] >= rc.min_trades_oos,
            f"espérance WF > {rc.min_ev_r}R": m_wf["ev_r"] > rc.min_ev_r,
            "IC 90 % de l'espérance > 0": m_wf["ci_low"] > 0,
            f"profit factor WF ≥ {rc.min_profit_factor}": m_wf["profit_factor"] >= rc.min_profit_factor,
            "espérance test final > 0": m_test["n"] >= 10 and m_test["ev_r"] > 0,
            "rentable avec coûts x2": ev_cost > 0,
            "rentable avec 1 barre de retard": ev_delay > 0,
            f"régularité des plis ≥ {rc.min_wf_consistency:.0%}": consistency >= rc.min_wf_consistency,
            f"stabilité des paramètres ≥ {rc.min_param_stability:.0%}": stability >= rc.min_param_stability,
            "pas de biais du futur": la_ok,
            f"risque de coupe-circuit ≤ {rc.max_risk_of_ruin:.0%}": ror <= rc.max_risk_of_ruin,
        }
        failed = [k for k, ok in checks.items() if not ok]
        allowed_regimes = [k for k, v in regime_breakdown(wf_trades).items()
                           if v["n"] >= 10 and v["ev_r"] > 0 and k != "unknown"]
        rep.update({
            "chosen_spec": {"id": chosen.id, "family": chosen.family, "params": dict(chosen.params),
                            "label": chosen.label()},
            "metrics": {"train": clean(m_train), "validation": clean(m_val), "test": clean(m_test),
                        "walk_forward": clean(m_wf)},
            "feasible_fraction": feas_frac, "wf_folds": len(fold_ev), "wf_consistency": consistency, "param_stability": stability,
            "ev_cost_x2": ev_cost, "ev_delay_1bar": ev_delay, "lookahead": la_msg,
            "regimes": regime_breakdown(wf_trades), "allowed_regimes": allowed_regimes,
            "monte_carlo": mc, "checks": checks, "failed": failed,
            "eligible": not failed and not simulated,
            "status": ("validated" if not failed else "rejected") if not simulated else
                      ("validated-on-simulated-data (NON éligible)" if not failed else "rejected"),
            "score": composite_score(m_wf, consistency, ev_cost, ev_delay),
        })
        results.append(rep)
        log(f"[recherche] {fam.name:20s} WF: n={m_wf['n']:4d} E={m_wf['ev_r']:+.3f}R PF={m_wf['profit_factor']:.2f} "
            f"Sharpe={m_wf['sharpe']:+.2f} -> {'VALIDÉE' if not failed else 'rejetée (' + str(len(failed)) + ' critères)'}")

    results.sort(key=lambda r: (r.get("eligible", False), r.get("score", -99)), reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return {
        "created": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "simulated_data": simulated,
        "universe": sorted(data),
        "period": {"start": str(d0.date()), "train_end": str(d_train.date()), "valid_end": str(d_val.date()),
                   "end": str(d_end.date())},
        "walk_forward_folds": len(wf),
        "total_trades_simulated": int(len(raw)),
        "feasible_trades": int(len(base)),
        "warnings": [SURVIVORSHIP_WARNING] + (["DONNÉES SIMULÉES : résultats sans valeur"] if simulated else []),
        "leaderboard": results,
        "seconds": round(time.time() - t0, 1),
    }
