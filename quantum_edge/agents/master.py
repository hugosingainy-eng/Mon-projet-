"""MASTER AGENT — Directeur quantitatif.

Coordonne les 10 agents, applique les 12 contrôles avant chaque trade, compare les
avis contradictoires et enregistre chaque décision. Il ne peut JAMAIS passer outre
le risk manager ni un veto. Refuser de trader est un résultat normal.

Décisions possibles : BUY, HOLD (déjà en position), NO TRADE.
(SELL est réservé à une future configuration de recherche : désactivé.)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .base import OPPOSE, SUPPORT, UNAVAILABLE, VETO

# agents dont le SOUTIEN explicite est obligatoire
REQUIRED_SUPPORT = ("2_technical", "3_quant", "6_strategy_tester", "7_monte_carlo", "8_risk_manager", "9_execution")
# agents dont une OPPOSITION suffit à bloquer
BLOCKING_OPPOSE = ("1_regime", "4_macro")


@dataclass
class Candidate:
    symbol: str
    strategy_id: str
    strategy_label: str
    family: str
    inspired_by: str
    hypothesis: str
    price: float
    stop_pct: float
    target_pct: float
    vol: float
    cost_pct: float
    date: str
    direction: int = +1

    @property
    def stop_price(self):
        return self.price * (1 - self.stop_pct)

    @property
    def target_price(self):
        return self.price * (1 + self.target_pct)

    @property
    def strategy(self):          # compatibilité avec l'agent Grok
        return self.strategy_label


@dataclass
class MasterDecision:
    candidate: Candidate
    checks: dict = field(default_factory=dict)
    reports: list = field(default_factory=list)
    decision: str = "NO TRADE"
    authorized: bool = False
    amount: float = 0.0
    risk_usd: float = 0.0
    reasons: list = field(default_factory=list)
    disagreements: list = field(default_factory=list)
    confidence: float = 0.0

    def to_record(self, cost_usd: float = 0.0) -> dict:
        c = self.candidate
        return {
            "instrument": c.symbol, "direction": "BUY" if c.direction > 0 else "SELL", "strategy": c.strategy_label,
            "family": c.family, "hypothesis": c.hypothesis, "inspired_by": c.inspired_by,
            "entry_conditions": f"signal {c.family} à la clôture du {c.date}, prix {c.price:.4g}",
            "stop_loss": c.stop_price, "take_profit": c.target_price, "position_size_usd": self.amount,
            "expected_risk_usd": self.risk_usd,
            "expected_reward_usd": self.amount * c.target_pct - cost_usd if self.amount else 0.0,
            "transaction_costs_usd": cost_usd, "checks": self.checks,
            "supporting_evidence": [r.conclusion for r in self.reports if r.vote == SUPPORT],
            "agent_disagreements": self.disagreements,
            "confidence_estimate": self.confidence,
            "confidence_note": "estimation subjective de cohérence entre agents, PAS une probabilité de gain",
            "decision": self.decision, "authorized": self.authorized, "reasons": self.reasons,
            "agents": {r.agent: r.to_dict() for r in self.reports},
        }


def decide(cand: Candidate, reports: dict, data_checks: dict, risk_verdict) -> MasterDecision:
    """reports : nom d'agent -> AgentReport. data_checks : contrôles 1-2 (fraîcheur, qualité)."""
    md = MasterDecision(cand, reports=list(reports.values()))
    g = lambda n: reports.get(n)
    v = lambda n: g(n).vote if g(n) else UNAVAILABLE
    rr = cand.target_pct / cand.stop_pct if cand.stop_pct else 0.0
    md.checks = {
        "1. données à jour": data_checks.get("fresh", False),
        "2. qualité des données acceptable": data_checks.get("quality", False),
        "3. régime de marché identifié et compatible": v("1_regime") not in (OPPOSE, VETO, UNAVAILABLE),
        "4. une stratégie validée s'applique": True,
        "5. soutien statistique (hors échantillon)": v("3_quant") == SUPPORT and v("6_strategy_tester") == SUPPORT,
        "6. confirmation technique multi-unités": v("2_technical") == SUPPORT,
        "7. pas de risque macro excessif": v("4_macro") not in (OPPOSE, VETO, UNAVAILABLE),
        "8. coûts de transaction acceptables": bool(risk_verdict and risk_verdict.budget.get("cost_to_risk", 1) <= 0.25),
        "9. ratio gain/risque ≥ 2": rr >= 2.0 - 1e-9,
        "10. Monte-Carlo favorable": v("7_monte_carlo") == SUPPORT,
        "11. pas d'exposition corrélée excessive": bool(risk_verdict and risk_verdict.checks.get("corrélation ≤ 0.7", False)),
        "12. autorisation du risk manager": v("8_risk_manager") == SUPPORT,
    }
    vetoes = [f"{r.agent}: {r.conclusion}" for r in reports.values() if r.vote == VETO]
    missing = [n for n in REQUIRED_SUPPORT if v(n) != SUPPORT]
    blockers = [n for n in BLOCKING_OPPOSE if v(n) in (OPPOSE, VETO)]
    md.disagreements = [f"{r.agent} ({r.vote}) : {r.conclusion}" for r in reports.values()
                        if r.vote in (OPPOSE, VETO, UNAVAILABLE)]
    md.reasons = vetoes + [f"soutien manquant : {n} ({v(n)})" for n in missing if not any(n in x for x in vetoes)] \
        + [f"opposition : {n}" for n in blockers if not any(n in x for x in vetoes)] \
        + [f"contrôle échoué : {k}" for k, ok in md.checks.items() if not ok]
    confs = [r.confidence for r in reports.values() if r.vote == SUPPORT and r.confidence is not None]
    agree = sum(r.vote == SUPPORT for r in reports.values()) / max(1, len(reports))
    md.confidence = round(float(np.mean(confs)) * agree, 3) if confs else 0.0
    if not md.reasons and risk_verdict is not None and risk_verdict.approved:
        md.decision, md.authorized = "BUY", True
        md.amount, md.risk_usd = risk_verdict.amount, risk_verdict.risk_usd
    return md
