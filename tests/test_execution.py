import pytest

from quantum_edge.config import Settings
from quantum_edge.database.db import Database
from quantum_edge.execution.brokers import EtoroDemoBroker, OrderResult
from quantum_edge.execution.etoro_client import ApiError
from quantum_edge.execution.executor import Executor
from quantum_edge.risk.account import Account

ORDER = {"client_key": "2026-11-09:AAPL:s1", "symbol": "AAPL", "strategy": "s1", "amount": 15.0, "price": 100.0,
         "stop": 97.0, "target": 106.0, "cost_pct": 0.0015, "risk_usd": 0.49}


class FakeBroker:
    simulated = False
    name = "fake"

    def __init__(self, state="confirmed"):
        self.state, self.calls, self.remote = state, 0, []

    def submit_open(self, *a, **k):
        self.calls += 1
        return OrderResult(self.state, "O1", "P1" if self.state == "confirmed" else None, 100.0, 0.15)

    def close(self, p, price):
        return OrderResult("confirmed", fill_price=price)

    def remote_positions(self):
        return self.remote


def _ex(broker):
    s = Settings()
    db = Database(s.db_path)
    acc = Account(db, 100.0, simulated=False)
    return Executor(db, acc, broker, s, log=lambda *_: None), acc, db


def test_duplicate_order_blocked():
    b = FakeBroker()
    ex, acc, _ = _ex(b)
    assert ex.open(ORDER).state == "confirmed"
    r = ex.open(ORDER)
    assert r.state == "rejected" and "double" in r.message and b.calls == 1
    assert acc.d["cash"] == pytest.approx(100 - 15 - 15 * 0.0015 / 2)


def test_uncertain_order_blocks_everything_until_reconciled():
    b = FakeBroker("uncertain")
    ex, acc, db = _ex(b)
    assert ex.open(ORDER).state == "uncertain"
    r = ex.open({**ORDER, "client_key": "other"})
    assert r.state == "rejected" and b.calls == 1
    # le rapprochement retrouve la position chez le courtier -> confirmée et comptabilisée
    db.update("orders", {"client_key": ORDER["client_key"]}, {"broker_position_id": "P9"})
    b.remote = [{"positionId": "P9", "orderId": "O1", "openRate": 100.5, "units": 0.149}]
    rep = ex.reconcile({})
    assert rep["confirmed"] == 1 and len(acc.open_positions()) == 1 and ex.can_submit()[0]


def test_position_closed_by_broker_is_booked():
    b = FakeBroker()
    ex, acc, _ = _ex(b)
    ex.open(ORDER)
    b.remote = []                       # eToro a exécuté le stop-loss
    rep = ex.reconcile({"AAPL": 96.9})
    assert rep["closed_by_broker"] == 1 and not acc.open_positions()
    closed = acc.closed_positions()[0]
    assert closed["pnl"] < 0 and "eToro" in closed["reason"]


def test_simulated_monitor_stop_target_and_time_exit():
    from quantum_edge.execution.brokers import SimulatedBroker

    ex, acc, _ = _ex(SimulatedBroker(0.0))
    ex.open(ORDER)
    ex.monitor({"AAPL": {"price": 106.5, "high": 107, "low": 101, "bar_date": "2026-11-10"}}, 15)
    assert acc.closed_positions()[0]["reason"] == "take-profit"
    ex.open({**ORDER, "client_key": "k2"})
    for i in range(15):
        ex.monitor({"AAPL": {"price": 101, "high": 101.5, "low": 100.5, "bar_date": f"2026-12-{i + 1:02d}"}}, 15)
    assert acc.closed_positions()[-1]["reason"] == "sortie temporelle"


class FakeClient:
    def __init__(self, fail=None, positions=None):
        self.fail, self.pos = fail, positions or []

    def open_by_amount(self, *a, **k):
        if self.fail:
            raise self.fail
        return {"orderForOpen": {"orderID": 77}}

    def positions(self):
        return self.pos


def test_etoro_broker_confirms_only_when_position_visible():
    ok = EtoroDemoBroker(FakeClient(positions=[{"positionID": 5, "orderID": 77, "openRate": 101.0, "units": 0.1}]),
                         confirm_attempts=1, confirm_wait=0)
    r = ok.submit_open("AAPL", 10, 100, 97, 106, "k")
    assert r.state == "confirmed" and r.broker_position_id == "5" and r.fill_price == 101.0
    nothing = EtoroDemoBroker(FakeClient(), confirm_attempts=1, confirm_wait=0)
    assert nothing.submit_open("AAPL", 10, 100, 97, 106, "k").state == "uncertain"
    timeout = EtoroDemoBroker(FakeClient(fail=TimeoutError("lent")), confirm_attempts=1, confirm_wait=0)
    assert timeout.submit_open("AAPL", 10, 100, 97, 106, "k").state == "uncertain"
    bad = EtoroDemoBroker(FakeClient(fail=ApiError(400, "invalide")), confirm_attempts=1, confirm_wait=0)
    assert bad.submit_open("AAPL", 10, 100, 97, 106, "k").state == "rejected"
