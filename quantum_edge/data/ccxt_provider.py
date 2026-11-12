"""Crypto market data through CCXT *public* endpoints only.

The exchange objects are created without any credentials, and this module only calls
read endpoints (markets, tickers, candles, order book, funding rate)."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd

from ..instruments import Instrument
from .base import (OHLCV, TF_SECONDS, HistoricalDataProvider, MarketDataProvider, OrderBookProvider,
                   Quote, empty_frame)


class CcxtProvider(MarketDataProvider, HistoricalDataProvider, OrderBookProvider):
    name = "ccxt"

    def __init__(self, exchanges: list[str]):
        self.exchange_names = exchanges
        self._ex: dict[str, object] = {}
        self._route: dict[str, str] = {}      # symbol -> exchange name
        self._unsupported: set[str] = set()
        self._funding_ex = None
        self._funding_failed = False
        self._last_error: str | None = None

    # --- routing ----------------------------------------------------------------------
    def _exchange(self, name: str):
        if name not in self._ex:
            import ccxt
            ex = getattr(ccxt, name)({"enableRateLimit": True, "timeout": 20000, "requests_trust_env": True})
            ex.load_markets()
            self._ex[name] = ex
        return self._ex[name]

    def supports(self, inst: Instrument) -> bool:
        return self._route_for(inst.provider_symbol) is not None

    def _route_for(self, symbol: str):
        if symbol in self._route:
            return self._route[symbol]
        if symbol in self._unsupported:
            return None
        reachable = 0
        for name in self.exchange_names:
            try:
                ex = self._exchange(name)
            except Exception as e:
                self._last_error = f"{name}: {type(e).__name__}: {e}"[:200]
                continue
            reachable += 1
            m = ex.markets.get(symbol)
            if m and m.get("active", True) and m.get("spot", True):
                self._route[symbol] = name
                return name
        if reachable == len(self.exchange_names):
            self._unsupported.add(symbol)     # genuinely not listed anywhere we look
        return None

    # --- quotes -----------------------------------------------------------------------
    def quotes(self, instruments: list[Instrument]) -> dict[str, Quote]:
        by_ex: dict[str, list[Instrument]] = {}
        for inst in instruments:
            name = self._route_for(inst.provider_symbol)
            if name:
                by_ex.setdefault(name, []).append(inst)
        if not by_ex and not self._ex and self._last_error:
            raise ConnectionError(f"no crypto exchange reachable ({self._last_error})")
        out: dict[str, Quote] = {}
        for name, insts in by_ex.items():
            ex = self._ex[name]
            tickers = ex.fetch_tickers([i.provider_symbol for i in insts])
            for inst in insts:
                t = tickers.get(inst.provider_symbol)
                if not t or t.get("last") is None:
                    continue
                ts_ms = t.get("timestamp") or ex.milliseconds()
                out[inst.symbol] = Quote(
                    symbol=inst.symbol, price=float(t["last"]),
                    ts=datetime.fromtimestamp(ts_ms / 1000, timezone.utc), source=f"ccxt:{name}",
                    bid=_f(t.get("bid")), ask=_f(t.get("ask")), volume=_f(t.get("baseVolume")),
                    change_pct=_f(t.get("percentage")))
        return out

    # --- candles ----------------------------------------------------------------------
    def history(self, inst: Instrument, timeframe: str, bars: int) -> pd.DataFrame:
        name = self._route_for(inst.provider_symbol)
        if not name:
            return empty_frame()
        ex = self._ex[name]
        step = TF_SECONDS[timeframe] * 1000
        since = ex.milliseconds() - bars * step
        rows: list[list] = []
        while len(rows) < bars + 5:
            chunk = ex.fetch_ohlcv(inst.provider_symbol, timeframe, since=since, limit=1000)
            if not chunk:
                break
            rows.extend(chunk)
            nxt = chunk[-1][0] + step
            if nxt <= since or len(chunk) < 2 or nxt > ex.milliseconds():
                break
            since = nxt
            time.sleep(ex.rateLimit / 1000)
        if not rows:
            return empty_frame()
        df = pd.DataFrame(rows, columns=["ts"] + OHLCV).drop_duplicates("ts").sort_values("ts")
        df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
        return df.astype(float)

    # --- microstructure ---------------------------------------------------------------
    def order_book(self, inst: Instrument, depth: int = 20) -> dict | None:
        name = self._route_for(inst.provider_symbol)
        if not name:
            return None
        ob = self._ex[name].fetch_order_book(inst.provider_symbol, depth)
        bids, asks = ob.get("bids") or [], ob.get("asks") or []
        if not bids or not asks:
            return None
        bv = sum(b[1] for b in bids[:depth])
        av = sum(a[1] for a in asks[:depth])
        mid = (bids[0][0] + asks[0][0]) / 2
        return {"bid": bids[0][0], "ask": asks[0][0], "spread_bps": (asks[0][0] - bids[0][0]) / mid * 1e4,
                "imbalance": (bv - av) / (bv + av) if bv + av else 0.0, "source": f"ccxt:{name}"}

    def funding_rate(self, base: str) -> float | None:
        """Latest perpetual funding rate (Binance USDT-margined), or None when not accessible."""
        if self._funding_failed:
            return None
        try:
            if self._funding_ex is None:
                import ccxt
                self._funding_ex = ccxt.binanceusdm({"enableRateLimit": True, "timeout": 20000, "requests_trust_env": True})
            r = self._funding_ex.fetch_funding_rate(f"{base}/USDT:USDT")
            return _f(r.get("fundingRate"))
        except Exception:
            self._funding_failed = True
            return None


def _f(x):
    return None if x is None else float(x)
