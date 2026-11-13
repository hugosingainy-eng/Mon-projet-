"""Twenty strategy families. Each family maps (market data, parameters) to four boolean arrays:
long entry, short entry, long exit, short exit — evaluated at the CLOSE of each bar.
The backtester and the live engine both act on the NEXT bar, so there is no look-ahead.

The same functions drive research and live trading: what is validated is what is traded."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ti


class Data:
    """OHLCV arrays plus an indicator cache (indicators are recomputed once per dataset)."""

    def __init__(self, df: pd.DataFrame, bench: pd.Series | None = None):
        self.ts = df.index
        self.o, self.h, self.l, self.c, self.v = (df[k].to_numpy(dtype=float) for k in
                                                  ("open", "high", "low", "close", "volume"))
        self.n = len(df)
        self.has_volume = bool(np.nansum(self.v) > 0)
        self.bench = None
        if bench is not None:
            b = bench.reindex(df.index, method="ffill").to_numpy(dtype=float)
            if np.isfinite(b).sum() > 0.8 * self.n:
                self.bench = b
        self._cache: dict = {}

    def ind(self, name: str, *args):
        key = (name,) + args
        if key not in self._cache:
            self._cache[key] = _IND[name](self, *args)
        return self._cache[key]


_IND = {
    "sma": lambda d, n: ti.sma(d.c, n),
    "ema": lambda d, n: ti.ema(d.c, n),
    "rsi": lambda d, n: ti.rsi(d.c, n),
    "atr": lambda d, n: ti.atr(d.h, d.l, d.c, n),
    "adx": lambda d, n: ti.adx(d.h, d.l, d.c, n),
    "roc": lambda d, n: ti.roc(d.c, n),
    "macd": lambda d, f, s, g: ti.macd(d.c, f, s, g),
    "bb": lambda d, n, k: ti.bollinger(d.c, n, k),
    "vwap": lambda d, n: ti.rolling_vwap(d.h, d.l, d.c, d.v, n),
    "don": lambda d, n: ti.donchian(d.h, d.l, n),
    "hh": lambda d, n: ti.shift(ti.rolling_max(d.c, n), 1),
    "ll": lambda d, n: ti.shift(ti.rolling_min(d.c, n), 1),
    "sr": lambda d, n: ti.support_resistance(d.h, d.l, n),
    "vol_sma": lambda d, n: ti.sma(d.v, n),
    "bench_roc": lambda d, n: ti.roc(d.bench, n),
    "ratio_z": lambda d, n: ti.zscore(np.log(d.c / d.bench), n),
    "atr_pct_med": lambda d, n: pd.Series(ti.atr(d.h, d.l, d.c, 14) / d.c).rolling(n, min_periods=n // 2).median().to_numpy(),
    "bbw_q": lambda d, n, k, look, q: _bbw_quantile(d, n, k, look, q),
}


def _bbw_quantile(d, n, k, look, q):
    lo, mid, up = d.ind("bb", n, k)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = (up - lo) / mid
    thr = pd.Series(w).rolling(look, min_periods=look // 2).quantile(q).to_numpy()
    return w, thr


def xup(a, b):
    """a crosses above b on this bar."""
    a = np.asarray(a, float)
    b = np.broadcast_to(np.asarray(b, float), a.shape)
    with np.errstate(invalid="ignore"):
        return (a > b) & (ti.shift(a) <= ti.shift(b))


def xdn(a, b):
    a = np.asarray(a, float)
    b = np.broadcast_to(np.asarray(b, float), a.shape)
    with np.errstate(invalid="ignore"):
        return (a < b) & (ti.shift(a) >= ti.shift(b))


def _gt(a, b):
    with np.errstate(invalid="ignore"):
        return np.asarray(a, float) > b


def _lt(a, b):
    with np.errstate(invalid="ignore"):
        return np.asarray(a, float) < b


def _vol_confirm(d: Data, mult: float):
    if not d.has_volume or mult <= 1.0:
        return np.ones(d.n, dtype=bool)
    return _gt(d.v, mult * d.ind("vol_sma", 20))


# ---------------------------------------------------------------------------------------
# families
# ---------------------------------------------------------------------------------------
def ma_cross(d, p):
    f, s = d.ind(p["kind"], p["fast"]), d.ind(p["kind"], p["slow"])
    up, dn = xup(f, s), xdn(f, s)
    return up, dn, dn, up


def _ma_trend(kind):
    def fn(d, p):
        m = d.ind(kind, p["n"])
        rising = _gt(m, ti.shift(m, p["slope"]))
        falling = _lt(m, ti.shift(m, p["slope"]))
        return xup(d.c, m) & rising, xdn(d.c, m) & falling, _lt(d.c, m), _gt(d.c, m)
    return fn


def rsi_reversion(d, p):
    r = d.ind("rsi", p["n"])
    return xup(r, p["lo"]), xdn(r, p["hi"]), _gt(r, p["exit"]), _lt(r, 100 - p["exit"])


def macd_momentum(d, p):
    line, sig, _ = d.ind("macd", p["fast"], p["slow"], p["sig"])
    up, dn = xup(line, sig), xdn(line, sig)
    if p["zero"]:
        return up & _gt(line, 0), dn & _lt(line, 0), dn, up
    return up, dn, dn, up


def bb_breakout(d, p):
    lo, mid, up = d.ind("bb", p["n"], p["k"])
    return xup(d.c, up), xdn(d.c, lo), _lt(d.c, mid), _gt(d.c, mid)


def bb_reversion(d, p):
    lo, mid, up = d.ind("bb", p["n"], p["k"])
    return xup(d.c, lo), xdn(d.c, up), _gt(d.c, mid), _lt(d.c, mid)


def vwap(d, p):
    with np.errstate(divide="ignore", invalid="ignore"):
        dev = (d.c - d.ind("vwap", p["n"])) / d.ind("atr", 14)
    k = p["dev"]
    if p["mode"] == "revert":
        return xup(dev, -k), xdn(dev, k), _gt(dev, 0), _lt(dev, 0)
    return xup(dev, k), xdn(dev, -k), _lt(dev, 0), _gt(dev, 0)


def momentum_cont(d, p):
    r = d.ind("roc", p["n"])
    vc = _vol_confirm(d, p["volx"])
    return xup(r, p["thr"]) & vc, xdn(r, -p["thr"]) & vc, _lt(r, 0), _gt(r, 0)


def price_breakout(d, p):
    hh, ll = d.ind("hh", p["n"]), d.ind("ll", p["n"])
    mid = d.ind("sma", max(5, p["n"] // 2))
    vc = _vol_confirm(d, p["volx"])
    return xup(d.c, hh) & vc, xdn(d.c, ll) & vc, _lt(d.c, mid), _gt(d.c, mid)


def donchian(d, p):
    lo_in, hi_in = d.ind("don", p["n_in"])
    lo_out, hi_out = d.ind("don", p["n_out"])
    return xup(d.c, hi_in), xdn(d.c, lo_in), _lt(d.c, lo_out), _gt(d.c, hi_out)


def atr_breakout(d, p):
    mid, a = d.ind("ema", p["n"]), d.ind("atr", 14)
    return xup(d.c, mid + p["k"] * a), xdn(d.c, mid - p["k"] * a), _lt(d.c, mid), _gt(d.c, mid)


def trend_pullback(d, p):
    e = d.ind("ema", p["trend"])
    r = d.ind("rsi", p["rsi_n"])
    up = _gt(d.c, e) & _gt(e, ti.shift(e, 5))
    dn = _lt(d.c, e) & _lt(e, ti.shift(e, 5))
    return up & xup(r, p["lvl"]), dn & xdn(r, 100 - p["lvl"]), _gt(r, 75), _lt(r, 25)


def support_resistance(d, p):
    sup, res = d.ind("sr", p["n"])
    tol = p["tol"] * d.ind("atr", 14)
    if p["mode"] == "bounce":
        le = _lt(d.l, sup + tol) & _gt(d.c, sup) & (d.c > d.o)
        se = _gt(d.h, res - tol) & _lt(d.c, res) & (d.c < d.o)
        return le, se, _gt(d.h, res), _lt(d.l, sup)
    return xup(d.c, res + tol), xdn(d.c, sup - tol), _lt(d.c, sup), _gt(d.c, res)


def mtf_confirm(d, p):
    m = p["mult"]
    blocks = d.c[m - 1::m]                       # closes of completed higher-timeframe bars
    e = ti.ema(blocks, p["htf_n"])
    with np.errstate(invalid="ignore"):
        up_b = np.where(np.isfinite(e), blocks > e, False)
        dn_b = np.where(np.isfinite(e), blocks < e, False)
    last_block = (np.arange(d.n) + 1) // m - 1   # last block fully closed at bar t
    ok = last_block >= 0
    htf_up = np.where(ok, up_b[np.clip(last_block, 0, len(blocks) - 1)], False)
    htf_dn = np.where(ok, dn_b[np.clip(last_block, 0, len(blocks) - 1)], False)
    f, s = d.ind("ema", p["fast"]), d.ind("ema", p["slow"])
    up, dn = xup(f, s), xdn(f, s)
    return up & htf_up, dn & htf_dn, dn | ~htf_up, up | ~htf_dn


def relative_strength(d, p):
    own = d.ind("roc", p["n"])
    rs = own - d.ind("bench_roc", p["n"])
    return xup(rs, p["thr"]) & _gt(own, 0), xdn(rs, -p["thr"]) & _lt(own, 0), _lt(rs, 0), _gt(rs, 0)


def pairs_ratio(d, p):
    """Single-leg statistical arbitrage on the log price ratio versus the benchmark instrument.
    (Only this leg is traded; a two-leg hedge is not simulated.)"""
    z = d.ind("ratio_z", p["n"])
    return xdn(z, -p["entry"]), xup(z, p["entry"]), _gt(z, -p["exit"]), _lt(z, p["exit"])


def volatility_squeeze(d, p):
    lo, mid, up = d.ind("bb", p["n"], 2.0)
    w, thr = d.ind("bbw_q", p["n"], 2.0, p["look"], p["pct"])
    with np.errstate(invalid="ignore"):
        sq = pd.Series((w <= thr).astype(float)).rolling(5, min_periods=1).max().to_numpy() > 0
    sq = np.roll(sq, 1)
    sq[0] = False
    return sq & xup(d.c, up), sq & xdn(d.c, lo), _lt(d.c, mid), _gt(d.c, mid)


def regime_switch(d, p):
    trending = _gt(d.ind("adx", p["adx_n"]), p["adx_thr"])
    f, s = d.ind("ema", p["fast"]), d.ind("ema", p["slow"])
    r = d.ind("rsi", 14)
    up, dn = xup(f, s), xdn(f, s)
    le = (trending & up) | (~trending & xup(r, p["rsi_lo"]))
    se = (trending & dn) | (~trending & xdn(r, 100 - p["rsi_lo"]))
    return le, se, dn | (~trending & _gt(r, 60)), up | (~trending & _lt(r, 40))


def ensemble(d, p):
    """Majority vote of five independent components."""
    f, s = d.ind("ema", p["fast"]), d.ind("ema", p["slow"])
    _, _, hist = d.ind("macd", 12, 26, 9)
    r = d.ind("rsi", 14)
    lo, hi = d.ind("don", p["don"])
    _, mid, _ = d.ind("bb", 20, 2.0)
    bull = (_gt(f, s).astype(int) + _gt(hist, 0) + _gt(r, 50) + _gt(d.c, (lo + hi) / 2) + _gt(d.c, mid))
    bear = (_lt(f, s).astype(int) + _lt(hist, 0) + _lt(r, 50) + _lt(d.c, (lo + hi) / 2) + _lt(d.c, mid))
    need = p["need"]
    return xup(bull, need - 0.5), xup(bear, need - 0.5), bull < need - 1, bear < need - 1


FAMILIES: dict[str, tuple] = {
    "ma_cross": (ma_cross, {"fast": [5, 8, 10, 13, 20], "slow": [30, 50, 100, 200], "kind": ["sma", "ema"]}),
    "ema_trend": (_ma_trend("ema"), {"n": [20, 50, 100, 200], "slope": [3, 5, 10]}),
    "sma_trend": (_ma_trend("sma"), {"n": [20, 50, 100, 200], "slope": [3, 5, 10]}),
    "rsi_reversion": (rsi_reversion, {"n": [7, 14, 21], "lo": [20, 25, 30], "hi": [70, 75, 80], "exit": [50, 55, 60]}),
    "macd_momentum": (macd_momentum, {"fast": [8, 12], "slow": [21, 26, 35], "sig": [7, 9], "zero": [True, False]}),
    "bb_breakout": (bb_breakout, {"n": [20, 30, 50], "k": [1.5, 2.0, 2.5]}),
    "bb_reversion": (bb_reversion, {"n": [20, 30, 50], "k": [1.5, 2.0, 2.5]}),
    "vwap": (vwap, {"n": [20, 50, 100], "dev": [0.5, 1.0, 1.5, 2.0], "mode": ["revert", "trend"]}),
    "momentum_cont": (momentum_cont, {"n": [10, 20, 50], "thr": [0.01, 0.02, 0.04], "volx": [1.0, 1.5, 2.0]}),
    "price_breakout": (price_breakout, {"n": [20, 50, 100], "volx": [1.0, 1.5, 2.0]}),
    "donchian": (donchian, {"n_in": [20, 40, 55], "n_out": [10, 20]}),
    "atr_breakout": (atr_breakout, {"n": [20, 50], "k": [1.5, 2.0, 2.5, 3.0]}),
    "trend_pullback": (trend_pullback, {"trend": [50, 100, 200], "rsi_n": [3, 5, 7], "lvl": [20, 30, 40]}),
    "support_resistance": (support_resistance, {"n": [5, 10, 20], "tol": [0.25, 0.5, 1.0], "mode": ["bounce", "break"]}),
    "mtf_confirm": (mtf_confirm, {"mult": [4, 8, 16], "htf_n": [20, 50], "fast": [5, 10], "slow": [20, 30]}),
    "relative_strength": (relative_strength, {"n": [20, 50, 100], "thr": [0.01, 0.02, 0.05]}),
    "pairs_ratio": (pairs_ratio, {"n": [50, 100, 200], "entry": [1.5, 2.0, 2.5], "exit": [0.0, 0.5]}),
    "volatility_squeeze": (volatility_squeeze, {"n": [20, 30], "pct": [0.1, 0.2, 0.3], "look": [100, 200]}),
    "regime_switch": (regime_switch, {"adx_n": [14, 20], "adx_thr": [20, 25, 30], "fast": [10, 20], "slow": [50, 100], "rsi_lo": [25, 30]}),
    "ensemble": (ensemble, {"fast": [10, 20], "slow": [50, 100], "need": [3, 4, 5], "don": [20, 55]}),
}
NEEDS_BENCH = {"relative_strength", "pairs_ratio"}

# Trade-management parameters shared by every family (also part of every experiment).
COMMON_SPACE = {
    "stop_atr": [1.0, 1.5, 2.0, 3.0, 4.0],      # stop-loss distance in ATR(14)
    "rr": [0.0, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0],  # take-profit as a multiple of the stop (0 = none)
    "trail": [False, True],                     # trailing stop
    "max_hold": [12, 24, 48, 96, 200],          # bars
    "size": [0.1, 0.25],                        # fraction of equity per trade
    "regime": ["none", "trend", "range"],       # market-regime filter (ADX)
    "vol": ["none", "high", "low"],             # volatility filter (ATR% vs its median)
    "short": [True, False],
}


def space_for(family: str) -> dict[str, list]:
    return {**FAMILIES[family][1], **COMMON_SPACE}


def signals(family: str, d: Data, p: dict):
    """Entry/exit arrays after the common regime / volatility / short filters."""
    le, se, lx, sx = FAMILIES[family][0](d, p)
    le, se, lx, sx = (np.asarray(a, dtype=bool) for a in (le, se, lx, sx))
    filt = np.ones(d.n, dtype=bool)
    if p.get("regime", "none") != "none":
        a = d.ind("adx", 14)
        filt &= _gt(a, 25) if p["regime"] == "trend" else _lt(a, 20)
    if p.get("vol", "none") != "none":
        with np.errstate(divide="ignore", invalid="ignore"):
            ap = d.ind("atr", 14) / d.c
        med = d.ind("atr_pct_med", 200)
        filt &= _gt(ap, med) if p["vol"] == "high" else _lt(ap, med)
    le = le & filt
    se = se & filt if p.get("short", True) else np.zeros(d.n, dtype=bool)
    return le, se, lx, sx
