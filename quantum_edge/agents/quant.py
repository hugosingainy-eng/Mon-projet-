"""Agent 3 — Chercheur quantitatif : la stratégie a-t-elle un avantage statistique
prouvé hors échantillon, et ce setup précis a-t-il un historique suffisant ?"""
from __future__ import annotations

from .base import OPPOSE, SUPPORT, Agent


class QuantAgent(Agent):
    name = "3_quant"
    role = "Chercheur quantitatif"

    def analyze(self, symbol: str, entry: dict, n_own: int, n_pool: int, data_time):
        m = entry.get("wf_metrics", {})
        details = {"strategy": entry["spec"]["label"], "walk_forward": m, "validated_at": entry.get("validated_at"),
                   "setup_history_own": n_own, "setup_history_universe": n_pool}
        if m.get("n", 0) < 30 or m.get("ci_low", -1) <= 0:
            return self.report(symbol, OPPOSE, "preuve statistique insuffisante hors échantillon", 0.8, data_time,
                               **details)
        if n_own + n_pool < 20:
            return self.report(symbol, OPPOSE, f"setup trop rare ({n_own + n_pool} occurrences)", 0.6, data_time,
                               **details)
        conf = min(0.9, 0.4 + 0.1 * m.get("tstat", 0))
        return self.report(symbol, SUPPORT,
                           f"avantage hors échantillon : E={m['ev_r']:+.2f}R, PF={m['profit_factor']:.2f}, "
                           f"n={m['n']}, IC90 [{m['ci_low']:+.2f}; {m['ci_high']:+.2f}]R", round(conf, 2), data_time,
                           **details)
