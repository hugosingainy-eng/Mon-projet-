"""Test fixtures.

IMPORTANT: the price series below are SYNTHETIC and exist only so the test-suite can run
offline and deterministically. They live in tests/ and are never imported by the application,
which only ever uses real provider data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from quantum_edge.config import Settings
from quantum_edge.data.base import TF_SECONDS, Quote
from quantum_edge.data.hub import DataHub
from quantum_edge.db import Database
from quantum_edge.instruments import UNIVERSE


def synthetic_candles(seed: int, bars: int, timeframe: str = "15m", start_price: float = 100.0,
                      end: datetime | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    step = TF_SECONDS[timeframe]
    end = end or datetime.now(timezone.utc)
    end_ts = int(end.timestamp()) // step * step
    idx = pd.to_datetime([end_ts - step * (bars - i) for i in range(bars)], unit="s", utc=True)
    drift = np.repeat(rng.normal(0, 0.0006, bars // 200 + 1), 200)[:bars]     # slow regimes
    ret = drift + rng.normal(0, 0.004, bars)
    close = start_price * np.exp(np.cumsum(ret))
    open_ = np.concatenate(([start_price], close[:-1]))
    spread = np.abs(rng.normal(0, 0.002, bars)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol = rng.uniform(500, 1500, bars)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)


class FakeProvider:
    """Offline stand-in for a market-data provider (tests only)."""

    def __init__(self, name: str, bars: int = 3000):
        self.name = name
        self.bars = bars
        self.fail = False
        self.prices: dict[str, float] = {}
        self.now = None          # override the quote timestamp

    def _seed(self, inst):
        return abs(hash(inst.symbol)) % 100000 if False else sum(map(ord, inst.symbol))

    def history(self, inst, timeframe, bars):
        if self.fail:
            raise ConnectionError("simulated outage")
        start = 1.1 if inst.asset_class == "forex" else 100.0
        return synthetic_candles(self._seed(inst), min(bars, self.bars), timeframe, start).iloc[-bars:]

    def quotes(self, instruments):
        if self.fail:
            raise ConnectionError("simulated outage")
        out = {}
        ts = self.now or datetime.now(timezone.utc)
        for inst in instruments:
            px = self.prices.get(inst.symbol)
            if px is None:
                px = 1.1 if inst.asset_class == "forex" else 100.0
            bid, ask = (px * 0.9998, px * 1.0002) if self.name == "ccxt" else (None, None)
            out[inst.symbol] = Quote(inst.symbol, px, ts, f"fake:{self.name}", bid, ask, 1e6, 0.0)
        return out

    def order_book(self, inst, depth=20):
        return {"bid": 99.98, "ask": 100.02, "spread_bps": 4.0, "imbalance": 0.1, "source": "fake"}

    def funding_rate(self, base):
        return None

    def news(self, inst):
        return []


@pytest.fixture
def settings(tmp_path):
    s = Settings()
    s.db_path = str(tmp_path / "qe.db")
    s.lab_target = 300
    s.lab_crypto_bars = 3000
    s.crypto_quote_seconds = 0
    s.yahoo_quote_seconds = 0
    return s


@pytest.fixture
def db(settings):
    return Database(settings.db_path)


@pytest.fixture
def providers():
    return {"ccxt": FakeProvider("ccxt"), "yahoo": FakeProvider("yahoo")}


@pytest.fixture
def hub(settings, providers):
    h = DataHub(settings, providers)
    h.refresh_quotes(force=True)
    return h
