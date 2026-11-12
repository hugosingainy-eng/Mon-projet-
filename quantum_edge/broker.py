"""Internal PAPER broker and EUR accounting.

This is the only execution venue in the application. It simulates fills against observed
market prices and writes an append-only fill log; it has no network access and no code path
to any real broker.

Accounting identities (all EUR, `live` book):
    cash   = initial_capital + Σ fill.cash_delta
    equity = cash + Σ value(open positions)
           = initial_capital + realized_pnl + unrealized_pnl
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from .config import PAPER_MODE, SecurityError, Settings
from .db import Database, Decision, EquitySnapshot, Fill, Position, Signal, Strategy, utcnow
from .instruments import BY_SYMBOL, Instrument, is_market_open


class BrokerError(Exception):
    pass


class PaperBroker:
    mode = PAPER_MODE

    def __init__(self, settings: Settings, db: Database, hub):
        if settings.trading_mode != PAPER_MODE:
            raise SecurityError("PaperBroker refuses to start outside paper mode")
        self.s, self.db, self.hub = settings, db, hub

    # --- pricing ----------------------------------------------------------------------
    def _fill_price(self, inst: Instrument, buy: bool, now: datetime):
        """(fill price, reference price, quote) from a FRESH real quote, else BrokerError."""
        q = self.hub.quote(inst.symbol)
        if q is None:
            raise BrokerError(f"no market price for {inst.symbol}")
        if not self.hub.is_fresh(inst.symbol, now):
            raise BrokerError(f"stale price for {inst.symbol} ({q.age(now):.0f}s old)")
        if not is_market_open(inst, now):
            raise BrokerError(f"market closed for {inst.symbol}")
        cls = inst.asset_class
        if q.bid and q.ask and q.ask >= q.bid > 0:
            ref = (q.bid + q.ask) / 2
            px = q.ask if buy else q.bid
        else:   # provider has no order book: modelled half-spread around the last price
            ref = q.price
            hs = self.s.half_spread_bps[cls] / 1e4
            px = ref * (1 + hs) if buy else ref * (1 - hs)
        slip = self.s.slippage_bps[cls] / 1e4
        px = px * (1 + slip) if buy else px * (1 - slip)
        return px, ref, q

    def _fx(self, inst: Instrument) -> float:
        r = self.hub.fx_rate(inst.quote_ccy)
        if r is None:
            raise BrokerError(f"no FX rate for {inst.quote_ccy}")
        return r[0]

    def _fx_cost_rate(self, inst: Instrument) -> float:
        if inst.quote_ccy == self.s.base_currency or inst.asset_class == "forex":
            return 0.0
        return self.s.fx_cost_bps / 1e4

    # --- orders -----------------------------------------------------------------------
    def open(self, inst: Instrument, side: int, notional_eur: float, book: str = "live", *,
             strategy_id: int | None = None, strategy_name: str = "", stop_price: float | None = None,
             take_profit: float | None = None, trail_dist: float | None = None,
             expires_at: datetime | None = None, now: datetime | None = None) -> Position:
        now = now or utcnow()
        if side not in (1, -1) or notional_eur <= 0:
            raise BrokerError("invalid order")
        if not inst.tradable:
            raise BrokerError(f"{inst.symbol} is not tradable ({inst.note})")
        px, ref, q = self._fill_price(inst, buy=side == 1, now=now)
        fx = self._fx(inst)
        qty = notional_eur / (px * fx)
        if not self.s.allow_fractional and inst.asset_class in ("equity", "etf"):
            qty = math.floor(qty)
            if qty < 1:
                raise BrokerError("notional below one share and fractional shares are disabled")
        notional = qty * px * fx
        fee = notional * self.s.fee_bps[inst.asset_class] / 1e4
        fxc = notional * self._fx_cost_rate(inst)
        if book == "live" and notional + fee + fxc > self.cash() + 1e-9:
            raise BrokerError("insufficient cash")
        slip_eur = abs(px - ref) * qty * fx
        with self.db.session() as s:
            pos = Position(book=book, status="open", instrument=inst.symbol, asset_class=inst.asset_class,
                           quote_ccy=inst.quote_ccy, side=side, qty=qty, entry_price=px, entry_fx=fx,
                           entry_notional_eur=notional, opened_at=now, last_price=ref, last_fx=fx,
                           stop_price=stop_price, take_profit=take_profit, trail_dist=trail_dist,
                           expires_at=expires_at, strategy_id=strategy_id, strategy_name=strategy_name,
                           fees_eur=fee, slippage_eur=slip_eur, fx_cost_eur=fxc)
            s.add(pos)
            s.flush()
            s.add(Fill(ts=now, book=book, position_id=pos.id, instrument=inst.symbol, action="open",
                       side="buy" if side == 1 else "sell", qty=qty, ref_price=ref, price=px, fx=fx,
                       price_source=q.source, price_ts=q.ts, notional_eur=notional, fee_eur=fee,
                       slippage_eur=slip_eur, fx_cost_eur=fxc, cash_delta_eur=-(notional + fee + fxc),
                       reason="entry"))
        return pos

    def close(self, position_id: int, reason: str, now: datetime | None = None) -> Position:
        now = now or utcnow()
        with self.db.session() as s:
            pos = s.get(Position, position_id)
            if pos is None or pos.status != "open":
                raise BrokerError("position not open")
            inst = BY_SYMBOL[pos.instrument]
            px, ref, q = self._fill_price(inst, buy=pos.side == -1, now=now)
            fx = self._fx(inst)
            exit_notional = pos.qty * px * fx
            fee = exit_notional * self.s.fee_bps[inst.asset_class] / 1e4
            fxc = exit_notional * self._fx_cost_rate(inst)
            slip_eur = abs(px - ref) * pos.qty * fx
            borrow = 0.0
            if pos.side == 1:
                returned = exit_notional
            else:   # short: margin back plus P&L in quote currency converted at the current rate
                returned = pos.entry_notional_eur + pos.qty * (pos.entry_price - px) * fx
                days = max((now - pos.opened_at).total_seconds(), 0) / 86400
                borrow = pos.entry_notional_eur * self.s.short_borrow_bps_per_day / 1e4 * days
            cash_delta = returned - fee - fxc - borrow
            entry_costs = pos.fees_eur + pos.fx_cost_eur
            pos.realized_pnl_eur = cash_delta - pos.entry_notional_eur - entry_costs
            pos.status, pos.closed_at, pos.exit_price, pos.exit_reason = "closed", now, px, reason
            pos.last_price, pos.last_fx = ref, fx
            pos.fees_eur += fee + borrow
            pos.fx_cost_eur += fxc
            pos.slippage_eur += slip_eur
            s.add(Fill(ts=now, book=pos.book, position_id=pos.id, instrument=pos.instrument, action="close",
                       side="sell" if pos.side == 1 else "buy", qty=pos.qty, ref_price=ref, price=px, fx=fx,
                       price_source=q.source, price_ts=q.ts, notional_eur=exit_notional, fee_eur=fee,
                       slippage_eur=slip_eur, fx_cost_eur=fxc, borrow_eur=borrow, cash_delta_eur=cash_delta,
                       reason=reason))
        return pos

    # --- marking and protective exits -------------------------------------------------
    @staticmethod
    def value(pos: Position) -> float:
        if pos.side == 1:
            return pos.qty * pos.last_price * pos.last_fx
        return pos.entry_notional_eur + pos.qty * (pos.entry_price - pos.last_price) * pos.last_fx

    def open_positions(self, book: str | None = "live") -> list[Position]:
        with self.db.session() as s:
            q = select(Position).where(Position.status == "open")
            if book:
                q = q.where(Position.book == book)
            return list(s.scalars(q.order_by(Position.id)))

    def mark_and_check(self, now: datetime | None = None, flatten: bool = False) -> list[tuple[Position, str]]:
        """Mark open positions to fresh quotes, trail stops, and close positions whose stop,
        target or time limit is hit (or everything closable, when `flatten`)."""
        now = now or utcnow()
        closed = []
        for pos in self.open_positions(book=None):
            q = self.hub.quote(pos.instrument)
            inst = BY_SYMBOL[pos.instrument]
            if q is None or not self.hub.is_fresh(pos.instrument, now) or not is_market_open(inst, now):
                continue          # no fresh price: nothing is marked, nothing is simulated
            fxr = self.hub.fx_rate(pos.quote_ccy)
            if fxr is None:
                continue
            px = q.price
            reason = None
            with self.db.session() as s:
                p = s.get(Position, pos.id)
                p.last_price, p.last_fx = px, fxr[0]
                if p.trail_dist and p.stop_price is not None:
                    p.stop_price = (max(p.stop_price, px - p.trail_dist) if p.side == 1
                                    else min(p.stop_price, px + p.trail_dist))
                if flatten and p.book == "live":
                    reason = "flatten"
                elif p.stop_price is not None and (px <= p.stop_price if p.side == 1 else px >= p.stop_price):
                    reason = "stop"
                elif p.take_profit is not None and (px >= p.take_profit if p.side == 1 else px <= p.take_profit):
                    reason = "take_profit"
                elif p.expires_at is not None and now >= p.expires_at:
                    reason = "time_limit"
            if reason:
                try:
                    closed.append((self.close(pos.id, reason, now), reason))
                except BrokerError:
                    pass
        return closed

    # --- accounting -------------------------------------------------------------------
    def cash(self) -> float:
        with self.db.session() as s:
            d = s.scalar(select(func.coalesce(func.sum(Fill.cash_delta_eur), 0.0)).where(Fill.book == "live"))
        return self.s.initial_capital + float(d)

    def account(self) -> dict:
        with self.db.session() as s:
            cash = self.s.initial_capital + float(s.scalar(
                select(func.coalesce(func.sum(Fill.cash_delta_eur), 0.0)).where(Fill.book == "live")))
            opens = list(s.scalars(select(Position).where(Position.book == "live", Position.status == "open")))
            realized = float(s.scalar(select(func.coalesce(func.sum(Position.realized_pnl_eur), 0.0)).where(
                Position.book == "live", Position.status == "closed")))
            fees, slip, fxc = s.execute(select(
                func.coalesce(func.sum(Fill.fee_eur + Fill.borrow_eur), 0.0),
                func.coalesce(func.sum(Fill.slippage_eur), 0.0),
                func.coalesce(func.sum(Fill.fx_cost_eur), 0.0)).where(Fill.book == "live")).one()
        invested = sum(p.entry_notional_eur for p in opens)
        value = sum(self.value(p) for p in opens)
        open_costs = sum(p.fees_eur + p.fx_cost_eur for p in opens)
        equity = cash + value
        return {"currency": self.s.base_currency, "initial_capital": self.s.initial_capital,
                "equity": equity, "cash": cash, "invested": invested, "positions_value": value,
                "realized_pnl": realized, "unrealized_pnl": value - invested - open_costs,
                "fees": float(fees), "slippage": float(slip), "fx_costs": float(fxc)}

    def audit(self) -> dict:
        """Replay the fill log from scratch and compare with the stored positions."""
        with self.db.session() as s:
            fills = list(s.scalars(select(Fill).where(Fill.book == "live").order_by(Fill.id)))
            closed = list(s.scalars(select(Position).where(Position.book == "live", Position.status == "closed")))
        cash = self.s.initial_capital
        per_pos: dict[int, float] = {}
        for f in fills:
            cash += f.cash_delta_eur
            per_pos[f.position_id] = per_pos.get(f.position_id, 0.0) + f.cash_delta_eur
        realized_from_fills = sum(per_pos[p.id] for p in closed)
        realized_stored = sum(p.realized_pnl_eur for p in closed)
        acct = self.account()
        return {"cash_replayed": cash, "cash_reported": acct["cash"],
                "realized_replayed": realized_from_fills, "realized_reported": realized_stored,
                "identity_gap": acct["equity"] - (acct["initial_capital"] + acct["realized_pnl"] + acct["unrealized_pnl"]),
                "ok": abs(cash - acct["cash"]) < 1e-6 and abs(realized_from_fills - realized_stored) < 1e-6}

    def reset(self) -> None:
        """Wipe the paper portfolio and its history (experiments in the lab are kept)."""
        with self.db.session() as s:
            for model in (Fill, Position, EquitySnapshot, Decision, Signal, Strategy):
                s.execute(delete(model))
