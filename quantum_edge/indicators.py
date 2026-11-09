"""Indicateurs techniques, tous causaux (aucune donnée future)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()],
                     axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    out = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    return out.fillna(100.0).where(up.notna())


def macd(s: pd.Series, fast=12, slow=26, signal=9) -> pd.DataFrame:
    line = ema(s, fast) - ema(s, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(s: pd.Series, n=20, k=2.0) -> pd.DataFrame:
    m = sma(s, n)
    sd = s.rolling(n, min_periods=n).std()
    return pd.DataFrame({"mid": m, "upper": m + k * sd, "lower": m - k * sd, "width": 2 * k * sd / m})


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = atr(df, n)
    pdi = 100 * pd.Series(plus, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / tr
    mdi = 100 * pd.Series(minus, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP intraday, remis à zéro chaque jour (n'a de sens qu'en intraday)."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    day = df.index.normalize()
    pv = (tp * df["volume"]).groupby(day).cumsum()
    v = df["volume"].groupby(day).cumsum().replace(0, np.nan)
    return pv / v


def support_resistance(df: pd.DataFrame, lookback: int = 60, order: int = 3) -> tuple[float, float]:
    """Plus proches supports/résistances = pivots locaux des `lookback` dernières barres."""
    w = df.iloc[-lookback:]
    hi, lo = w["high"].to_numpy(), w["low"].to_numpy()
    price = float(w["close"].iloc[-1])
    piv_hi = [hi[i] for i in range(order, len(w) - order) if hi[i] == hi[i - order:i + order + 1].max()]
    piv_lo = [lo[i] for i in range(order, len(w) - order) if lo[i] == lo[i - order:i + order + 1].min()]
    res = min([h for h in piv_hi if h > price], default=float("nan"))
    sup = max([l for l in piv_lo if l < price], default=float("nan"))
    return sup, res


def candle_patterns(df: pd.DataFrame) -> dict:
    """Structures de chandeliers simples sur la dernière barre."""
    if len(df) < 2:
        return {}
    o, h, l, c = (df[k].iloc[-1] for k in ("open", "high", "low", "close"))
    po, pc = df["open"].iloc[-2], df["close"].iloc[-2]
    body = abs(c - o)
    rng = max(h - l, 1e-12)
    return {
        "bullish_engulfing": bool(c > o and pc < po and c >= po and o <= pc),
        "bearish_engulfing": bool(c < o and pc > po and o >= pc and c <= po),
        "hammer": bool(body / rng < 0.35 and (min(o, c) - l) / rng > 0.55),
        "shooting_star": bool(body / rng < 0.35 and (h - max(o, c)) / rng > 0.55),
        "strong_close": bool((c - l) / rng > 0.75),
    }


def realized_vol(s: pd.Series, n: int = 20) -> pd.Series:
    return np.log(s).diff().rolling(n, min_periods=n).std()
