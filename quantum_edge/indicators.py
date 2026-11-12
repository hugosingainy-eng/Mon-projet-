"""Technical indicators on numpy arrays. Every function is causal: the value at index t uses
only data up to and including t (no look-ahead)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _s(x) -> pd.Series:
    return pd.Series(np.asarray(x, dtype=float))


def sma(x, n: int) -> np.ndarray:
    return _s(x).rolling(n, min_periods=n).mean().to_numpy()


def ema(x, n: int) -> np.ndarray:
    return _s(x).ewm(span=n, adjust=False, min_periods=n).mean().to_numpy()


def rolling_max(x, n: int) -> np.ndarray:
    return _s(x).rolling(n, min_periods=n).max().to_numpy()


def rolling_min(x, n: int) -> np.ndarray:
    return _s(x).rolling(n, min_periods=n).min().to_numpy()


def rolling_std(x, n: int) -> np.ndarray:
    return _s(x).rolling(n, min_periods=n).std(ddof=0).to_numpy()


def shift(x, k: int = 1) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    if k < len(x):
        out[k:] = x[:len(x) - k]
    return out


def roc(x, n: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return x / shift(x, n) - 1.0


def rsi(close, n: int = 14) -> np.ndarray:
    d = _s(close).diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out[(dn == 0) & up.notna()] = 100.0
    return out.to_numpy()


def macd(close, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = pd.Series(line).ewm(span=signal, adjust=False, min_periods=signal).mean().to_numpy()
    return line, sig, line - sig


def bollinger(close, n: int = 20, k: float = 2.0):
    mid = sma(close, n)
    sd = rolling_std(close, n)
    return mid - k * sd, mid, mid + k * sd


def true_range(high, low, close) -> np.ndarray:
    high, low, close = (np.asarray(a, dtype=float) for a in (high, low, close))
    pc = shift(close, 1)
    tr = np.maximum(high - low, np.maximum(np.abs(high - pc), np.abs(low - pc)))
    tr[0] = high[0] - low[0]
    return tr


def atr(high, low, close, n: int = 14) -> np.ndarray:
    return _s(true_range(high, low, close)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()


def adx(high, low, close, n: int = 14) -> np.ndarray:
    high, low = np.asarray(high, dtype=float), np.asarray(low, dtype=float)
    up = np.diff(high, prepend=high[0])
    dn = -np.diff(low, prepend=low[0])
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(high, low, close, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * _s(plus).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy() / a
        mdi = 100 * _s(minus).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy() / a
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    return _s(dx).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()


def stoch_rsi(close, n: int = 14, k: int = 3) -> np.ndarray:
    r = rsi(close, n)
    lo, hi = rolling_min(r, n), rolling_max(r, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        st = (r - lo) / (hi - lo)
    return _s(st).rolling(k, min_periods=k).mean().to_numpy() * 100


def rolling_vwap(high, low, close, volume, n: int) -> np.ndarray:
    """Volume-weighted average price over the last n bars (falls back to SMA of the typical
    price where the provider reports no volume, e.g. forex)."""
    tp = (np.asarray(high, float) + np.asarray(low, float) + np.asarray(close, float)) / 3
    v = np.asarray(volume, dtype=float)
    pv = _s(tp * v).rolling(n, min_periods=n).sum().to_numpy()
    vv = _s(v).rolling(n, min_periods=n).sum().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        out = pv / vv
    fallback = sma(tp, n)
    return np.where(np.isfinite(out) & (vv > 0), out, fallback)


def donchian(high, low, n: int):
    """Channel of the previous n bars (excludes the current bar)."""
    return shift(rolling_min(low, n), 1), shift(rolling_max(high, n), 1)


def zscore(x, n: int) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return (np.asarray(x, float) - sma(x, n)) / rolling_std(x, n)


def fibonacci_levels(high, low, n: int = 100) -> dict[str, float] | None:
    """Retracement levels of the last n bars' range."""
    h, l = np.asarray(high, float)[-n:], np.asarray(low, float)[-n:]
    if len(h) < 5:
        return None
    hi, lo = float(np.max(h)), float(np.min(l))
    return {str(r): hi - (hi - lo) * r for r in (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)}


def support_resistance(high, low, n: int):
    """Most recent confirmed swing low / swing high (pivot with n bars either side).
    A pivot at bar p is only known at bar p+n, so the series is shifted by n: causal."""
    high, low = _s(high), _s(low)
    w = 2 * n + 1
    is_hi = high.rolling(w, min_periods=w).max().to_numpy() == shift(high.to_numpy(), n)
    is_lo = low.rolling(w, min_periods=w).min().to_numpy() == shift(low.to_numpy(), n)
    res = pd.Series(np.where(is_hi, shift(high.to_numpy(), n), np.nan)).ffill().to_numpy()
    sup = pd.Series(np.where(is_lo, shift(low.to_numpy(), n), np.nan)).ffill().to_numpy()
    return sup, res


def regime(high, low, close, n: int = 14) -> str | None:
    """Coarse market regime of the latest bar."""
    if len(close) < 3 * n + 50:
        return None
    a = adx(high, low, close, n)[-1]
    at = atr(high, low, close, n)
    atr_pct = at / np.asarray(close, float)
    recent = atr_pct[-200:]
    recent = recent[np.isfinite(recent)]
    if not np.isfinite(a) or len(recent) < 20:
        return None
    if atr_pct[-1] > np.quantile(recent, 0.9):
        return "volatile"
    if a >= 25:
        e = ema(close, 50)
        return "trend_up" if close[-1] > e[-1] else "trend_down"
    return "range"


def candle_pattern(o, h, l, c) -> str | None:
    """Pattern on the latest completed candle (uses the previous one for engulfing)."""
    if len(c) < 2:
        return None
    body, rng = abs(c[-1] - o[-1]), h[-1] - l[-1]
    if rng <= 0:
        return None
    upper, lower = h[-1] - max(c[-1], o[-1]), min(c[-1], o[-1]) - l[-1]
    if c[-1] > o[-1] and c[-2] < o[-2] and c[-1] >= o[-2] and o[-1] <= c[-2]:
        return "bullish_engulfing"
    if c[-1] < o[-1] and c[-2] > o[-2] and c[-1] <= o[-2] and o[-1] >= c[-2]:
        return "bearish_engulfing"
    if body / rng < 0.1:
        return "doji"
    if lower > 2 * body and upper < body:
        return "hammer"
    if upper > 2 * body and lower < body:
        return "shooting_star"
    return None
