"""Sources de données OHLCV, toutes gratuites.

* YahooSource     : yfinance (gratuit, sans clé). Journalier sur 10+ ans ; intraday
                    limité par Yahoo (5m/15m : 60 jours, 1h : 730 jours).
* EtoroSource     : bougies de l'API publique eToro (gratuite avec un compte).
* CsvSource       : fichiers data/csv/<SYMBOLE>_<tf>.csv
* SyntheticSource : marché FICTIF pour les tests hors ligne. Ses résultats
                    n'ont AUCUNE valeur et sont étiquetés "SIMULATED".
"""
from __future__ import annotations

import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

COLS = ["open", "high", "low", "close", "volume"]
TIMEFRAMES = ("5m", "15m", "1h", "4h", "1d")


def normalize(df: pd.DataFrame, daily: bool = True) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    idx = pd.to_datetime(df.index, utc=True).tz_convert(None)
    df.index = idx.normalize() if daily else idx
    if "volume" not in df:
        df["volume"] = 0.0
    df = df[COLS].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.dropna(subset=["close"])


class DataSource:
    name = "base"
    simulated = False

    def daily(self, symbol: str, years: int) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError

    def intraday(self, symbol: str, tf: str) -> pd.DataFrame | None:
        return None

    def load_daily(self, symbols, years: int, log=print) -> dict:
        out = {}
        for s in symbols:
            for attempt in range(3):
                try:
                    df = self.daily(s, years)
                    if len(df) >= 300:
                        out[s] = df
                    else:
                        log(f"[data] {s}: historique trop court ({len(df)} barres), ignoré")
                    break
                except Exception as e:
                    if attempt == 2:
                        log(f"[data] {s}: indisponible ({type(e).__name__}: {e})")
                    else:
                        time.sleep(1.5 * (attempt + 1))
        return out


class YahooSource(DataSource):
    name = "yahoo"
    _intervals = {"5m": ("5m", "59d"), "15m": ("15m", "59d"), "1h": ("60m", "729d")}

    def daily(self, symbol, years):
        import yfinance as yf

        df = yf.download(symbol, period=f"{years}y", interval="1d", auto_adjust=True,
                         progress=False, threads=False)
        return normalize(df)

    def intraday(self, symbol, tf):
        import yfinance as yf

        if tf == "4h":
            h = self.intraday(symbol, "1h")
            return resample(h, "4h") if h is not None else None
        if tf == "1d":
            return self.daily(symbol, 2)
        interval, period = self._intervals[tf]
        df = yf.download(symbol, period=period, interval=interval, auto_adjust=True,
                         progress=False, threads=False)
        return normalize(df, daily=False) if len(df) else None


class EtoroSource(DataSource):
    name = "etoro"
    TF = {"5m": "FiveMinutes", "15m": "FifteenMinutes", "1h": "OneHour", "4h": "FourHours", "1d": "OneDay"}

    def __init__(self, client):
        self.client = client

    def daily(self, symbol, years):
        return normalize(self.client.candles(symbol, "OneDay", min(1000, years * 252)))

    def intraday(self, symbol, tf):
        if tf == "1d":
            return self.daily(symbol, 2)
        return normalize(self.client.candles(symbol, self.TF[tf], 500), daily=False)


class CsvSource(DataSource):
    name = "csv"

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def daily(self, symbol, years):
        return normalize(pd.read_csv(self.folder / f"{symbol}_1d.csv", index_col=0))

    def intraday(self, symbol, tf):
        p = self.folder / f"{symbol}_{tf}.csv"
        return normalize(pd.read_csv(p, index_col=0), daily=False) if p.exists() else None


class SyntheticSource(DataSource):
    name = "synthetic"
    simulated = True

    def __init__(self, seed: int = 7, end: str | None = None):
        self.seed = seed
        self.end = pd.Timestamp(end) if end else pd.Timestamp.now().normalize()

    def _rng(self, symbol):
        return np.random.default_rng(zlib.crc32(f"{symbol}-{self.seed}".encode()))

    def daily(self, symbol, years):
        rng = self._rng(symbol)
        n = years * 252
        vol = rng.uniform(0.010, 0.022)
        drift = np.zeros(n)
        regime, left = 0, 0
        for i in range(n):
            if left == 0:
                regime = rng.choice([-1, 0, 1], p=[0.25, 0.35, 0.40])
                left = int(rng.integers(20, 120))
            drift[i] = regime * vol * 0.10
            left -= 1
        ret = drift + vol * rng.standard_t(4, n) / np.sqrt(2)
        close = 100 * np.exp(np.cumsum(ret))
        hl = np.abs(rng.normal(0, vol * 0.6, n)) * close
        open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, vol * 0.2, n))
        high = np.maximum(open_, close) + hl
        low = np.minimum(open_, close) - hl
        volume = rng.lognormal(15, 0.4, n)
        idx = pd.bdate_range(end=self.end, periods=n)
        return normalize(pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                                       "volume": volume}, index=idx))

    def intraday(self, symbol, tf):
        d = self.daily(symbol, 1).iloc[-40:]
        rng = self._rng(symbol + tf)
        step = {"5m": "5min", "15m": "15min", "1h": "60min", "4h": "60min"}[tf]
        rows = []
        for day, r in d.iterrows():
            t = pd.date_range(day + pd.Timedelta(hours=13, minutes=30), day + pd.Timedelta(hours=19, minutes=55),
                              freq=step)
            path = np.linspace(r["open"], r["close"], len(t)) * (1 + rng.normal(0, 0.001, len(t)))
            for ts, px in zip(t, path):
                rows.append((ts, px, px * 1.001, px * 0.999, px, 1e4))
        df = pd.DataFrame(rows, columns=["date"] + COLS).set_index("date")
        df = normalize(df, daily=False)
        return resample(df, "4h") if tf == "4h" else df


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["close"])


def make_source(name: str, settings, client=None) -> DataSource:
    name = name.lower()
    if name == "yahoo":
        return YahooSource()
    if name == "etoro":
        return EtoroSource(client)
    if name == "csv":
        return CsvSource(settings.paths["data"] / "csv")
    if name == "synthetic":
        return SyntheticSource()
    raise ValueError(f"source inconnue : {name}")
