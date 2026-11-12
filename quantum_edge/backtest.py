"""Event-accurate backtester.

Rules that keep it honest:
* a signal seen at the close of bar t is executed at the OPEN of bar t+1;
* stops/targets are checked on later bars' high/low; if both are hit in one bar the STOP is
  assumed (worst case); a gap through the stop fills at the open (worse than the stop);
* every trade pays the full cost model on both sides (fee + slippage + half-spread + FX)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import indicators as ti
from .strategies import Data, signals


@dataclass
class Trades:
    entry: np.ndarray      # bar index of entry
    exit: np.ndarray       # bar index of exit
    side: np.ndarray       # +1 / -1
    ret: np.ndarray        # net fractional return on traded notional
    gross: np.ndarray      # before costs

    def __len__(self):
        return len(self.ret)


def _first(mask: np.ndarray) -> int:
    i = int(np.argmax(mask)) if mask.size else 0
    return i if mask.size and mask[i] else -1


def simulate(d: Data, le, se, lx, sx, stop_atr: float, rr: float, trail: bool, max_hold: int,
             cost_per_side: float, atr_n: int = 14) -> Trades:
    o, h, l, c, n = d.o, d.h, d.l, d.c, d.n
    atr = d.ind("atr", atr_n)
    sig_idx = np.flatnonzero(le | se)
    ent, ext, sides, rets, gross = [], [], [], [], []
    free_from = 0                      # first bar whose close-signal may open a new trade
    pos = 0
    while pos < len(sig_idx):
        s = int(sig_idx[pos])
        pos += 1
        if s < free_from:
            continue
        e = s + 1
        if e >= n:
            break
        a = atr[s]
        if le[s] and se[s] or not np.isfinite(a) or a <= 0:
            continue
        side = 1 if le[s] else -1
        px = o[e]
        dist = stop_atr * a
        end = min(n, e + max_hold)
        hs, ls = h[e:end], l[e:end]
        if side == 1:
            if trail:
                ref = np.maximum.accumulate(np.concatenate(([px], hs[:-1])))
                stops = ref - dist
            else:
                stops = np.full(end - e, px - dist)
            k_stop = _first(ls <= stops)
            k_tp = _first(hs >= px + rr * dist) if rr > 0 else -1
            xsig = lx
        else:
            if trail:
                ref = np.minimum.accumulate(np.concatenate(([px], ls[:-1])))
                stops = ref + dist
            else:
                stops = np.full(end - e, px + dist)
            k_stop = _first(hs >= stops)
            k_tp = _first(ls <= px - rr * dist) if rr > 0 else -1
            xsig = sx
        # exit signal at close of bar e+j -> exit at open of bar e+j+1
        k_sig = _first(xsig[e:end - 1]) if end - 1 > e else -1
        if k_sig >= 0:
            k_sig += 1
        cands = [(k, r) for k, r in ((k_stop, 0), (k_tp, 1), (k_sig, 2)) if k >= 0]
        if cands:
            k, reason = min(cands)        # earliest bar; on a tie the stop (0) wins
            if reason == 0:
                level = stops[k]
                xp = min(level, o[e + k]) if side == 1 else max(level, o[e + k])
            elif reason == 1:
                xp = px + side * rr * dist
            else:
                xp = o[e + k]
            xi = e + k
        else:
            xi = end - 1
            xp = c[xi]
        g = side * (xp / px - 1.0)
        ent.append(e); ext.append(xi); sides.append(side); gross.append(g)
        rets.append(g - 2 * cost_per_side)
        free_from = xi
    return Trades(np.array(ent, dtype=int), np.array(ext, dtype=int), np.array(sides, dtype=int),
                  np.array(rets, dtype=float), np.array(gross, dtype=float))


def run(family: str, d: Data, params: dict, cost_per_side: float) -> Trades:
    le, se, lx, sx = signals(family, d, params)
    return simulate(d, le, se, lx, sx, params["stop_atr"], params["rr"], params["trail"],
                    params["max_hold"], cost_per_side)


def metrics(tr: Trades, mask: np.ndarray, day_index: np.ndarray, lo: int, hi: int, size: float,
            ann: int) -> dict:
    """Metrics for the trades selected by `mask`, over bars [lo, hi). `day_index` maps each
    bar to an integer day number; Sharpe/Sortino use daily P&L including flat days."""
    r = tr.ret[mask] * size
    out = {"trades": int(len(r)), "ret": 0.0, "dd": 0.0, "sharpe": 0.0, "sortino": 0.0,
           "pf": None, "win": None, "avg": None}
    if hi <= lo:
        return out
    if len(r) == 0:
        return out
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(np.concatenate(([1.0], eq)))[1:]
    out["ret"] = float(eq[-1] - 1.0)
    out["dd"] = float(np.max(1.0 - eq / np.maximum(peak, 1.0)))
    wins, losses = r[r > 0], r[r <= 0]
    out["win"] = float(len(wins) / len(r))
    out["avg"] = float(np.mean(tr.ret[mask]))
    out["pf"] = float(wins.sum() / -losses.sum()) if losses.sum() < 0 else None
    d0, d1 = int(day_index[lo]), int(day_index[hi - 1])
    daily = np.zeros(d1 - d0 + 1)
    np.add.at(daily, np.clip(day_index[tr.exit[mask]] - d0, 0, len(daily) - 1), r)
    if len(daily) > 1:
        sd = daily.std(ddof=1)
        if sd > 0:
            out["sharpe"] = float(daily.mean() / sd * np.sqrt(ann))
        dsd = np.sqrt(np.mean(np.square(np.minimum(daily, 0.0))))
        if dsd > 0:
            out["sortino"] = float(daily.mean() / dsd * np.sqrt(ann))
    return out


def evaluate(tr: Trades, d: Data, size: float, ann: int, train: float, val: float,
             min_train: int, min_oos: int, cost_per_side: float) -> dict:
    """Chronological train / validation / untouched-test evaluation of one backtest."""
    n = d.n
    i1, i2 = int(n * train), int(n * (train + val))
    day = (d.ts.asi8 // (86_400 * 10 ** _unit_pow(d.ts))).astype(np.int64)
    seg = {}
    for name, lo, hi in (("train", 0, i1), ("val", i1, i2), ("test", i2, n)):
        m = (tr.entry >= lo) & (tr.entry < hi)
        seg[name] = metrics(tr, m, day, lo, hi, size, ann)
    full = metrics(tr, np.ones(len(tr), dtype=bool), day, 0, n, size, ann)
    # stability: share of 6 equal chronological slices with positive net P&L
    edges = np.linspace(0, n, 7).astype(int)
    pos = sum(1 for a, b in zip(edges[:-1], edges[1:])
              if tr.ret[(tr.entry >= a) & (tr.entry < b)].sum() > 0)
    stability = pos / 6
    t, v, te = seg["train"], seg["val"], seg["test"]
    if t["trades"] < min_train or v["trades"] < min_oos or te["trades"] < min_oos:
        verdict = "INSUFFICIENT_TRADES"
    elif t["ret"] <= 0 or t["sharpe"] < 0.5:
        verdict = "FAIL_TRAIN"
    elif v["ret"] <= 0 or v["sharpe"] < 1.0:
        verdict = "FAIL_VALIDATION"       # looked good only on the data it was tuned on
    elif te["ret"] <= 0 or te["sharpe"] < 0.5 or stability < 0.5:
        verdict = "FAIL_TEST"
    else:
        verdict = "PASS"
    # robustness score: the WEAKEST out-of-sample Sharpe, scaled by stability — not the best return
    score = min(v["sharpe"], te["sharpe"], t["sharpe"]) * stability if len(tr) else -9.0
    if verdict == "INSUFFICIENT_TRADES":
        score = min(score, 0.0) - 5.0     # too few trades to mean anything: never ranked high
    return {"full": full, "segments": seg, "stability": float(stability), "evaluation": verdict,
            "score": float(max(min(score, 99.0), -99.0)),
            "cost_pct": float(len(tr) * 2 * cost_per_side * size * 100),
            "train_objective": float(t["sharpe"] if t["trades"] >= min_train else -5.0 + t["trades"] / 100)}


def _unit_pow(idx) -> int:
    return {"s": 0, "ms": 3, "us": 6, "ns": 9}.get(getattr(idx, "unit", "ns"), 9)
