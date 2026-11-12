"""Dashboard API, controls, and the paper-only guarantees."""
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import quantum_edge
from quantum_edge.api import create_app
from quantum_edge.config import SecurityError, Settings, load_settings, validate_paper_only
from quantum_edge.broker import PaperBroker

SRC = Path(quantum_edge.__file__).parent


@pytest.fixture
def client(settings, providers):
    app = create_app(settings, providers, run_engine=False)
    app.state.engine.hub.refresh_quotes(force=True)
    with TestClient(app) as c:
        c.engine = app.state.engine
        yield c


def test_read_endpoints_have_documented_shapes(client):
    assert client.get("/api/health").json() == {"ok": True, "mode": "paper", "version": quantum_edge.__version__}
    st = client.get("/api/state").json()
    assert st["experiment"]["status"] == "idle" and st["experiment"]["mode"] == "paper"
    assert st["experiment"]["remaining_seconds"] == 5 * 86400
    p = st["portfolio"]
    assert p["initial_capital"] == p["equity"] == p["cash"] == 1000.0 and p["currency"] == "EUR"
    assert st["trading"]["win_rate"] is None and st["trading"]["closed_trades"] == 0     # no invented stats
    assert st["lab"]["target"] == client.engine.s.lab_target and st["lab"]["completed"] == 0
    for path in ("positions", "trades", "equity", "lab/top", "strategies", "signals", "decisions", "incidents", "news"):
        assert client.get(f"/api/{path}").json() == [] or path == "incidents", path
    market = client.get("/api/market").json()
    assert {"instrument", "asset_class", "tradable", "price", "provider", "last_update", "market_open", "stale"} <= set(market[0])
    assert any(not m["tradable"] for m in market) and any(m["asset_class"] == "forex" for m in market)
    assert len(client.get("/api/agents").json()) == 14
    el = client.get("/api/elite").json()
    assert el["principles"] and el["filings"] == [] and el["holdings"] == []           # nothing invented offline
    assert set(client.get("/api/lab/summary").json()) == {"by_evaluation", "by_method", "by_family"}


def test_controls_are_wired_to_the_engine(client):
    post = lambda a, **b: client.post(f"/api/control/{a}", json=b or None).json()
    assert post("start")["ok"] and client.engine.state["status"] == "running"
    assert post("pause")["ok"] and client.get("/api/state").json()["experiment"]["status"] == "paused"
    assert post("resume")["ok"]
    assert not post("emergency_stop")["ok"]                         # needs confirm
    assert post("emergency_stop", confirm=True)["ok"] and client.engine.state["status"] == "halted"
    assert not post("reset")["ok"]
    assert post("reset", confirm=True)["ok"] and client.engine.state["status"] == "idle"
    assert not post("buy")["ok"]


def test_run_experiments_button_runs_the_lab(client):
    assert client.post("/api/control/run_experiments").json()["ok"]
    client.engine.lab._thread.join(timeout=120)
    lab = client.get("/api/state").json()["lab"]
    assert lab["completed"] == client.engine.s.lab_target and lab["progress_pct"] == 100.0
    top = client.get("/api/lab/top").json()
    assert len(top) == 20 and {"val_sharpe", "test_sharpe", "evaluation", "params", "score"} <= set(top[0])
    assert sum(client.get("/api/lab/summary").json()["by_method"].values()) == lab["completed"]


def test_report_and_websocket(client):
    rep = client.get("/api/report").json()
    assert rep["ledger_audit"]["ok"] and rep["caveats"] and rep["trades"] == []
    html = client.get("/api/report.html")
    assert html.status_code == 200 and "PAPER TRADING" in html.text
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "state" and msg["data"]["portfolio"]["equity"] == 1000.0


# --- paper-only security ---------------------------------------------------------------
def test_refuses_any_mode_but_paper(tmp_path):
    s = Settings(); s.trading_mode = "live"
    with pytest.raises(SecurityError):
        validate_paper_only(s)
    with pytest.raises(SecurityError):
        PaperBroker(s, None, None)
    s = Settings(); s.max_exposure_pct = 2.0
    with pytest.raises(SecurityError, match="leverage"):
        validate_paper_only(s)


def test_refuses_to_start_with_credentials_or_live_env(monkeypatch):
    monkeypatch.setenv("QE_TRADING_MODE", "live")
    with pytest.raises(SecurityError):
        load_settings("/nonexistent.json")
    monkeypatch.delenv("QE_TRADING_MODE")
    monkeypatch.setenv("QE_BROKER_API_KEY", "abc")
    with pytest.raises(SecurityError, match="credential"):
        load_settings("/nonexistent.json")


def test_source_contains_no_order_or_credential_code():
    """No broker order call and no credential field anywhere in the application source."""
    forbidden = re.compile(r"create_order|createOrder|create_market_order|create_limit_order|cancel_order|"
                           r"edit_order|withdraw\(|submit_order|place_order|['\"]apiKey['\"]|['\"]secret['\"]|"
                           r"api_secret|private_key|set_sandbox_mode\(False")
    hits = [f"{f.name}:{i}" for f in SRC.rglob("*.py") for i, line in enumerate(f.read_text().splitlines(), 1)
            if forbidden.search(line)]
    assert not hits, hits


def test_no_api_route_can_place_an_order(client):
    routes = {(m, r.path) for r in client.app.routes if hasattr(r, "methods") for m in r.methods}
    writes = {p for m, p in routes if m in ("POST", "PUT", "PATCH", "DELETE")}
    assert writes == {"/api/control/{action}"}
    assert not any(k in p for _, p in routes for k in ("order", "trade/", "buy", "sell", "live"))


def test_data_adapters_are_read_only():
    from quantum_edge.data.ccxt_provider import CcxtProvider
    from quantum_edge.data.yahoo_provider import YahooProvider
    for cls in (CcxtProvider, YahooProvider):
        public = {n for n in dir(cls) if not n.startswith("_")}
        assert public <= {"name", "quotes", "history", "history_many", "order_book", "funding_rate", "news", "supports"}
