"""Central orchestration engine: the experiment clock, the agent schedule, the strategy
pipeline (signal -> proposal -> Risk Manager -> paper execution) and restart recovery."""
from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, select

from . import indicators as ti
from .agents import build_agents
from .broker import BrokerError, PaperBroker
from .config import Settings, validate_paper_only
from .data.base import TF_SECONDS
from .data.hub import DataHub
from .db import Database, EquitySnapshot, Position, Signal, Strategy, utcnow
from .instruments import BY_SYMBOL, is_market_open
from .lab import Lab
from .risk import Proposal, RiskManager
from .strategies import Data, signals as strategy_signals

DEFAULT_STATE = {"explore_halted": False, "status": "idle", "started_at": None, "ends_at": None, "flatten": False,
                 "halt_reason": None, "peak_equity": None, "max_drawdown": 0.0,
                 "day": None, "day_start_equity": None}


def default_providers(settings: Settings) -> dict:
    from .data.ccxt_provider import CcxtProvider
    from .data.yahoo_provider import YahooProvider
    return {"ccxt": CcxtProvider(settings.crypto_exchanges, settings.crypto_history_exchanges), "yahoo": YahooProvider()}


class Engine:
    def __init__(self, settings: Settings, providers: dict | None = None, clock=None):
        validate_paper_only(settings)
        self.s = settings
        self._clock = clock or utcnow
        self.db = Database(settings.db_path)
        self.hub = DataHub(settings, providers if providers is not None else default_providers(settings))
        self.broker = PaperBroker(settings, self.db, self.hub)
        self.risk = RiskManager(settings, self.db, self.hub, self.broker)
        self.lab = Lab(settings, self.db, self.hub)
        self.lab.on_finish = self.deploy
        self.lab.revalidate = self._active_configs
        self.agents = build_agents()
        self.market_stats: dict[str, dict] = {}
        self.focus: list[str] = []
        self.loop_lag = 0.0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_snapshot = 0.0
        self._incident_seen: dict[str, float] = {}
        self.state = {**DEFAULT_STATE, **(self.db.get("experiment") or {})}
        self._recover()

    # --- time / state -----------------------------------------------------------------
    def now(self) -> datetime:
        return self._clock()

    def _save(self):
        self.db.set("experiment", self.state)

    def _recover(self):
        """After a restart: keep the same experiment and clock; record the downtime."""
        hb = self.db.get("heartbeat")
        if self.state["status"] in ("running", "paused") and hb:
            gap = (self.now() - datetime.fromisoformat(hb)).total_seconds()
            self.db.incident("warning", "supervisor",
                             f"application restarted; experiment resumed as '{self.state['status']}' after "
                             f"{gap / 60:.1f} min offline (no trades or prices were simulated during the gap)",
                             recovered=True)

    def incident(self, severity: str, component: str, message: str, every: float = 900.0):
        """Record an incident, suppressing identical repeats within `every` seconds."""
        key = f"{component}:{message[:120]}"
        if time.monotonic() - self._incident_seen.get(key, -1e9) < every:
            return
        self._incident_seen[key] = time.monotonic()
        self.db.incident(severity, component, message)

    # --- controls ---------------------------------------------------------------------
    def control(self, action: str, confirm: bool = False, options: dict | None = None) -> tuple[bool, str]:
        with self._lock:
            st, now = self.state, self.now()
            status = st["status"]
            if action == "start":
                if status in ("running", "paused"):
                    return False, f"experiment already {status}"
                if status == "completed":
                    return False, "experiment completed — use RESET PAPER PORTFOLIO to begin a new one"
                if status == "idle":
                    st.update(started_at=now.isoformat(),
                              ends_at=(now + timedelta(days=self.s.duration_days)).isoformat())
                    msg = f"experiment started: €{self.s.initial_capital:,.0f} paper capital, {self.s.duration_days:g} days"
                else:
                    if now >= datetime.fromisoformat(st["ends_at"]):
                        return False, "experiment clock has expired — use RESET PAPER PORTFOLIO"
                    msg = "experiment restarted on the same clock"
                st.update(status="running", flatten=False, halt_reason=None)
            elif action == "pause":
                if status != "running":
                    return False, "not running"
                st["status"] = "paused"
                msg = "paused: no new trades; stops and targets stay active; the clock keeps running"
            elif action == "resume":
                if status != "paused":
                    return False, "not paused"
                st["status"] = "running"
                msg = "resumed"
            elif action == "stop":
                if status not in ("running", "paused"):
                    return False, "not running"
                st.update(status="stopped", flatten=True, halt_reason="stopped by user")
                msg = "stopped: open positions are closed as soon as a fresh market price is available"
            elif action == "emergency_stop":
                if not confirm:
                    return False, "confirmation required"
                st.update(status="halted", flatten=True, halt_reason="EMERGENCY STOP")
                self.lab.stop()
                self._save()
                closed = self.broker.mark_and_check(now, flatten=True)
                left = len(self.broker.open_positions("live"))
                msg = (f"EMERGENCY STOP: trading halted, {len(closed)} positions closed"
                       + (f", {left} on closed/stale markets will close at the first fresh price" if left else ""))
                self.db.incident("error", "supervisor", msg)
            elif action == "run_experiments":
                opt = options or {}
                classes, tfs = opt.get("asset_classes"), opt.get("timeframes")
                if not self.lab.start(classes=classes, timeframes=tfs):
                    return False, "the strategy lab is already running"
                scope = f" on {', '.join(classes)}" if classes else ""
                return True, f"strategy lab started: {self.s.lab_target:,} experiments{scope}"
            elif action == "kickstart":
                if not confirm:
                    return False, "confirmation required"
                if status != "running":
                    return False, "not running"
                opened = self.kickstart(now)
                msg = ("kick-start: opened " + ", ".join(opened)) if opened else "kick-start: no trade could be opened (see risk decisions)"
            elif action == "reset":
                if not confirm:
                    return False, "confirmation required"
                if status in ("running", "paused"):
                    return False, "stop the experiment before resetting"
                self.broker.reset()
                self.state = dict(DEFAULT_STATE)
                self.risk.approved = self.risk.rejected = 0
                msg = f"paper portfolio reset to €{self.s.initial_capital:,.0f}; lab experiments kept"
            else:
                return False, f"unknown action '{action}'"
            self._save()
            self.db.incident("info", "control", f"{action}: {msg}")
            for a in self.agents:
                if a.id in ("optimizer", "risk", "execution", "performance", "supervisor"):
                    a._next = 0.0            # react to the new state on the very next cycle
            self._wake.set()
            return True, msg

    # --- main loop --------------------------------------------------------------------
    def start_thread(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)
        self._thread.start()

    def shutdown(self):
        self._stop.set()
        self._wake.set()
        self.lab.stop()
        if self._thread:
            self._thread.join(timeout=15)

    def _run(self):
        while not self._stop.is_set():
            t0 = time.monotonic()
            try:
                self.cycle()
            except Exception as e:      # the loop must survive anything; the supervisor reports it
                self.incident("error", "engine", f"cycle failed: {type(e).__name__}: {e} | "
                              + traceback.format_exc().strip().splitlines()[-2].strip(), every=120)
            self.loop_lag = time.monotonic() - t0
            self._wake.wait(max(1.0, self.s.cycle_seconds - self.loop_lag))
            self._wake.clear()

    def cycle(self):
        """One engine cycle. Network calls run OUTSIDE the lock so dashboard controls
        (pause, emergency stop...) never wait behind a slow or failing data provider."""
        now = self.now()
        for e in self.hub.refresh_quotes(now):
            self.incident("warning", "data", e)
        with self._lock:
            st = self.state
            if st["status"] != "idle":
                for pos, reason in self.broker.mark_and_check(now, flatten=st["flatten"]):
                    if pos.book == "live":
                        self.db.incident("info", "execution",
                                         f"closed {pos.instrument} ({reason}): net €{pos.realized_pnl_eur:+.2f}")
                if st["flatten"] and not self.broker.open_positions(None):
                    st["flatten"] = False
                self._track_equity(now)
            if st["status"] in ("running", "paused") and now >= datetime.fromisoformat(st["ends_at"]):
                self._complete(now)
            self._save()
        for agent in self.agents:
            if self._stop.is_set():
                return
            if agent.due():
                self.run_agent(agent)
        if self.state["status"] == "running":
            self.evaluate_strategies(self.now())
        with self._lock:
            self._save()

    def _track_equity(self, now: datetime):
        st = self.state
        acct = self.broker.account()
        eq = acct["equity"]
        st["peak_equity"] = max(st["peak_equity"] or eq, eq)
        st["max_drawdown"] = max(st["max_drawdown"], 1 - eq / st["peak_equity"])
        day = now.strftime("%Y-%m-%d")
        if st["day"] != day:
            st["day"], st["day_start_equity"] = day, eq
        if time.monotonic() - self._last_snapshot >= self.s.snapshot_seconds:
            self._last_snapshot = time.monotonic()
            with self.db.session() as s:
                s.add(EquitySnapshot(ts=now, equity=eq, cash=acct["cash"]))

    def _complete(self, now: datetime):
        self.state.update(status="completed", flatten=True, halt_reason="five-day experiment finished")
        self.broker.mark_and_check(now, flatten=True)
        self.db.incident("info", "control", "experiment clock finished: trading stopped, final report generated")
        try:
            from .report import save_final
            save_final(self)
        except Exception as e:
            self.db.incident("error", "report", f"final report failed: {type(e).__name__}: {e}")

    # --- agents -----------------------------------------------------------------------
    def run_agent(self, agent):
        agent._next = time.monotonic() + agent.interval
        prev = agent.status
        agent.status = "running"
        try:
            activity, sigs = agent.run(self)
            agent.activity = activity
            if agent.status == "running":
                agent.status = "ok"
            if prev == "error":
                self.db.incident("info", "supervisor", f"agent '{agent.id}' recovered", recovered=True)
            if sigs:
                with self.db.session() as s:
                    for g in sigs:
                        s.add(Signal(ts=self.now(), agent=agent.id, instrument=g["instrument"],
                                     direction={1: "long", -1: "short"}.get(g["direction"], "neutral"),
                                     confidence=g["confidence"], summary=g["summary"],
                                     data={k: (None if v is None else float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                                           for k, v in g["data"].items()}))
        except Exception as e:
            agent.status = "error"
            agent.errors += 1
            agent.last_error = f"{type(e).__name__}: {e}"[:300]
            agent._next = time.monotonic() + min(agent.interval, 120)     # retry soon ("restart")
            self.incident("error", agent.id, f"agent failed, will retry: {agent.last_error}")
        agent.last_run = self.now()

    def consensus(self, symbol: str) -> float:
        """Signed sum of each analysis agent's latest signal (last 30 minutes)."""
        since = self.now() - timedelta(minutes=30)
        with self.db.session() as s:
            rows = list(s.scalars(select(Signal).where(Signal.instrument == symbol, Signal.ts >= since)
                                  .order_by(Signal.ts.desc())))
        latest = {}
        for r in rows:
            latest.setdefault(r.agent, r)
        return sum({"long": 1, "short": -1}.get(r.direction, 0) * r.confidence for r in latest.values())

    # --- strategy pipeline ------------------------------------------------------------
    def deploy(self, run_id: int):
        """Called when a lab run completes: PASS configurations enter the FORWARD test."""
        cands = self.lab.candidates(run_id)
        now, added, keep = self.now(), 0, set()
        with self.db.session() as s:
            active = list(s.scalars(select(Strategy).where(Strategy.stage != "retired")))
            index = {(a.family, str(sorted(a.params.items())), a.instrument, a.timeframe): a for a in active}
            for c in cands:
                key = (c.family, str(sorted(c.params.items())), c.instrument, c.timeframe)
                keep.add(key)
                oos = [c.segments[k]["avg"] for k in ("val", "test") if c.segments[k]["avg"] is not None]
                expected = float(np.mean(oos)) if oos else 0.0
                if key in index:
                    index[key].experiment_id, index[key].expected_trade_pct = c.id, expected
                    continue
                s.add(Strategy(experiment_id=c.id, family=c.family, params=c.params, instrument=c.instrument,
                               timeframe=c.timeframe, stage="forward", weight=1.0, expected_trade_pct=expected,
                               note="validated in the lab; forward test on live prices", created_at=now, updated_at=now))
                added += 1
            for key, a in index.items():
                if key in keep:
                    continue
                verdict = self.lab.verdict(run_id, a.family, a.params, a.instrument, a.timeframe)
                if verdict is not None and verdict != "PASS":      # re-tested on fresh data and failed
                    a.stage, a.updated_at = "retired", now
                    a.note = f"retired: re-validation on fresh data gave {verdict}"
        self.db.incident("info", "optimizer", f"research run {run_id}: {len(cands)} validated candidates, {added} new in forward test")
        picks = self.lab.exploration_picks(run_id)
        if picks:
            with self.db.session() as s:
                for old in s.scalars(select(Strategy).where(Strategy.stage == "explore")):
                    old.stage, old.note, old.updated_at = "retired", "exploration slot replaced by a newer research run", now
                for c in picks:
                    oos = [c.segments[k]["avg"] for k in ("val", "test") if c.segments[k]["avg"] is not None]
                    s.add(Strategy(experiment_id=c.id, family=c.family, params=c.params, instrument=c.instrument,
                                   timeframe=c.timeframe, stage="explore", weight=self.s.explore_weight,
                                   expected_trade_pct=float(np.mean(oos)) if oos else 0.0,
                                   note=f"EXPLORATION: not validated (lab verdict {c.evaluation}); small size, loss budget applies",
                                   created_at=now, updated_at=now))
            self.db.incident("warning", "optimizer", f"exploration: {len(picks)} unvalidated high-frequency strategies trade with small size (owner's setting)")

    def _active_configs(self) -> list[tuple]:
        with self.db.session() as s:
            return [(a.family, a.params, a.instrument, a.timeframe)
                    for a in s.scalars(select(Strategy).where(Strategy.stage != "retired"))]

    def kickstart(self, now: datetime, count: int = 3) -> list[str]:
        """Owner-requested immediate entries: small exploratory positions on the instruments
        where the analysis agents currently agree most, in the direction they indicate.
        These are NOT lab-validated trades; they go through the Risk Manager, carry a stop,
        a target and a time limit, and count against the exploration loss budget."""
        ranked = []
        for inst in (i for i in BY_SYMBOL.values() if i.tradable and i.asset_class in self.s.explore_classes):
            c = self.consensus(inst.symbol)
            if abs(c) > 0 and self.hub.is_fresh(inst.symbol, now) and is_market_open(inst, now):
                ranked.append((abs(c), c, inst))
        opened = []
        for _, c, inst in sorted(ranked, key=lambda x: -x[0]):
            if len(opened) >= count:
                break
            df = self.hub.candles(inst, "15m", bars=300)
            if len(df) < 60:
                continue
            d = Data(df)
            atr = float(d.ind("atr", 14)[-1])
            price = self.hub.quote(inst.symbol).price
            if not np.isfinite(atr) or atr <= 0:
                continue
            side, dist = (1 if c > 0 else -1), 2.0 * atr
            name = "explore:kickstart/agents"
            verdict = self.risk.evaluate(Proposal(
                inst=inst, side=side, strategy_id=None, strategy_name=name, book="live",
                stop_dist_pct=dist / price, weight=self.s.explore_weight, expected_trade_pct=0.0,
                bar_turnover=float(d.v[-1] * d.c[-1]) if d.has_volume else None,
                consensus=c, exploratory=True), self.state, now)
            if not verdict.approved:
                continue
            try:
                pos = self.broker.open(inst, side, verdict.notional_eur, "live", strategy_name=name,
                                       stop_price=price - side * dist, take_profit=price + side * 1.5 * dist,
                                       expires_at=now + timedelta(hours=6), now=now)
            except BrokerError as e:
                self.incident("warning", "execution", f"kick-start {inst.symbol}: {e}")
                continue
            opened.append(f"{'long' if side == 1 else 'short'} {inst.symbol} €{pos.entry_notional_eur:.2f}")
            self.db.incident("warning", "execution",
                             f"opened {'long' if side == 1 else 'short'} {inst.symbol} €{pos.entry_notional_eur:.2f} @ {pos.entry_price:.6g} "
                             f"(kick-start on owner's request, agent consensus {c:+.2f}; not a validated strategy)")
        return opened

    def evaluate_strategies(self, now: datetime):
        with self.db.session() as s:
            strategies = list(s.scalars(select(Strategy).where(Strategy.stage.in_(("forward", "live", "explore")))))
        for st in strategies:
            try:
                inst = BY_SYMBOL[st.instrument]
                if is_market_open(inst, now) and self.hub.is_fresh(inst.symbol, now):
                    self.hub.candles(inst, st.timeframe, bars=600)      # network, outside the lock
                    if inst.benchmark:
                        self.hub.candles(BY_SYMBOL[inst.benchmark], st.timeframe, bars=600)
                with self._lock:
                    if self.state["status"] != "running":
                        return                                          # paused/stopped meanwhile
                    self._evaluate_one(st, now)
            except BrokerError as e:
                self.incident("warning", "execution", f"{st.instrument}: {e}")
            except Exception as e:
                self.incident("error", "engine", f"strategy {st.id} ({st.family} {st.instrument}): {type(e).__name__}: {e}")

    def _evaluate_one(self, st: Strategy, now: datetime):
        inst = BY_SYMBOL[st.instrument]
        if not is_market_open(inst, now) or not self.hub.is_fresh(inst.symbol, now):
            return
        df = self.hub.candles(inst, st.timeframe, bars=600)
        if len(df) < 250:
            return
        bar_ts = df.index[-1].to_pydatetime()
        if st.last_bar_ts is not None and bar_ts <= st.last_bar_ts:
            return                                   # this completed bar was already acted on
        with self.db.session() as s:
            s.get(Strategy, st.id).last_bar_ts = bar_ts
        tf = TF_SECONDS[st.timeframe]
        if (now - bar_ts).total_seconds() > 2.5 * tf:
            return                                   # the latest bar is old (gap in data): do not act on it
        bench = None
        if inst.benchmark:
            bdf = self.hub.candles(BY_SYMBOL[inst.benchmark], st.timeframe, bars=600)
            bench = bdf["close"] if len(bdf) else None
        d = Data(df, bench)
        if st.family in ("relative_strength", "pairs_ratio") and d.bench is None:
            return
        le, se, lx, sx = strategy_signals(st.family, d, st.params)
        book = "live" if st.stage in ("live", "explore") else "shadow"
        exploring = st.stage == "explore"
        with self.db.session() as s:
            pos = s.scalar(select(Position).where(Position.strategy_id == st.id, Position.status == "open",
                                                  Position.book == book))
        if pos is not None:
            if (pos.side == 1 and lx[-1]) or (pos.side == -1 and sx[-1]):
                closed = self.broker.close(pos.id, "signal", now)
                if book == "live":
                    self.db.incident("info", "execution", f"closed {pos.instrument} (signal): net €{closed.realized_pnl_eur:+.2f}")
            return
        if le[-1] == se[-1]:
            return
        side = 1 if le[-1] else -1
        atr = float(d.ind("atr", 14)[-1])
        price = self.hub.quote(inst.symbol).price
        if not np.isfinite(atr) or atr <= 0:
            return
        p = st.params
        dist = p["stop_atr"] * atr
        name = f"{'explore:' if exploring else ''}{st.family}/{st.timeframe}#{st.id}"
        verdict = self.risk.evaluate(Proposal(
            inst=inst, side=side, strategy_id=st.id, strategy_name=name, book=book,
            stop_dist_pct=dist / price, weight=st.weight, expected_trade_pct=st.expected_trade_pct,
            bar_turnover=float(d.v[-1] * d.c[-1]) if d.has_volume else None,
            consensus=self.consensus(inst.symbol), exploratory=exploring), self.state, now)
        if not verdict.approved:
            return
        pos = self.broker.open(
            inst, side, verdict.notional_eur, book, strategy_id=st.id, strategy_name=name,
            stop_price=price - side * dist, take_profit=(price + side * p["rr"] * dist) if p["rr"] > 0 else None,
            trail_dist=dist if p["trail"] else None, expires_at=now + timedelta(seconds=p["max_hold"] * tf), now=now)
        if book == "live":
            self.db.incident("info", "execution",
                             f"opened {'long' if side == 1 else 'short'} {inst.symbol} €{pos.entry_notional_eur:.2f} @ {pos.entry_price:.6g} ({name})")

    # --- views ------------------------------------------------------------------------
    def state_view(self) -> dict:
        st, now = self.state, self.now()
        acct = self.broker.account()
        total = self.s.duration_days * 86400
        elapsed = 0.0
        if st["started_at"]:
            elapsed = min(total, max(0.0, (now - datetime.fromisoformat(st["started_at"])).total_seconds()))
        eq = acct["equity"]
        day0 = st["day_start_equity"]
        acct.update(total_return_pct=(eq / acct["initial_capital"] - 1) * 100,
                    daily_return_pct=(eq / day0 - 1) * 100 if day0 else 0.0,
                    max_drawdown_pct=st["max_drawdown"] * 100)
        with self.db.session() as s:
            closed = list(s.scalars(select(Position).where(Position.book == "live", Position.status == "closed")))
            n_open = s.scalar(select(func.count()).select_from(Position).where(Position.book == "live", Position.status == "open"))
        pnl = [p.realized_pnl_eur for p in closed]
        wins = [x for x in pnl if x > 0]
        losses = [x for x in pnl if x <= 0]
        lab = self.lab.status()
        lab["running"] = self.lab.is_running()
        lab["total_all_runs"] = self.lab.total()
        return {
            "server_time": now.isoformat(),
            "experiment": {"status": st["status"], "mode": self.s.trading_mode, "started_at": st["started_at"],
                           "ends_at": st["ends_at"], "duration_days": self.s.duration_days,
                           "elapsed_seconds": elapsed, "remaining_seconds": total - elapsed,
                           "halt_reason": st["halt_reason"]},
            "portfolio": acct,
            "trading": {"open_positions": n_open, "closed_trades": len(pnl), "wins": len(wins), "losses": len(losses),
                        "win_rate": len(wins) / len(pnl) if pnl else None,
                        "profit_factor": sum(wins) / -sum(losses) if losses and sum(losses) < 0 else None,
                        "avg_duration_minutes": float(np.mean([(p.closed_at - p.opened_at).total_seconds() / 60 for p in closed])) if closed else None,
                        "expectancy": float(np.mean(pnl)) if pnl else None},
            "lab": lab,
        }
