"""Tests de sécurité : aucune exécution réelle ne doit être possible."""
import pytest

from quantum_edge import safety
from quantum_edge.execution.etoro_client import EtoroDemoClient


def test_live_mode_refused(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    with pytest.raises(safety.SafetyViolation):
        safety.check_mode()


@pytest.mark.parametrize("path", [
    "/api/v1/trading/execution/market-open-orders/by-amount",
    "/api/v1/trading/execution/real/market-open-orders/by-amount",
    "/api/v2/trading/execution/orders",
    "/api/v1/trading/info/real/portfolio",
])
def test_non_demo_routes_blocked(path):
    with pytest.raises(safety.SafetyViolation):
        safety.check_request("POST", path)


def test_demo_routes_allowed():
    safety.check_request("POST", "/api/v1/trading/execution/demo/market-open-orders/by-amount")
    safety.check_request("GET", "/api/v1/trading/info/demo/portfolio")
    safety.check_request("GET", "/api/v1/market-data/search")


@pytest.mark.parametrize("args", [(True, 2, 10, 100), (False, 1, 10, 100), (True, 1, 150, 100), (True, 1, 0, 100)])
def test_forbidden_orders(args):
    with pytest.raises(safety.SafetyViolation):
        safety.check_order(*args)


def test_safety_module_is_immutable():
    with pytest.raises(safety.SafetyViolation):
        safety._ALLOWED_MODE = "LIVE"
    with pytest.raises(safety.SafetyViolation):
        safety.check_order = lambda *a: None


def test_client_checks_safety_before_any_network_call(monkeypatch):
    class Boom:
        def request(self, *a, **k):
            raise AssertionError("le réseau n'aurait jamais dû être appelé")

    c = EtoroDemoClient("k", "u", session=Boom())
    with pytest.raises(safety.SafetyViolation):
        c._req("POST", "/api/v1/trading/execution/real/x")
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    with pytest.raises(safety.SafetyViolation):
        c._req("GET", "/api/v1/trading/info/demo/portfolio")


def test_secrets_redacted(monkeypatch):
    monkeypatch.setenv("ETORO_USER_KEY", "SECRET123456")
    assert "SECRET123456" not in safety.redact("erreur avec SECRET123456 dedans")


def test_client_requires_keys():
    with pytest.raises(ValueError):
        EtoroDemoClient("", "")
