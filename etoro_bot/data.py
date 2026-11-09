"""Sources de données (bougies journalières OHLCV).

* EtoroData    : bougies de l'API publique eToro (utilisée en mode démo).
* YahooData    : yfinance, pratique pour les backtests sur ta machine.
* CsvData      : fichiers data/<SYMBOLE>.csv (date,open,high,low,close,volume).
* SyntheticData: marché fictif pour tester le code sans connexion.
"""
from __future__ import annotations

import os
import zlib

import numpy as np
import pandas as pd

COLS = ["open", "high", "low", "close", "volume"]


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    idx = pd.to_datetime(df.index, utc=True).tz_convert(None).normalize()
    df.index = idx
    if "volume" not in df:
        df["volume"] = 0.0
    df = df[COLS].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.dropna(subset=["close"])


class DataSource:
    def history(self, symbol: str, bars: int) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError

    def load(self, symbols, bars: int) -> dict:
        out = {}
        for s in symbols:
            try:
                df = self.history(s, bars)
                if len(df) >= 260:
                    out[s] = df
                else:
                    print(f"[data] {s}: historique trop court ({len(df)} barres), ignoré")
            except Exception as e:  # une donnée manquante ne doit pas tuer le bot
                print(f"[data] {s}: erreur {e}")
        return out


class EtoroData(DataSource):
    def __init__(self, client):
        self.client = client

    def history(self, symbol, bars):
        return normalize(self.client.candles(symbol, bars))


class YahooData(DataSource):
    MAP = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"}

    def history(self, symbol, bars):
        import yfinance as yf

        t = self.MAP.get(symbol, symbol)
        years = max(2, int(np.ceil(bars / 250)) + 1)
        df = yf.download(t, period=f"{years}y", interval="1d", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return normalize(df).iloc[-bars:]


class CsvData(DataSource):
    def __init__(self, folder="data"):
        self.folder = folder

    def history(self, symbol, bars):
        df = pd.read_csv(os.path.join(self.folder, f"{symbol}.csv"), index_col=0)
        return normalize(df).iloc[-bars:]


class SyntheticData(DataSource):
    """Marché fictif avec régimes de tendance / range et chocs. Sert UNIQUEMENT à
    vérifier que le code fonctionne : les résultats n'ont aucune valeur prédictive."""

    def __init__(self, seed: int = 7):
        self.seed = seed

    def history(self, symbol, bars):
        rng = np.random.default_rng(zlib.crc32(f"{symbol}-{self.seed}".encode()))
        n = bars
        vol = 0.035 if symbol in ("BTC", "ETH") else rng.uniform(0.010, 0.025)
        drift = np.zeros(n)
        regime, left = 0, 0
        for i in range(n):
            if left == 0:
                regime = rng.choice([-1, 0, 1], p=[0.25, 0.35, 0.40])
                left = rng.integers(20, 120)
            drift[i] = regime * vol * 0.12
            left -= 1
        ret = drift + vol * rng.standard_t(4, n) / np.sqrt(2)
        for i in range(1, n):                      # légère persistance (momentum)
            ret[i] += 0.05 * ret[i - 1]
        close = 100 * np.exp(np.cumsum(ret))
        rng_hl = np.abs(rng.normal(0, vol * 0.6, n)) * close
        open_ = np.r_[close[0], close[:-1]]
        high = np.maximum(open_, close) + rng_hl
        low = np.minimum(open_, close) - rng_hl
        volume = rng.lognormal(15, 0.4, n) * (1 + 3 * np.abs(ret) / vol)
        idx = pd.bdate_range(end=pd.Timestamp("2026-11-06"), periods=n)
        return normalize(pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx
        ))


def make_source(name: str, client=None) -> DataSource:
    name = name.lower()
    if name == "etoro":
        return EtoroData(client)
    if name == "yahoo":
        return YahooData()
    if name == "csv":
        return CsvData()
    if name == "synthetic":
        return SyntheticData()
    raise ValueError(f"source de données inconnue : {name}")
