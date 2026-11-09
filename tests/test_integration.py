"""Tests d'intégration : moteur complet, coupe-circuit, reprise, tableau de bord."""
import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from quantum_edge.config import Settings
from quantum_edge.engine import AwaitingCredentials, Engine
from quantum_edge.quantitative.library import StrategyLibrary
from quantum_edge.risk.circuit_breaker import RESUME_PHRASE


def _promote_sim(engine, family="momentum"):
    from quantum_edge.strategies.catalog import FAMILY_BY_NAME
    spec = FAMILY_BY_NAME[family].specs()[0]
    lib = StrategyLibrary(engine.paths["research"], simulated=True)
    lib.promote({"created": datetime.now(timezone.utc).isoformat(), "simulated_data": True, "leaderboard": [
        {"family": family, "chosen_spec": {"id": spec.id, "family": family, "params": dict(spec.params),
                                           "label": spec.label()},
         "allowed_regimes": [], "metrics": {"walk_forward": {"n": 200, "ev_r": 0.2, "ci_low": 0.05, "ci_high": 0.3,
                                                             "profit_factor": 1.5, "tstat": 3}},
         "score": 1.0, "failed": []}]})


def test_etoro_backend_requires_credentials(monkeypatch):
    monkeypatch.setenv("EXECUTION_BACKEND", "etoro_demo")
    try:
        Engine(Settings())
        assert False, "aurait dû exiger les clés"
    except AwaitingCredentials:
        pass


def test_scan_without_validated_strategy_never_trades():
    e = Engine(Settings())
    assert e.scan(require_open=False) == []
    assert e.account.open_positions() == []


def test_full_scan_records_decisions_with_all_agents():
    e = Engine(Settings())
    _promote_sim(e)
    data = e.load(3)
    e.scan(data=data, require_open=False)
    for d in e.db.query("SELECT payload FROM decisions"):
        p = json.loads(d["payload"])
        assert len(p["agents"]) == 9 and "12. autorisation du risk manager" in p["checks"]
    assert e.db.query("SELECT COUNT(*) n FROM scans")[0]["n"] == 1


def test_circuit_breaker_trips_and_requires_authorization():
    e = Engine(Settings())
    data = e.load(2)
    prices = {k: float(v["close"].iloc[-1]) for k, v in data.items()}
    e.cycle(data=data)
    acc = e.account.d
    acc["cash"] -= 1.2                         # perte de 1,20 $ dans la journée (> 1 $)
    e.db.set("account", acc)
    e.update_risk_state(prices, datetime.now(timezone.utc))
    assert e.breaker.state["tripped"] and not e.entries_allowed()[0]
    assert e.db.query("SELECT id FROM events WHERE kind='circuit_breaker'")
    e.update_risk_state(prices, datetime.now(timezone.utc))
    assert e.breaker.state["tripped"]           # aucune reprise automatique
    assert not e.breaker.authorize_resume("ok", "moi")[0]
    assert e.breaker.authorize_resume(RESUME_PHRASE, "moi")[0]
    e.update_risk_state(prices, datetime.now(timezone.utc))
    assert e.entries_allowed()[0] and not e.breaker.state["tripped"]


def test_dashboard_endpoints_and_controls():
    from quantum_edge.api.server import create_app
    e = Engine(Settings())
    e.cycle()
    c = TestClient(create_app(Settings()))
    ov = c.get("/api/overview").json()
    assert ov["simulated"] and ov["starting_capital"] == 100.0 and "SIMUL" in ov["label"]
    for ep in ("/api/market", "/api/agents", "/api/trades", "/api/lab", "/api/risk", "/api/weekly", "/api/equity"):
        assert c.get(ep).status_code == 200
    assert "etoro_api_key" not in json.dumps(c.get("/api/overview").json()).lower()
    assert c.post("/api/resume", json={"phrase": "x", "operator": "a"}).status_code == 400
    assert c.post("/api/emergency-stop", json={"reason": "test"}).json()["ok"]
    assert c.get("/api/risk").json()["emergency"]["active"]
    with c.websocket_connect("/ws") as ws:
        assert "overview" in ws.receive_json()


def test_dashboard_token_protects_controls(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "t0k3n")
    from quantum_edge.api.server import create_app
    c = TestClient(create_app(Settings()))
    assert c.post("/api/emergency-stop", json={}).status_code == 401
    assert c.post("/api/emergency-stop", json={}, headers={"X-Dashboard-Token": "t0k3n"}).status_code == 200


def test_restart_recovery_reconciles_before_entries():
    e = Engine(Settings())
    e.db.insert("orders", {"client_key": "k", "ts": "2026-01-01T00:00:00+00:00", "symbol": "SPY", "strategy": "s",
                           "side": "BUY", "amount": 10, "state": "uncertain", "payload": {}})
    e.db.set("heartbeat", {"ts": "x", "clean_shutdown": False})
    e.db.set("recovery", {"active": True})
    e2 = Engine(Settings())
    assert not e2.entries_allowed()[0]
    e2.startup_recovery()
    assert e2.entries_allowed()[0] and e2.executor.can_submit()[0]


def test_reports_generated():
    from quantum_edge.reports import daily_report, weekly_report
    e = Engine(Settings())
    e.cycle()
    assert daily_report(e).endswith(".md") and weekly_report(e).endswith(".md")
