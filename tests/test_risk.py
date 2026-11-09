import pytest

from quantum_edge.config import RiskLimits
from quantum_edge.risk.manager import evaluate_trade, limit_breaches

ACC = {"starting_capital": 100.0, "cash": 100.0, "peak_equity": 100.0, "day_start_equity": 100.0,
       "week_start_equity": 100.0}
BASE = dict(symbol="AAPL", direction=1, leverage=1, price=100.0, stop_pct=0.03, target_pct=0.06, cost_pct=0.0015,
            acc=ACC, equity=100.0, cash=100.0, open_positions=[], open_risk_usd=0.0, max_corr=0.1,
            entries_allowed=(True, ""), lim=RiskLimits())


def test_valid_trade_risks_at_most_50_cents_including_costs():
    v = evaluate_trade(**BASE)
    assert v.approved
    assert v.risk_usd <= 0.50 + 1e-6
    assert v.amount * (0.03 + 0.0015 + 0.001) == pytest.approx(v.risk_usd, abs=0.01)
    assert v.amount >= 10


@pytest.mark.parametrize("override,reason", [
    (dict(target_pct=0.04), "gain/risque"),
    (dict(stop_pct=0.07, target_pct=0.14), "minimum eToro"),
    (dict(direction=-1), "achat uniquement"),
    (dict(leverage=2), "sans levier"),
    (dict(max_corr=0.85), "corrélation"),
    (dict(open_positions=[{"symbol": s, "amount": 10.0} for s in ("A", "B", "C")]), "positions"),
    (dict(open_positions=[{"symbol": "AAPL", "amount": 10.0}]), "déjà investi"),
    (dict(entries_allowed=(False, "COUPE-CIRCUIT")), "COUPE-CIRCUIT"),
    (dict(cost_pct=0.02), "coûts"),
])
def test_rule_violations_are_vetoed(override, reason):
    v = evaluate_trade(**{**BASE, **override})
    assert not v.approved
    assert any(reason in r for r in v.reasons), v.reasons


def test_open_risk_consumes_daily_budget():
    """Si 2 positions risquent déjà 0,95 $, une 3e ne peut pas dépasser la limite de 1 $/jour."""
    v = evaluate_trade(**{**BASE, "open_positions": [{"symbol": "X", "amount": 15}, {"symbol": "Y", "amount": 15}],
                          "open_risk_usd": 0.95})
    assert not v.approved


def test_risk_never_increases_after_losses():
    acc = {**ACC, "day_start_equity": 100.0}
    v0 = evaluate_trade(**BASE)
    v1 = evaluate_trade(**{**BASE, "acc": acc, "equity": 99.6, "cash": 99.6})
    assert v1.risk_usd <= v0.risk_usd


def test_limit_breaches():
    lim = RiskLimits()
    assert limit_breaches(ACC, 99.0, lim)                       # -1 $ dans la journée
    assert limit_breaches({**ACC, "day_start_equity": 98.0}, 97.5, lim)  # -2,5 $ sur la semaine
    assert limit_breaches({**ACC, "day_start_equity": 95.5, "week_start_equity": 95.5}, 95.0, lim)  # drawdown 5 $
    assert not limit_breaches(ACC, 99.5, lim)
