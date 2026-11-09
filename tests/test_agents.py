from datetime import date

import pytest

from quantum_edge.agents.base import AgentReport
from quantum_edge.agents.macro import MacroAgent
from quantum_edge.agents.master import Candidate, decide
from quantum_edge.agents.regime import RegimeAgent
from quantum_edge.agents.sentiment import evaluate_investor
from quantum_edge.agents.technical import TechnicalAgent
from quantum_edge.marketdata import news
from quantum_edge.marketdata.quality import check_daily
from quantum_edge.marketdata.sources import SyntheticSource
from quantum_edge.risk.manager import RiskVerdict


def test_regime_and_technical_agents_use_real_inputs(small_data):
    df = small_data["AAPL"]
    r = RegimeAgent().analyze("AAPL", df, small_data["SPY"], ["bull"])
    assert r.details["market_regime"] in ("bull", "bear", "sideways")
    src = SyntheticSource(end="2026-11-06")
    intr = {tf: src.intraday("AAPL", tf) for tf in ("4h", "1h", "15m", "5m")}
    t = TechnicalAgent().analyze("AAPL", df, intr, require_intraday=True)
    assert set(t.details["timeframes"]) == {"1d", "4h", "1h", "15m", "5m"}
    assert "vwap" in t.details["timeframes"]["5m"]
    missing = TechnicalAgent().analyze("AAPL", df, {}, require_intraday=True)
    assert missing.vote == "unavailable"           # pas de données -> pas de trade


def test_macro_agent_vetoes_events_and_unknown_earnings(tmp_path):
    cal = tmp_path / "m.csv"
    cal.write_text("date,event,importance,source\n2026-11-10,FOMC,high,federalreserve.gov\n", encoding="utf-8")
    a = MacroAgent(cal, offline=True)
    assert a.analyze("SPY", "etf", 15, True, date(2026, 11, 9)).vote == "veto"
    assert a.analyze("SPY", "etf", 15, True, date(2026, 11, 20)).vote == "support"
    assert a.analyze("AAPL", "stock", 15, True, date(2026, 11, 20)).vote == "veto"   # résultats inconnus


def test_news_scoring_and_rss_parsing():
    xml = """<rss><channel><item><title>Apple beats estimates, shares surge</title>
    <pubDate>Mon, 09 Nov 2026 10:00:00 GMT</pubDate></item>
    <item><title>Regulators open antitrust probe</title><pubDate>Mon, 09 Nov 2026 11:00:00 GMT</pubDate></item>
    </channel></rss>"""
    h = news._parse(xml, "test")
    assert len(h) == 2 and h[0].published.year == 2026
    s = news.score(h)
    assert s["n"] == 2 and s["risk_mentions"] >= 1


def test_investor_evaluation():
    good = evaluate_investor({"monthly_returns": [0.02, 0.01, -0.005, 0.015] * 6, "max_drawdown": 0.08,
                              "avg_exposure": 0.7, "top_position_weight": 0.15,
                              "regime_returns": {"bull": 0.2, "bear": 0.02}})
    bad = evaluate_investor({"monthly_returns": [0.3, -0.25, 0.2, -0.2] * 6, "max_drawdown": 0.5,
                             "avg_exposure": 1.0, "top_position_weight": 0.8, "regime_returns": {"bull": 0.5, "bear": -0.4}})
    assert good["score"] > 70 > bad["score"]
    assert evaluate_investor({"monthly_returns": [0.1]})["score"] == 0


def test_data_quality_detects_stale_and_broken_data(small_data):
    import pandas as pd
    df = small_data["AAPL"]
    assert check_daily(df, df.index[-1], 4).ok
    assert not check_daily(df, df.index[-1] + pd.Timedelta(days=20), 4).fresh
    broken = df.copy()
    broken.iloc[-3, broken.columns.get_loc("close")] *= 2
    assert not check_daily(broken, df.index[-1], 4).ok


def _rep(agent, vote, conf=0.6):
    return AgentReport(agent, "AAPL", vote, f"{agent} {vote}", conf)


def _cand():
    return Candidate("AAPL", "x", "fam(x)", "momentum", "", "", 100.0, 0.03, 0.06, 0.015, 0.0015, "2026-11-09")


ALL = ["1_regime", "2_technical", "3_quant", "4_macro", "5_sentiment", "6_strategy_tester", "7_monte_carlo",
       "8_risk_manager", "9_execution", "10_auditor"]


def _verdict(ok=True):
    return RiskVerdict(ok, 15.0 if ok else 0, 0.49, [] if ok else ["x"],
                       {"corrélation ≤ 0.7": True}, {"cost_to_risk": 0.08})


def test_master_buys_only_with_full_support():
    reps = {a: _rep(a, "support") for a in ALL}
    md = decide(_cand(), reps, {"fresh": True, "quality": True}, _verdict())
    assert md.decision == "BUY" and md.authorized and md.amount == 15.0
    rec = md.to_record()
    for k in ("instrument", "direction", "strategy", "entry_conditions", "stop_loss", "take_profit",
              "position_size_usd", "expected_risk_usd", "expected_reward_usd", "transaction_costs_usd",
              "supporting_evidence", "agent_disagreements", "confidence_estimate", "authorized"):
        assert k in rec


@pytest.mark.parametrize("agent,vote", [("5_sentiment", "veto"), ("4_macro", "oppose"), ("2_technical", "unavailable"),
                                        ("7_monte_carlo", "oppose"), ("1_regime", "oppose")])
def test_master_refuses_on_veto_or_missing_support(agent, vote):
    reps = {a: _rep(a, "support") for a in ALL}
    reps[agent] = _rep(agent, vote)
    md = decide(_cand(), reps, {"fresh": True, "quality": True}, _verdict())
    assert md.decision == "NO TRADE" and not md.authorized and md.disagreements


def test_master_cannot_override_risk_manager():
    reps = {a: _rep(a, "support") for a in ALL}
    assert decide(_cand(), reps, {"fresh": True, "quality": True}, _verdict(False)).decision == "NO TRADE"
    assert decide(_cand(), reps, {"fresh": False, "quality": True}, _verdict()).decision == "NO TRADE"


def test_grok_is_optional_and_parses(monkeypatch):
    from quantum_edge.agents.grok import GrokAgent, parse_report
    assert not GrokAgent(api_key="").enabled
    r = parse_report('x {"sentiment": -0.2, "event_risk": "high", "earnings_in_days": 3, "veto": true, "summary": "s"}')
    assert r.used and r.veto and r.event_risk == "high"
