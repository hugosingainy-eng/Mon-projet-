"""DataHub: one place the rest of the system asks for prices, candles and FX rates.
It never synthesizes data: when a provider fails, the previous observation stays (with its
original timestamp) and becomes stale, which blocks trading on that instrument."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import pandas as pd

from ..config import Settings
from ..instruments import BY_SYMBOL, UNIVERSE, Instrument, is_market_open
from .base import TF_SECONDS, Quote, drop_forming_bar, empty_frame

# how to derive "EUR per 1 unit of currency" from forex pairs in the universe
_FX_PATH = {
    "USD": [("EURUSD", -1)],
    "GBP": [("EURGBP", -1)],
    "JPY": [("EURUSD", -1), ("USDJPY", -1)],
    "CHF": [("EURUSD", -1), ("USDCHF", -1)],
    "CAD": [("EURUSD", -1), ("USDCAD", -1)],
}


class DataHub:
    def __init__(self, settings: Settings, providers: dict[str, object]):
        self.s = settings
        self.providers = providers
        self.quotes: dict[str, Quote] = {}
        self._candles: dict[tuple[str, str], tuple] = {}   # (fetched_at, frame, bars_requested)
        self._last_poll: dict[str, float] = {}
        self.health: dict[str, dict] = {n: {"last_ok": None, "last_error": None, "errors": 0}
                                        for n in providers}
        self._lock = threading.RLock()

    # --- quotes -----------------------------------------------------------------------
    def refresh_quotes(self, now: datetime | None = None, force: bool = False) -> list[str]:
        """Poll each provider when due. Returns error messages (empty when all fine)."""
        now = now or datetime.now(timezone.utc)
        errors = []
        for name, prov in self.providers.items():
            every = self.s.crypto_quote_seconds if name == "ccxt" else self.s.yahoo_quote_seconds
            if not force and time.monotonic() - self._last_poll.get(name, -1e9) < every:
                continue
            insts = [i for i in UNIVERSE if i.provider == name
                     and (is_market_open(i, now) or i.symbol not in self.quotes)]
            if not insts:
                continue
            self._last_poll[name] = time.monotonic()
            try:
                got = prov.quotes(insts)
                with self._lock:
                    for sym, q in got.items():
                        old = self.quotes.get(sym)
                        if old is None or q.ts >= old.ts:
                            self.quotes[sym] = q
                if got:
                    self.health[name]["last_ok"] = now
                else:
                    self.health[name]["last_error"] = "provider returned no quotes"
                    errors.append(f"{name}: provider returned no quotes")
            except Exception as e:  # network / API failure: keep old data, report
                self.health[name]["last_error"] = f"{type(e).__name__}: {e}"[:300]
                self.health[name]["errors"] += 1
                errors.append(f"{name}: {type(e).__name__}: {e}"[:300])
        return errors

    def quote(self, symbol: str) -> Quote | None:
        return self.quotes.get(symbol)

    def is_fresh(self, symbol: str, now: datetime | None = None) -> bool:
        q = self.quotes.get(symbol)
        if q is None:
            return False
        return q.age(now) <= self.s.max_quote_age[BY_SYMBOL[symbol].asset_class]

    # --- candles ----------------------------------------------------------------------
    def candles(self, inst: Instrument, timeframe: str, bars: int = 600,
                max_age: float | None = None, completed_only: bool = True) -> pd.DataFrame:
        key = (inst.symbol, timeframe)
        max_age = max_age if max_age is not None else max(60.0, TF_SECONDS[timeframe] / 3)
        with self._lock:
            hit = self._candles.get(key)
        if hit is None or time.monotonic() - hit[0] > max_age or hit[2] < bars:
            prov = self.providers.get(inst.provider)
            if prov is None:
                return empty_frame()
            df = prov.history(inst, timeframe, bars)
            with self._lock:
                # Yahoo always returns its whole available window, so any request size is satisfied
                self._candles[key] = (time.monotonic(), df, bars if inst.provider == "ccxt" else 10 ** 9)
        else:
            df = hit[1]
        df = df.iloc[-bars:]
        return drop_forming_bar(df, timeframe) if completed_only else df

    def prefetch(self, instruments: list[Instrument], timeframe: str, max_age: float = 900.0) -> list[str]:
        """Refresh the candle cache for many instruments, batching where the provider allows."""
        errors = []
        stale = [i for i in instruments
                 if (hit := self._candles.get((i.symbol, timeframe))) is None
                 or time.monotonic() - hit[0] > max_age]
        for name, prov in self.providers.items():
            mine = [i for i in stale if i.provider == name]
            if not mine:
                continue
            try:
                if hasattr(prov, "history_many"):
                    got = prov.history_many(mine, timeframe)
                    with self._lock:
                        for sym, df in got.items():
                            self._candles[(sym, timeframe)] = (time.monotonic(), df, 10 ** 9)
                else:
                    for i in mine:
                        df = prov.history(i, timeframe, 1000)
                        with self._lock:
                            self._candles[(i.symbol, timeframe)] = (time.monotonic(), df, 1000)
            except Exception as e:
                errors.append(f"{name} {timeframe} history: {type(e).__name__}: {e}"[:300])
        return errors

    def cached_candles(self, inst: Instrument, timeframe: str) -> pd.DataFrame | None:
        """Completed candles already in the cache (no network call), or None."""
        hit = self._candles.get((inst.symbol, timeframe))
        return None if hit is None or hit[1].empty else drop_forming_bar(hit[1], timeframe)

    # --- FX ---------------------------------------------------------------------------
    def fx_rate(self, ccy: str):
        """EUR per 1 unit of `ccy` as (rate, source, timestamp), or None when unknown."""
        if ccy == self.s.base_currency:
            return 1.0, "identity", datetime.now(timezone.utc)
        path = _FX_PATH.get(ccy)
        if not path:
            return None
        rate, oldest = 1.0, None
        for pair, power in path:
            q = self.quotes.get(pair)
            if q is None or q.price <= 0:
                return None
            rate *= q.price ** power
            oldest = q.ts if oldest is None else min(oldest, q.ts)
        return rate, "yahoo:" + "*".join(p for p, _ in path), oldest

    # --- microstructure ---------------------------------------------------------------
    def order_book(self, inst: Instrument):
        prov = self.providers.get(inst.provider)
        return prov.order_book(inst) if hasattr(prov, "order_book") else None

    def funding_rate(self, base: str):
        prov = self.providers.get("ccxt")
        return prov.funding_rate(base) if hasattr(prov, "funding_rate") else None
