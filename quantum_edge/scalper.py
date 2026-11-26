"""Short-term trading ("scalper"): many quick positions on 5-minute bars.

OFF by default. It exists because the owner explicitly asked for 30-100 trades a day with
large positions. It is NOT a validated method: before the third run, 1,974 variants of
short-term techniques (reversion, momentum bursts, breakouts, passive limit entries, trend
and rotation systems) were back-tested on a month of 5-minute data with costs, and none
was profitable. The expected result is a loss of roughly the trading costs; the daily loss
limit of the Risk Manager stops it for the day.

What it does each cycle:
  1. refreshes 5-minute candles for a few instruments (staggered, real data only);
  2. on every newly completed bar, looks for three set-ups (dip, burst, breakout);
  3. re-tests each set-up on that instrument's own recent bars with the live exit rules
     and ranks the candidates by that test and by the set-up's live record;
  4. opens the best ones through the Risk Manager, each with a stop, a target and a time
     limit, while respecting the hourly pace, the position cap and a per-instrument cool-down.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select

from .broker import BrokerError
from .db import Position
from .instruments import UNIVERSE, is_market_open
from .risk import Proposal

TF = "5m"
BARS = 600
PLAYS = ("dip", "burst", "breakout")


def _roll(x: np.ndarray, n: int, how: str) -> np.ndarray:
    return getattr(pd.Series(x).rolling(n), how)().to_numpy()


def signals(o, h, l, c, v, level: int = 0) -> dict[str, np.ndarray]:
    """Set-up signals (+1 long, -1 short, 0 none) for every bar. `level` 0 is the strict
    definition; 1 and 2 loosen the thresholds when the trading pace is behind its target."""
    level = max(0, min(int(level), 2))
    prev = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    tr[0] = h[0] - l[0]
    atr = _roll(tr, 14, "mean")
    m20, s20 = _roll(c, 20, "mean"), _roll(c, 20, "std")
    z = (c - m20) / np.where(s20 > 0, s20, np.nan)
    e50 = pd.Series(c).ewm(span=50).mean().to_numpy()
    e200 = pd.Series(c).ewm(span=200).mean().to_numpy()
    r3 = c - np.roll(c, 3)
    r3[:3] = 0.0
    vm = _roll(v, 48, "mean")
    vs = np.where(vm > 0, v / np.where(vm > 0, vm, 1.0), 1.0)      # no volume data -> neutral

    kz = 2.5 - 0.5 * level
    dip = np.where(z <= -kz, 1, np.where(z >= kz, -1, 0))
    if level == 0:                                  # strict: only buy dips in an up-trend, sell spikes in a down-trend
        dip = np.where((dip == 1) & (c > e200), 1, np.where((dip == -1) & (c < e200), -1, 0))
    kb, kv = 3.0 - 0.75 * level, 2.0 - 0.5 * level
    burst = np.where((r3 >= kb * atr) & (vs >= kv), 1, np.where((r3 <= -kb * atr) & (vs >= kv), -1, 0))
    n = (72, 48, 24)[level]
    hh, ll = np.roll(_roll(h, n, "max"), 1), np.roll(_roll(l, n, "min"), 1)
    brk = np.where(c > hh, 1, np.where(c < ll, -1, 0))
    if level < 2:
        brk = np.where((brk == 1) & (e50 > e200), 1, np.where((brk == -1) & (e50 < e200), -1, 0))
    out = {"dip": dip, "burst": burst, "breakout": brk}
    for k in out:
        out[k] = np.where(np.isfinite(atr) & np.isfinite(z), out[k], 0)
        out[k][:205] = 0                            # indicators are not warmed up before this
    return out


def quick_test(o, h, l, c, sig, tp: float, sl: float, hold: int, cost: float) -> tuple[int, float]:
    """Replay a set-up on past bars with the live exit rules: entry at the next bar's open,
    stop checked before target inside a bar, time exit at the close. Returns (trades, mean net)."""
    n, i, rets = len(c), 205, []
    while i < n - 1:
        s = int(sig[i])
        if s == 0:
            i += 1
            continue
        e, j, end, r = o[i + 1], i + 1, min(n - 1, i + hold), None
        while j <= end:
            if (s == 1 and l[j] <= e * (1 - sl)) or (s == -1 and h[j] >= e * (1 + sl)):
                r = -sl
                break
            if (s == 1 and h[j] >= e * (1 + tp)) or (s == -1 and l[j] <= e * (1 - tp)):
                r = tp
                break
            j += 1
        if r is None:
            j, r = end, s * (c[end] / e - 1)
        rets.append(r - cost)
        i = j + 1
    return len(rets), (float(np.mean(rets)) if rets else 0.0)


class Scalper:
    NAME = "scalp:"

    def __init__(self, engine):
        self.eng = engine
        self._seen: dict[str, datetime] = {}                 # last completed bar acted on, per instrument
        self._tests: dict[tuple, tuple] = {}                 # (symbol, play, level) -> (monotonic, trades, mean net)
        self._cursor = 0
        self.last_note = ""

    # --- records ----------------------------------------------------------------------
    def _positions(self, since: datetime) -> list[Position]:
        with self.eng.db.session() as s:
            return list(s.scalars(select(Position).where(
                Position.book == "live", Position.strategy_name.like(self.NAME + "%"),
                Position.opened_at >= since)))

    def record(self, now: datetime | None = None) -> dict:
        """Live record of the scalper since midnight UTC, per set-up and in total."""
        s, now = self.eng.s, now or self.eng.now()
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = self._positions(day)
        closed = [p for p in today if p.status == "closed"]
        plays = {}
        for p in closed:
            d = plays.setdefault(p.strategy_name[len(self.NAME):], {"trades": 0, "wins": 0, "net_eur": 0.0})
            d["trades"] += 1
            d["wins"] += p.realized_pnl_eur > 0
            d["net_eur"] = round(d["net_eur"] + p.realized_pnl_eur, 2)
        return {"enabled": bool(s.scalp_enabled), "target_per_day": s.scalp_trades_per_day,
                "max_per_day": s.scalp_max_trades_per_day, "opened_today": len(today),
                "closed_today": len(closed), "wins_today": sum(1 for p in closed if p.realized_pnl_eur > 0),
                "net_today_eur": round(sum(p.realized_pnl_eur for p in closed), 2),
                "open_now": sum(1 for p in today if p.status == "open"), "by_setup": plays,
                "note": self.last_note}

    # --- one cycle --------------------------------------------------------------------
    def step(self, now: datetime):
        eng, s = self.eng, self.eng.s
        if not s.scalp_enabled or eng.state.get("status") != "running" or eng.state.get("flatten"):
            return
        universe = [i for i in UNIVERSE if i.tradable and i.asset_class in s.scalp_classes
                    and is_market_open(i, now) and eng.hub.is_fresh(i.symbol, now)]
        if not universe:
            self.last_note = "no instrument with a fresh price"
            return
        self._refresh(universe)

        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        recent = self._positions(min(day, now - timedelta(hours=1)))
        today = [p for p in recent if p.opened_at >= day]
        last_hour = sum(1 for p in recent if p.opened_at >= now - timedelta(hours=1))
        open_now = [p for p in recent if p.status == "open"]
        per_hour = s.scalp_trades_per_day / 24.0
        hour_cap = math.ceil(s.scalp_max_trades_per_day / 24.0)
        if len(today) >= s.scalp_max_trades_per_day:
            self.last_note = f"daily maximum of {s.scalp_max_trades_per_day} trades reached"
            return
        if last_hour >= hour_cap or len(open_now) >= s.scalp_max_positions:
            self.last_note = f"waiting: {last_hour} opened in the last hour, {len(open_now)} open"
            return
        level = 2 if last_hour < 0.5 * per_hour else (1 if last_hour < per_hour else 0)

        held = {p.instrument for p in eng.broker.open_positions("live")}
        cool = now - timedelta(minutes=s.scalp_cooldown_minutes)
        resting, losers = set(), {}
        for p in today:
            if p.status == "closed":
                if p.closed_at and p.closed_at >= cool:
                    resting.add(p.instrument)
                d = losers.setdefault(p.instrument, [0, 0.0])
                d[0] += 1
                d[1] += p.realized_pnl_eur
        benched = {sym for sym, (n, net) in losers.items() if n >= 3 and net < 0}     # it keeps losing: leave it
        winners = {sym: net for sym, (n, net) in losers.items() if net > 0}           # it pays: size up
        setup_live = {k: v["net_eur"] / v["trades"] for k, v in self.record(now)["by_setup"].items() if v["trades"] >= 5}

        cands = []
        for inst in universe:
            if inst.symbol in held or inst.symbol in resting or inst.symbol in benched:
                continue
            df = eng.hub.cached_candles(inst, TF)
            if df is None or len(df) < 260:
                continue
            bar_ts = df.index[-1].to_pydatetime()
            if self._seen.get(inst.symbol) == bar_ts or (now - bar_ts).total_seconds() > 2.5 * 300:
                continue                              # bar already acted on, or the data has a gap
            self._seen[inst.symbol] = bar_ts
            o, h, l, c, v = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close", "volume"))
            cost = 2 * s.cost_per_side(inst.asset_class, inst.quote_ccy)
            hold = max(1, int(s.scalp_hold_minutes // 5))
            sig = signals(o, h, l, c, v, level)
            for play in PLAYS:
                side = int(sig[play][-1])
                if side == 0:
                    continue
                key = (inst.symbol, play, level)
                hit = self._tests.get(key)
                if hit is None or time.monotonic() - hit[0] > 1800:
                    n, mean = quick_test(o, h, l, c, sig[play], s.scalp_tp_pct, s.scalp_sl_pct, hold, cost)
                    hit = self._tests[key] = (time.monotonic(), n, mean)
                tested = hit[2] if hit[1] >= 5 else -cost          # too few past cases: assume it only pays the costs
                live = setup_live.get(play, 0.0) / max(1.0, s.initial_capital * s.max_position_pct)
                turnover = float(v[-1] * c[-1]) if np.nansum(v) > 0 else None
                bonus = 0.002 if winners.get(inst.symbol, 0.0) > 0 else 0.0   # prefer what is paying today
                cands.append((tested + live + bonus, tested, hit[1], inst, side, play, turnover))
        if not cands:
            self.last_note = f"no set-up on the latest bars (level {level})"
            return
        cands.sort(key=lambda x: -x[0])
        room = min(s.scalp_max_positions - len(open_now), hour_cap - last_hour,
                   s.scalp_max_trades_per_day - len(today), max(1, len(cands) // 2 if len(cands) > 3 else len(cands)))
        opened, taken = 0, set()
        for score, tested, n, inst, side, play, turnover in cands:
            if opened >= room:
                break
            if inst.symbol in taken:
                continue
            winning = setup_live.get(play, 0.0) > 0 or winners.get(inst.symbol, 0.0) > 0
            weight = s.scalp_weight_best if ((tested > 0 and n >= 5) or winning) else s.scalp_weight
            depth = eng.book_depth(inst, side)                     # network, outside the lock
            with eng._lock:
                if eng.state.get("status") != "running":
                    return
                q = eng.hub.quote(inst.symbol)
                if q is None:
                    continue
                verdict = eng.risk.evaluate(Proposal(
                    inst=inst, side=side, strategy_id=None, strategy_name=self.NAME + play, book="live",
                    stop_dist_pct=s.scalp_sl_pct, weight=weight, expected_trade_pct=tested,
                    bar_turnover=turnover, book_depth=depth, consensus=0.0, exploratory=True), eng.state, now)
                if not verdict.approved:
                    self.last_note = f"{inst.symbol}: {verdict.reason}"
                    continue
                try:
                    pos = eng.broker.open(inst, side, verdict.notional_eur, "live", strategy_name=self.NAME + play,
                                          stop_price=q.price * (1 - side * s.scalp_sl_pct),
                                          take_profit=q.price * (1 + side * s.scalp_tp_pct),
                                          expires_at=now + timedelta(minutes=s.scalp_hold_minutes), now=now)
                except BrokerError as e:
                    eng.incident("warning", "execution", f"scalp {inst.symbol}: {e}")
                    continue
                eng.db.incident("info", "execution",
                                f"opened {'long' if side == 1 else 'short'} {inst.symbol} €{pos.entry_notional_eur:.2f} "
                                f"@ {pos.entry_price:.6g} (scalp:{play}; recent test {tested:+.2%} over {n} cases; "
                                f"not a validated strategy)")
            opened += 1
            taken.add(inst.symbol)
        self.last_note = f"{opened} opened from {len(cands)} set-ups (level {level})"

    def _refresh(self, universe):
        """Refresh the 5-minute candles of a few instruments per cycle so one slow venue never
        delays the stop checks: every instrument is refreshed about once per bar."""
        eng, s = self.eng, self.eng.s
        crypto = [i for i in universe if i.provider == "ccxt"]
        other = [i for i in universe if i.provider != "ccxt"]
        if other:
            for e in eng.hub.prefetch(other, TF, max_age=240.0):
                eng.incident("warning", "data", e, every=900)
        if not crypto:
            return
        batch = [crypto[(self._cursor + k) % len(crypto)] for k in range(min(s.scalp_refresh_per_cycle, len(crypto)))]
        self._cursor = (self._cursor + len(batch)) % len(crypto)
        for inst in batch:
            try:
                eng.hub.candles(inst, TF, bars=BARS, max_age=200.0)
            except Exception as e:
                eng.incident("warning", "data", f"{inst.symbol} 5m candles: {type(e).__name__}: {e}"[:200], every=900)
