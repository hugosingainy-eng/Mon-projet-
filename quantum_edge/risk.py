"""Risk Manager — the final authority. Every proposed trade passes through `evaluate`;
nothing else in the system can open a position, and no agent can override a rejection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .config import Settings
from .db import Database, Decision, utcnow
from .instruments import Instrument, is_market_open


@dataclass
class Proposal:
    inst: Instrument
    side: int                       # +1 long, -1 short
    strategy_id: int | None
    strategy_name: str
    book: str                       # live | shadow
    stop_dist_pct: float            # stop distance as a fraction of price
    weight: float = 1.0             # allocation weight from the performance analyst
    expected_trade_pct: float = 0.0  # out-of-sample average net trade return (fraction)
    bar_turnover: float | None = None   # last bar volume × price in quote currency
    consensus: float = 0.0          # signed agent consensus for this instrument
    book_depth: float | None = None  # resting orders on the side the order hits (quote ccy), from the live book
    exploratory: bool = False       # unvalidated strategy traded on the owner's explicit request


@dataclass
class Verdict:
    approved: bool
    reason: str
    notional_eur: float = 0.0


class RiskManager:
    def __init__(self, settings: Settings, db: Database, hub, broker):
        self.s, self.db, self.hub, self.broker = settings, db, hub, broker
        self.approved = 0
        self.rejected = 0

    def evaluate(self, p: Proposal, state: dict, now: datetime | None = None) -> Verdict:
        v = self._check(p, state, now or utcnow())
        if p.book == "live":
            self.approved += v.approved
            self.rejected += not v.approved
            with self.db.session() as s:
                s.add(Decision(ts=now or utcnow(), instrument=p.inst.symbol,
                               side="long" if p.side == 1 else "short", strategy=p.strategy_name,
                               approved=v.approved, reason=v.reason,
                               notional_eur=v.notional_eur if v.approved else None))
        return v

    def _check(self, p: Proposal, state: dict, now: datetime) -> Verdict:
        s, inst = self.s, p.inst
        no = lambda why: Verdict(False, why)
        # ---- experiment state ---------------------------------------------------------
        if state.get("status") != "running":
            return no(f"experiment is {state.get('status')}")
        if state.get("flatten"):
            return no("portfolio is being flattened")
        # ---- instrument & data quality -----------------------------------------------
        if not inst.tradable:
            return no(f"not tradable: {inst.note}")
        if p.side == -1 and not s.allow_short:
            return no("short selling disabled")
        if not is_market_open(inst, now):
            return no("market closed")
        q = self.hub.quote(inst.symbol)
        if q is None:
            return no("no market data")
        if not self.hub.is_fresh(inst.symbol, now):
            return no(f"stale market data ({q.age(now):.0f}s old)")
        if self.hub.fx_rate(inst.quote_ccy) is None:
            return no(f"no FX rate for {inst.quote_ccy}")
        # ---- liquidity & costs -------------------------------------------------------
        cls = inst.asset_class
        if q.bid and q.ask:
            spread_bps = (q.ask - q.bid) / ((q.ask + q.bid) / 2) * 1e4
            if spread_bps > s.max_spread_bps:
                return no(f"spread {spread_bps:.1f} bps exceeds limit {s.max_spread_bps:.0f} bps")
        fx = self.hub.fx_rate(inst.quote_ccy)[0]
        if p.book_depth is not None:            # real order book: the best liquidity measure we have
            if p.book_depth * fx < s.min_bar_turnover_eur:
                return no(f"insufficient liquidity (order book depth €{p.book_depth * fx:,.0f})")
        elif p.bar_turnover is not None and cls != "forex":
            if p.bar_turnover * fx < s.min_bar_turnover_eur:
                return no(f"insufficient liquidity (last bar turnover €{p.bar_turnover * fx:,.0f})")
        round_trip = 2 * s.cost_per_side(cls, inst.quote_ccy)
        if p.expected_trade_pct <= 0 and not p.exploratory:
            return no("no positive out-of-sample expectancy after costs")
        if not 0 < p.stop_dist_pct < 0.5:
            return no("invalid stop distance")
        if p.stop_dist_pct < round_trip:
            return no(f"stop distance {p.stop_dist_pct:.2%} is inside round-trip cost {round_trip:.2%}")
        if p.exploratory and state.get("explore_halted"):
            return no("exploration loss budget exhausted")
        if p.consensus * p.side < -s.agent_veto_threshold:
            return no(f"agent consensus opposes the trade ({p.consensus:+.2f})")
        if p.book == "shadow":      # forward test: no capital at risk, only data/cost checks
            return Verdict(True, "forward-test (shadow) trade", s.shadow_notional_eur)
        # ---- portfolio limits --------------------------------------------------------
        acct = self.broker.account()
        equity = acct["equity"]
        peak = max(state.get("peak_equity") or equity, equity)
        if equity <= 0:
            return no("no equity")
        dd = 1 - equity / peak
        if dd >= s.max_drawdown_pct:
            return no(f"drawdown {dd:.1%} reached the {s.max_drawdown_pct:.0%} limit: new trades paused")
        day_start = state.get("day_start_equity") or equity
        if equity < day_start * (1 - s.max_daily_loss_pct):
            return no(f"daily loss limit {s.max_daily_loss_pct:.0%} reached")
        positions = self.broker.open_positions("live")
        if any(x.instrument == inst.symbol for x in positions):
            return no("already holding this instrument")
        if len(positions) >= s.max_positions:
            return no(f"maximum {s.max_positions} simultaneous positions")
        # ---- sizing ------------------------------------------------------------------
        size = min(equity * s.risk_per_trade_pct / p.stop_dist_pct,          # risk-based
                   equity * s.max_position_pct) * max(0.0, min(p.weight, 1.0))
        room = equity * s.max_exposure_pct - acct["invested"]
        bucket = sum(x.entry_notional_eur for x in positions if x.asset_class == cls and x.side == p.side)
        room_class = equity * s.max_class_exposure_pct - bucket
        cost_buffer = 1 + (s.fee_bps[cls] + s.fx_cost_bps) / 1e4
        power = self.broker.buying_power()
        size = min(size, room, room_class, power / cost_buffer)
        limits = {"exposure": room, "correlated exposure": room_class, "cash": power}
        if p.book_depth is not None:
            limits["liquidity"] = liq = p.book_depth * fx * s.max_book_participation
            size = min(size, liq)
        elif p.bar_turnover is not None and cls != "forex":    # stay a small part of real traded volume
            liq = p.bar_turnover * fx * s.max_bar_participation
            limits["liquidity"] = liq
            size = min(size, liq)
        if size < s.min_notional_eur:
            tight = min(limits, key=limits.get)
            return no(f"size €{max(size, 0):.2f} below minimum (limited by {tight})")
        return Verdict(True, "approved", round(size, 2))
