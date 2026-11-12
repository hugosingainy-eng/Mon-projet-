"""Provider interfaces. Data adapters are READ-ONLY by construction: none of these interfaces
has a method that could place, modify or cancel an order."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from ..instruments import Instrument

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
OHLCV = ["open", "high", "low", "close", "volume"]


@dataclass
class Quote:
    symbol: str
    price: float
    ts: datetime                 # timestamp of the observation at the source
    source: str
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None  # in units of the instrument, session / 24h
    change_pct: float | None = None
    extra: dict = field(default_factory=dict)

    def age(self, now: datetime | None = None) -> float:
        return ((now or datetime.now(timezone.utc)) - self.ts).total_seconds()


class MarketDataProvider(ABC):
    """Latest prices."""
    name: str = "provider"

    @abstractmethod
    def quotes(self, instruments: list[Instrument]) -> dict[str, Quote]: ...


class HistoricalDataProvider(ABC):
    """OHLCV candles: DataFrame indexed by UTC bar-open time with columns open/high/low/close/volume."""

    @abstractmethod
    def history(self, inst: Instrument, timeframe: str, bars: int) -> pd.DataFrame: ...


class OrderBookProvider(ABC):
    @abstractmethod
    def order_book(self, inst: Instrument, depth: int = 20) -> dict | None: ...


class NewsProvider(ABC):
    @abstractmethod
    def news(self, inst: Instrument) -> list[dict]: ...


class AlternativeDataProvider(ABC):
    """Regulatory disclosures and other non-price data."""

    @abstractmethod
    def fetch(self) -> dict: ...


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=OHLCV, index=pd.DatetimeIndex([], tz="UTC"), dtype=float)


def drop_forming_bar(df: pd.DataFrame, timeframe: str, now: datetime | None = None) -> pd.DataFrame:
    """Remove the last candle if it has not closed yet, so signals only ever use completed bars."""
    if df.empty:
        return df
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    if df.index[-1] + pd.Timedelta(seconds=TF_SECONDS[timeframe]) > now:
        return df.iloc[:-1]
    return df


def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    rule = {"30m": "30min", "1h": "1h", "4h": "4h", "1d": "1D"}[timeframe]
    out = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return out.dropna(subset=["close"])
