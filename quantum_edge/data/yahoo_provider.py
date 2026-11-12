"""Yahoo Finance adapter (unofficial API via yfinance): equities, ETFs, forex, indices, futures.

Limitations, stated rather than hidden: quotes may be delayed for some instruments, there is no
bid/ask (a modelled spread is used and flagged), and intraday history is limited
(1m: 7 days, 5m/15m: 60 days, 1h: 730 days)."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from ..instruments import Instrument
from .base import OHLCV, HistoricalDataProvider, MarketDataProvider, NewsProvider, Quote, empty_frame

_PERIOD = {"1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d", "1h": "730d", "1d": "10y"}


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return empty_frame()
    df = df.rename(columns=str.lower)[OHLCV].dropna(subset=["close"])
    idx = pd.DatetimeIndex(df.index)
    df.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return df.astype(float)


class YahooProvider(MarketDataProvider, HistoricalDataProvider, NewsProvider):
    name = "yahoo"

    def quotes(self, instruments: list[Instrument]) -> dict[str, Quote]:
        import yfinance as yf
        if not instruments:
            return {}
        tickers = [i.provider_symbol for i in instruments]
        raw = yf.download(tickers=tickers, period="1d", interval="1m", group_by="ticker",
                          progress=False, threads=False, auto_adjust=False)
        out: dict[str, Quote] = {}
        if raw is None or raw.empty:
            return out
        for inst in instruments:
            try:
                sub = raw[inst.provider_symbol] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                continue
            sub = _normalize(sub)
            if sub.empty:
                continue
            last = sub.iloc[-1]
            first_open = float(sub["open"].iloc[0])
            out[inst.symbol] = Quote(
                symbol=inst.symbol, price=float(last["close"]),
                # a 1-minute bar is stamped with its open time; the close is observed up to 60s later
                ts=min(sub.index[-1].to_pydatetime() + pd.Timedelta(seconds=60), datetime.now(timezone.utc)),
                source="yahoo", volume=float(sub["volume"].sum()),
                change_pct=(float(last["close"]) / first_open - 1) * 100 if first_open else None,
                extra={"change_basis": "session open"})
        return out

    def history(self, inst: Instrument, timeframe: str, bars: int) -> pd.DataFrame:
        import yfinance as yf
        df = yf.Ticker(inst.provider_symbol).history(period=_PERIOD[timeframe], interval=timeframe,
                                                     auto_adjust=False)
        return _normalize(df).iloc[-bars:]

    def history_many(self, instruments: list[Instrument], timeframe: str) -> dict[str, pd.DataFrame]:
        """One batched request for many tickers (keeps the request count low)."""
        import yfinance as yf
        if not instruments:
            return {}
        raw = yf.download(tickers=[i.provider_symbol for i in instruments], period=_PERIOD[timeframe],
                          interval=timeframe, group_by="ticker", progress=False, threads=False,
                          auto_adjust=False)
        out = {}
        if raw is None or raw.empty:
            return out
        for inst in instruments:
            try:
                sub = raw[inst.provider_symbol] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                continue
            sub = _normalize(sub)
            if not sub.empty:
                out[inst.symbol] = sub
        return out

    def news(self, inst: Instrument) -> list[dict]:
        """Headlines with source and timestamp: Yahoo's news API, then its public RSS feed."""
        try:
            items = self._news_api(inst)
            if items:
                return items
        except Exception:
            pass
        return self._news_rss(inst)

    @staticmethod
    def _news_rss(inst: Instrument) -> list[dict]:
        import urllib.parse
        import urllib.request
        import xml.etree.ElementTree as ET
        from email.utils import parsedate_to_datetime
        url = ("https://feeds.finance.yahoo.com/rss/2.0/headline?s="
               + urllib.parse.quote(inst.provider_symbol) + "&region=US&lang=en-US")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            root = ET.fromstring(r.read())
        out = []
        for it in root.iter("item"):
            title, link, when = it.findtext("title"), it.findtext("link"), it.findtext("pubDate")
            if not (title and link and when):
                continue
            try:
                ts = parsedate_to_datetime(when)
            except (TypeError, ValueError):
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            out.append({"title": title.strip(), "url": link.strip(), "publisher": "Yahoo Finance RSS",
                        "ts": ts.astimezone(timezone.utc)})
        return out

    @staticmethod
    def _news_api(inst: Instrument) -> list[dict]:
        import yfinance as yf
        items = yf.Ticker(inst.provider_symbol).news or []
        out = []
        for it in items:
            c = it.get("content") or it
            title = c.get("title")
            url = ((c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url")
                   or c.get("link"))
            when = c.get("pubDate") or c.get("displayTime") or c.get("providerPublishTime")
            publisher = (c.get("provider") or {}).get("displayName") or c.get("publisher") or "Yahoo Finance"
            if not (title and url and when):
                continue   # no source or no timestamp -> not recorded
            ts = (datetime.fromtimestamp(when, timezone.utc) if isinstance(when, (int, float))
                  else pd.Timestamp(when).tz_convert("UTC").to_pydatetime())
            out.append({"title": title, "url": url, "publisher": publisher, "ts": ts})
        return out
