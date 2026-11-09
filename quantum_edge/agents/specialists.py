"""Agents 6 à 10 : testeur de stratégies, Monte-Carlo, risk manager, exécution, auditeur."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from ..quantitative.setup_history import unconditional_z
from ..risk.manager import evaluate_trade
from ..simulations.trade_paths import run_trade_paths
from .base import OPPOSE, SUPPORT, VETO, Agent


class StrategyTesterAgent(Agent):
    """Agent 6 : le travail lourd (backtests, walk-forward, biais...) est fait par le moteur
    de compétition (`research`). Au moment du trade, il vérifie que la validation est récente."""
    name = "6_strategy_tester"
    role = "Testeur de stratégies"

    def analyze(self, symbol: str, entry: dict, max_age_days: int = 120):
        at = entry.get("validated_at")
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(at)).days if at else 9999
        details = {"validated_at": at, "age_days": age, "run_id": entry.get("run_id"),
                   "allowed_regimes": entry.get("allowed_regimes")}
        if age > max_age_days:
            return self.report(symbol, OPPOSE, f"validation vieille de {age} jours : relancer la recherche", 0.7,
                               at, **details)
        return self.report(symbol, SUPPORT, f"stratégie validée il y a {age} jours (walk-forward, test, stress)",
                           0.6, at, **details)


class MonteCarloAgent(Agent):
    """Agent 7 : simule le trade candidat (10 000 à 100 000 trajectoires) et rappelle les
    résultats Monte-Carlo de séquence de la stratégie."""
    name = "7_monte_carlo"
    role = "Moteur de simulation Monte-Carlo"

    def analyze(self, symbol, df, stop_pct, target_pct, vol, cost_pct, cond_z, n_paths, horizon, shrinkage,
                min_expected_r, max_p_big_loss, sequence_mc: dict | None, seed=None):
        rep = run_trade_paths(stop_pct, target_pct, vol, cost_pct, cond_z, unconditional_z(df), n_paths, horizon,
                              shrinkage, seed)
        details = {"trade": rep.to_dict(), "strategy_sequences": sequence_mc or {},
                   "note": "les simulations ré-échantillonnent l'historique : ce n'est pas une preuve indépendante"}
        if rep.paths == 0:
            return self.report(symbol, OPPOSE, "historique conditionnel insuffisant pour simuler", None,
                               df.index[-1], **details)
        problems = []
        if rep.expected_r < min_expected_r:
            problems.append(f"espérance {rep.expected_r:+.2f}R < {min_expected_r}R")
        if rep.p_big_loss > max_p_big_loss:
            problems.append(f"P(perte > 1,5R) = {rep.p_big_loss:.0%}")
        if rep.batch_agreement < 0.9:
            problems.append(f"sous-échantillons pas unanimes ({rep.batch_agreement:.0%})")
        msg = (f"{rep.paths:,} trajectoires : E={rep.expected_r:+.2f}R, P(gain)={rep.p_win:.0%}, "
               f"5e centile {rep.r_p05:+.2f}R")
        if problems:
            return self.report(symbol, OPPOSE, msg + " | " + "; ".join(problems), 0.6, df.index[-1], **details)
        return self.report(symbol, SUPPORT, msg, round(min(0.9, 0.5 + rep.expected_r), 2), df.index[-1], **details)


class RiskManagerAgent(Agent):
    """Agent 8 : veto absolu."""
    name = "8_risk_manager"
    role = "Risk manager (veto absolu)"

    def analyze(self, symbol, **kw):
        v = evaluate_trade(symbol=symbol, **kw)
        if v.approved:
            return self.report(symbol, SUPPORT, f"autorisé : {v.amount:.2f} $ pour un risque de {v.risk_usd:.2f} $",
                               None, "", verdict=v.to_dict()), v
        return self.report(symbol, VETO, "REFUS : " + "; ".join(v.reasons), None, "", verdict=v.to_dict()), v


class ExecutionAgentChecks(Agent):
    """Agent 9 (contrôles pré-trade) : instrument, marché ouvert, ordres en attente, horloge.
    L'envoi et la surveillance des ordres sont dans execution/executor.py."""
    name = "9_execution"
    role = "Agent d'exécution"

    def analyze(self, symbol, instrument_ok: tuple, market_open: bool, can_submit: tuple, clock: dict,
                require_open: bool):
        details = {"instrument": instrument_ok[1], "market_open": market_open, "pending": can_submit[1],
                   "clock": clock}
        if not instrument_ok[0]:
            return self.report(symbol, VETO, f"instrument non vérifié : {instrument_ok[1]}", None, "", **details)
        if require_open and not market_open:
            return self.report(symbol, VETO, "marché fermé", None, "", **details)
        if not can_submit[0]:
            return self.report(symbol, VETO, can_submit[1], None, "", **details)
        if clock.get("blocking"):
            return self.report(symbol, VETO, f"horloge désynchronisée ({clock.get('offset_s')} s)", None, "",
                               **details)
        return self.report(symbol, SUPPORT, "prêt à exécuter", None, "", **details)


class PerformanceAuditorAgent(Agent):
    """Agent 10 : analyse les trades clos et propose des améliorations (sans jamais
    modifier les paramètres validés en production)."""
    name = "10_auditor"
    role = "Auditeur de performance"

    def analyze_history(self, closed: list[dict], decisions: list[dict]) -> dict:
        if not closed:
            return {"n": 0, "findings": ["aucun trade clos : pas de conclusion possible"], "proposals": []}
        r = np.array([c["r"] or 0.0 for c in closed])
        by = defaultdict(list)
        for c in closed:
            by[("strategy", c["strategy"])].append(c["r"] or 0.0)
            by[("regime", c["regime"] or "?")].append(c["r"] or 0.0)
            by[("exit", (c["reason"] or "?").split(" ")[0])].append(c["r"] or 0.0)
        findings, proposals = [], []
        for (kind, k), v in sorted(by.items()):
            if len(v) >= 5 and np.mean(v) < -0.2:
                findings.append(f"{kind} « {k} » : {len(v)} trades, moyenne {np.mean(v):+.2f}R")
                proposals.append(f"Relancer la recherche en isolant {kind}={k} (aucun changement automatique).")
        time_exits = [c for c in closed if (c["reason"] or "").startswith("sortie temporelle")]
        if len(time_exits) / len(closed) > 0.5 and len(closed) >= 10:
            findings.append("plus de la moitié des trades sortent au temps : objectifs peut-être trop lointains")
        rejected = [d for d in decisions if not d.get("authorized")]
        if len(closed) < 30:
            findings.append(f"seulement {len(closed)} trades : aucune conclusion statistique fiable (il en faut 30+)")
        return {"n": len(closed), "ev_r": float(r.mean()), "win_rate": float((r > 0).mean()),
                "rejected_opportunities": len(rejected), "findings": findings, "proposals": proposals}

