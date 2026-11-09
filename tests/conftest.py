import pytest


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Chaque test a sa propre base et ses propres dossiers ; jamais de clés réelles."""
    monkeypatch.setenv("QE_ROOT", str(tmp_path))
    monkeypatch.setenv("QE_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("DATA_SOURCE", "synthetic")
    monkeypatch.setenv("EXECUTION_BACKEND", "simulated")
    monkeypatch.setenv("TRADING_MODE", "DEMO")
    for k in ("ETORO_API_KEY", "ETORO_USER_KEY", "XAI_API_KEY", "TELEGRAM_BOT_TOKEN", "DASHBOARD_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    yield tmp_path


@pytest.fixture
def small_data():
    from quantum_edge.marketdata.sources import SyntheticSource

    syms = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "XLE"]
    return SyntheticSource(end="2026-11-06").load_daily(syms, 8)
