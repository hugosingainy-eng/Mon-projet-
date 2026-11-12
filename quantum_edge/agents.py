"""The fourteen agents. Each one is a deterministic, inspectable module with a single role.
Analysis agents return structured signals (instrument, direction, confidence, evidence);
they never trade. Only strategies validated by the lab can propose trades, and only the
Risk Manager can approve them."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, select

from . import elite
from . import indicators as ti
from .data.base import resample
from .db import Incident, News, Position, Signal, Strategy, utcnow
from .instruments import BY_SYMBOL, UNIVERSE, is_market_open


def sig(symbol: str, direction: int, confidence: float, summary: str, **data) -> dict:
    return {"instrument": symbol, "direction": direction, "confidence": float(max(0.0, min(1.0, confidence))),
            "summary": summary[:300], "data": data}


class Agent:
    id = "agent"
    name = "Agent"
    role = ""
    interval = 300.0

    def __init__(self):
        self.status = "idle"
        self.last_run: datetime | None = None
        self.activity = ""
        self.errors = 0
        self.last_error: str | None = None
        self._next = 0.0

    def due(self) -> bool:
        return time.monotonic() >= self._next

    def run(self, eng) -> tuple[str, list[dict]]:
        raise NotImplementedError

    def info(self) -> dict:
        return {"id": self.id, "name": self.name, "role": self.role, "status": self.status,
                "last_run": self.last_run.isoformat() if self.last_run else None,
                "activity": self.activity, "errors": self.errors, "last_error": self.last_error}


def _arr(df):
    return (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))


# ---------------------------------------------------------------------------------------
class MarketScanner(Agent):
    id, name, role = "scanner", "Market Scanner", "Scans every market, ranks instruments, detects regimes"

    def run(self, eng):
        errs = eng.hub.prefetch(UNIVERSE, "1h", 900)
        errs += eng.hub.prefetch([i for i in UNIVERSE if i.tradable], "15m", 900)
        for e in errs:
            eng.db.incident("warning", self.id, e)
        ranked = []
        for inst in UNIVERSE:
            df = eng.hub.cached_candles(inst, "1h")
            if df is None or len(df) < 60:
                continue
            o, h, l, c, v = _arr(df)
            r = np.diff(np.log(c[-61:]))
            sd = r.std()
            mom = (c[-1] / c[-25] - 1) if len(c) > 25 else 0.0
            z = mom / (sd * np.sqrt(24)) if sd > 0 else 0.0
            volx = v[-1] / v[-21:-1].mean() if v[-21:-1].mean() > 0 else None
            atr_pct = ti.atr(h, l, c, 14)[-1] / c[-1] * 100
            eng.market_stats[inst.symbol] = {"volatility_pct": float(atr_pct), "regime": ti.regime(h, l, c),
                                             "momentum_z": float(z), "volume_x": volx, "bar_ts": df.index[-1]}
            score = abs(z) + max(0.0, (volx or 1.0) - 1.0)
            if inst.tradable:
                ranked.append((score, inst.symbol, z, volx, atr_pct))
        ranked.sort(reverse=True)
        eng.focus = [sym for _, sym, *_ in ranked[:14]]
        out = []
        for score, sym, z, volx, atr_pct in ranked[:8]:
            if abs(z) < 1.0 and (volx or 0) < 2.0:
                continue
            out.append(sig(sym, int(np.sign(z)) if abs(z) >= 1.0 else 0, score / 4,
                           f"24-bar momentum z={z:+.2f}, volume x{volx:.1f}, ATR {atr_pct:.2f}%" if volx
                           else f"24-bar momentum z={z:+.2f}, ATR {atr_pct:.2f}%", z=z, volume_x=volx))
        return f"scanned {len(eng.market_stats)} instruments, {len(out)} opportunities", out


class TechnicalAnalyst(Agent):
    id, name, role = "technical", "Technical Analyst", "Multi-timeframe indicator analysis (RSI, MACD, EMA, VWAP, Bollinger, ADX, StochRSI, S/R, Fibonacci, candles)"

    def votes(self, df) -> tuple[int, list[str]]:
        o, h, l, c, v = _arr(df)
        if len(c) < 210:
            return 0, []
        score, why = 0, []

        def vote(cond_up, cond_dn, label):
            nonlocal score
            if cond_up:
                score += 1; why.append("+" + label)
            elif cond_dn:
                score -= 1; why.append("-" + label)

        r = ti.rsi(c)[-1]
        vote(r < 30, r > 70, f"RSI {r:.0f}")
        hist = ti.macd(c)[2]
        vote(hist[-1] > 0 and hist[-1] > hist[-2], hist[-1] < 0 and hist[-1] < hist[-2], "MACD")
        e50, s200 = ti.ema(c, 50)[-1], ti.sma(c, 200)[-1]
        vote(c[-1] > e50 > s200, c[-1] < e50 < s200, "EMA50/SMA200")
        lo, mid, up = ti.bollinger(c)
        vote(c[-1] < lo[-1], c[-1] > up[-1], "Bollinger")
        sr = ti.stoch_rsi(c)[-1]
        vote(sr < 15, sr > 85, f"StochRSI {sr:.0f}")
        vw = ti.rolling_vwap(h, l, c, v, 50)[-1]
        a = ti.adx(h, l, c)[-1]
        vote(a > 25 and c[-1] > vw, a > 25 and c[-1] < vw, f"ADX {a:.0f}+VWAP")
        sup, res = ti.support_resistance(h, l, 10)
        at = ti.atr(h, l, c)[-1]
        vote(abs(c[-1] - sup[-1]) < 0.5 * at, abs(c[-1] - res[-1]) < 0.5 * at, "S/R")
        fib = ti.fibonacci_levels(h, l, 100)
        if fib:
            near = min(fib.items(), key=lambda kv: abs(kv[1] - c[-1]))
            if abs(near[1] - c[-1]) < 0.3 * at and near[0] in ("0.382", "0.5", "0.618"):
                why.append(f"at Fib {near[0]}")
        pat = ti.candle_pattern(o, h, l, c)
        if pat:
            vote(pat in ("bullish_engulfing", "hammer"), pat in ("bearish_engulfing", "shooting_star"), pat)
        return score, why

    def run(self, eng):
        out = []
        for sym in eng.focus:
            inst = BY_SYMBOL[sym]
            frames = {"15m": eng.hub.cached_candles(inst, "15m"), "1h": eng.hub.cached_candles(inst, "1h")}
            if frames["1h"] is not None and len(frames["1h"]) > 900:
                frames["4h"] = resample(frames["1h"], "4h")
            total, parts = 0, []
            for tf, df in frames.items():
                if df is None:
                    continue
                sc, why = self.votes(df)
                total += sc
                if why:
                    parts.append(f"{tf}: {' '.join(why)}")
            if abs(total) >= 3:
                out.append(sig(sym, int(np.sign(total)), abs(total) / 8, "; ".join(parts), score=total))
        return f"analysed {len(eng.focus)} instruments on 15m/1h/4h, {len(out)} signals", out


class MomentumTrader(Agent):
    id, name, role = "momentum", "Momentum Trader", "Relative strength, acceleration, breakouts with volume confirmation"

    def run(self, eng):
        out = []
        for sym in eng.focus:
            df = eng.hub.cached_candles(BY_SYMBOL[sym], "1h")
            if df is None or len(df) < 60:
                continue
            o, h, l, c, v = _arr(df)
            r20, r5 = c[-1] / c[-21] - 1, c[-1] / c[-6] - 1
            hh, ll = c[-21:-1].max(), c[-21:-1].min()
            vol_ok = v[-21:-1].mean() == 0 or v[-1] > 1.3 * v[-21:-1].mean()
            accel = abs(r5) > abs(r20) / 3 and np.sign(r5) == np.sign(r20)
            if c[-1] > hh and vol_ok:
                out.append(sig(sym, 1, 0.5 + 0.3 * accel, f"breakout above 20-bar high, r20={r20:+.2%}", r20=r20))
            elif c[-1] < ll and vol_ok:
                out.append(sig(sym, -1, 0.5 + 0.3 * accel, f"breakdown below 20-bar low, r20={r20:+.2%}", r20=r20))
            elif accel and abs(r20) > 0.03:
                out.append(sig(sym, int(np.sign(r20)), 0.4, f"accelerating trend r5={r5:+.2%} r20={r20:+.2%}", r20=r20))
        return f"{len(out)} momentum signals", out


class ScalpingAgent(Agent):
    id, name, role = "scalping", "Scalping Agent", "Short-horizon microstructure on liquid crypto (spread, order-book imbalance) — polling-based, not HFT"
    interval = 120.0

    def run(self, eng):
        out, checked = [], 0
        cryptos = [i for i in UNIVERSE if i.asset_class == "crypto"][:5]
        for inst in cryptos:
            try:
                ob = eng.hub.order_book(inst)
            except Exception as e:
                eng.db.incident("warning", self.id, f"order book {inst.symbol}: {type(e).__name__}: {e}")
                continue
            df = eng.hub.cached_candles(inst, "15m")
            if not ob or df is None or len(df) < 30:
                continue
            checked += 1
            o, h, l, c, v = _arr(df)
            exp_move = 0.5 * ti.atr(h, l, c, 14)[-1] / c[-1]        # half an ATR as reachable move
            cost = 2 * eng.s.cost_per_side("crypto", inst.quote_ccy)
            if abs(ob["imbalance"]) > 0.3 and exp_move > 1.5 * cost and ob["spread_bps"] < eng.s.max_spread_bps:
                out.append(sig(inst.symbol, int(np.sign(ob["imbalance"])), abs(ob["imbalance"]),
                               f"book imbalance {ob['imbalance']:+.2f}, spread {ob['spread_bps']:.1f} bps, "
                               f"expected move {exp_move:.2%} vs cost {cost:.2%}", **ob))
        return (f"{checked} order books checked, {len(out)} setups clear of costs "
                f"(execution is 60-second polling; no HFT is simulated)"), out


class SwingAgent(Agent):
    id, name, role = "swing", "Swing Trading Agent", "Trend structure, pullbacks and breakouts over hours to days"

    def run(self, eng):
        out = []
        for sym in eng.focus:
            df = eng.hub.cached_candles(BY_SYMBOL[sym], "1h")
            if df is None or len(df) < 400:
                continue
            h4 = resample(df, "4h")
            if len(h4) < 60:
                continue
            c4 = h4["close"].to_numpy(float)
            e20, e50 = ti.ema(c4, 20)[-1], ti.ema(c4, 50)[-1]
            o, h, l, c, v = _arr(df)
            r1 = ti.rsi(c)[-1]
            at = ti.atr(h, l, c)[-1]
            if e20 > e50 and c[-1] > e50 and r1 < 40:
                out.append(sig(sym, 1, 0.6, f"4h uptrend (EMA20>EMA50), 1h pullback RSI {r1:.0f}, ATR {at / c[-1]:.2%}"))
            elif e20 < e50 and c[-1] < e50 and r1 > 60:
                out.append(sig(sym, -1, 0.6, f"4h downtrend (EMA20<EMA50), 1h bounce RSI {r1:.0f}, ATR {at / c[-1]:.2%}"))
        return f"{len(out)} swing setups", out


class CryptoIntelligence(Agent):
    id, name, role = "crypto", "Crypto Intelligence", "BTC influence, altcoin relative strength, correlations, funding rates"

    def run(self, eng):
        btc = eng.hub.cached_candles(BY_SYMBOL["BTC/EUR"], "1h")
        if btc is None or len(btc) < 80:
            return "waiting for BTC history", []
        bc = btc["close"]
        btc_ret = float(bc.iloc[-1] / bc.iloc[-25] - 1)
        notes, out = [f"BTC 24h {btc_ret:+.2%}"], []
        for base in ("BTC", "ETH"):
            fr = eng.hub.funding_rate(base)
            notes.append(f"{base} funding {fr:+.4%}" if fr is not None else f"{base} funding unavailable")
        rs = []
        for inst in UNIVERSE:
            if inst.asset_class != "crypto" or inst.symbol == "BTC/EUR":
                continue
            df = eng.hub.cached_candles(inst, "1h")
            if df is None or len(df) < 80:
                continue
            c = df["close"]
            rel = float(c.iloc[-1] / c.iloc[-25] - 1) - btc_ret
            corr = float(np.log(c).diff().tail(72).corr(np.log(bc).diff().reindex(c.index).tail(72)))
            rs.append((rel, inst.symbol, corr))
        rs.sort(reverse=True)
        for rel, sym, corr in rs[:2]:
            if rel > 0.02:
                out.append(sig(sym, 1, min(1, rel * 10), f"outperforming BTC by {rel:+.2%} (24h), corr {corr:.2f}", rel=rel, corr=corr))
        for rel, sym, corr in rs[-2:]:
            if rel < -0.02:
                out.append(sig(sym, -1, min(1, -rel * 10), f"underperforming BTC by {rel:+.2%} (24h), corr {corr:.2f}", rel=rel, corr=corr))
        return "; ".join(notes) + f"; {len(rs)} altcoins ranked", out


class ForexIntelligence(Agent):
    id, name, role = "forex", "Forex Intelligence", "Currency strength, sessions, correlations (no economic-calendar provider configured)"

    @staticmethod
    def session(now: datetime) -> str:
        h = now.hour
        return "Asia" if h < 7 else "London" if h < 12 else "London/New York" if h < 16 else "New York" if h < 21 else "Asia"

    def run(self, eng):
        strength: dict[str, list[float]] = {}
        pairs = [i for i in UNIVERSE if i.asset_class == "forex"]
        for inst in pairs:
            df = eng.hub.cached_candles(inst, "1h")
            if df is None or len(df) < 30:
                continue
            c = df["close"].to_numpy(float)
            r = c[-1] / c[-25] - 1
            strength.setdefault(inst.symbol[:3], []).append(r)
            strength.setdefault(inst.symbol[3:], []).append(-r)
        if not strength:
            return "waiting for forex history", []
        avg = sorted(((np.mean(v), k) for k, v in strength.items()), reverse=True)
        strong, weak = avg[0], avg[-1]
        out = []
        if is_market_open(pairs[0], eng.now()) and strong[0] - weak[0] > 0.004:
            for inst in pairs:
                b, q = inst.symbol[:3], inst.symbol[3:]
                if (b, q) == (strong[1], weak[1]):
                    out.append(sig(inst.symbol, 1, 0.5, f"{b} strongest ({strong[0]:+.2%}), {q} weakest ({weak[0]:+.2%}) over 24h"))
                elif (b, q) == (weak[1], strong[1]):
                    out.append(sig(inst.symbol, -1, 0.5, f"{b} weakest ({weak[0]:+.2%}), {q} strongest ({strong[0]:+.2%}) over 24h"))
        ranking = ", ".join(f"{k} {v:+.2%}" for v, k in avg)
        return (f"session {self.session(eng.now())}; strength: {ranking}; economic calendar and "
                f"rate expectations: no provider configured, not used"), out


POSITIVE = {"beat", "beats", "surge", "surges", "soar", "soars", "rally", "rallies", "record", "upgrade",
            "upgraded", "raises", "raised", "growth", "profit", "strong", "jumps", "gain", "gains", "bullish",
            "outperform", "tops", "approval", "wins", "boost"}
NEGATIVE = {"miss", "misses", "plunge", "plunges", "fall", "falls", "drop", "drops", "cut", "cuts", "downgrade",
            "downgraded", "lawsuit", "probe", "recall", "weak", "loss", "losses", "slump", "bearish", "warns",
            "warning", "fraud", "investigation", "layoffs", "tumbles", "sinks", "ban"}


def headline_sentiment(title: str) -> float:
    words = {w.strip(".,:;!?'\"()").lower() for w in title.split()}
    p, n = len(words & POSITIVE), len(words & NEGATIVE)
    return 0.0 if p + n == 0 else (p - n) / (p + n)


class NewsSentiment(Agent):
    id, name, role = "news", "News & Sentiment", "Headlines with source and timestamp; keyword sentiment"
    interval = 1800.0

    def __init__(self):
        super().__init__()
        self._cursor = 0

    def run(self, eng):
        prov = eng.hub.providers.get("yahoo")
        if not hasattr(prov, "news"):
            self.status = "disabled"
            return "no news provider available", []
        pool = [i for i in UNIVERSE if i.asset_class == "equity"]
        batch = [pool[(self._cursor + k) % len(pool)] for k in range(5)]
        self._cursor = (self._cursor + 5) % len(pool)
        new, out = 0, []
        for inst in batch:
            for item in prov.news(inst)[:8]:
                with eng.db.session() as s:
                    if s.scalar(select(News.id).where(News.url == item["url"][:600])):
                        continue
                    s.add(News(ts=item["ts"], instrument=inst.symbol, title=item["title"][:400],
                               publisher=item["publisher"][:80], url=item["url"][:600],
                               sentiment=headline_sentiment(item["title"])))
                    new += 1
            with eng.db.session() as s:
                recent = list(s.scalars(select(News).where(News.instrument == inst.symbol,
                                                           News.ts >= eng.now() - timedelta(hours=6))))
            scored = [n.sentiment for n in recent if n.sentiment != 0]
            if len(scored) >= 2 and abs(np.mean(scored)) >= 0.5:
                m = float(np.mean(scored))
                out.append(sig(inst.symbol, int(np.sign(m)), abs(m) * 0.5,
                               f"{len(scored)} headlines in 6h, keyword sentiment {m:+.2f} "
                               f"(latest: {recent[-1].publisher}, {recent[-1].ts:%Y-%m-%d %H:%M} UTC)"))
        return f"{new} new headlines for {', '.join(i.symbol for i in batch)}", out


class EliteTraderIntelligence(Agent):
    id, name, role = "elite", "Elite Trader Intelligence", "Public 13F disclosures (delayed) and documented principles turned into testable hypotheses"
    interval = 86400.0

    def run(self, eng):
        families = sorted({f for p in elite.PRINCIPLES for f in p["families"]})
        if not eng.s.sec_user_agent:
            return (f"{len(elite.PRINCIPLES)} documented principles mapped to {len(families)} strategy families "
                    f"under test; 13F ingestion is off (set sec_user_agent to enable SEC EDGAR)"), []
        res = elite.EdgarProvider(eng.s.sec_user_agent, eng.db).fetch()
        return (f"{res['new_filings']} new 13F filings ingested (delayed quarter-end disclosures, never "
                f"current positions); {len(families)} families under test"), []


# ---------------------------------------------------------------------------------------
# operational agents: thin, visible wrappers around engine components
# ---------------------------------------------------------------------------------------
class StrategyOptimizer(Agent):
    id, name, role = "optimizer", "Strategy Optimizer", "Runs the 10,000-experiment lab; re-validates periodically"
    interval = 60.0

    def run(self, eng):
        st = eng.lab.status()
        if eng.lab.is_running():
            self.status = "running"
            return f"{st['phase']}: {st['completed']}/{st['target']} experiments — {st['message']}", []
        status = eng.state["status"]
        last = st.get("last_run_at")
        age_h = (eng.now() - datetime.fromisoformat(last)).total_seconds() / 3600 if last else None
        need_first = status == "running" and st["completed"] == 0 and st["phase"] in ("idle", "interrupted", "failed", "no data")
        need_relab = status == "running" and age_h is not None and age_h >= eng.s.relab_hours and st["phase"] == "complete"
        retry_due = age_h is None or age_h * 3600 > 600
        if (need_first and retry_due) or need_relab:
            eng.lab.start()
            return "started a research run", []
        return f"last run: {st['phase']} — {st['message'] or 'no run yet'}", []


class RiskManagerAgent(Agent):
    id, name, role = "risk", "Risk Manager", "Final authority: approves or rejects every proposed trade"
    interval = 60.0

    def run(self, eng):
        a = eng.broker.account()
        peak = max(eng.state.get("peak_equity") or a["equity"], a["equity"])
        dd = 1 - a["equity"] / peak if peak else 0.0
        expo = a["invested"] / a["equity"] if a["equity"] > 0 else 0.0
        note = ""
        if dd >= eng.s.max_drawdown_pct:
            note = " — NEW TRADES PAUSED (drawdown limit)"
        return (f"approved {eng.risk.approved}, rejected {eng.risk.rejected}; exposure {expo:.0%}, "
                f"drawdown {dd:.1%}{note}"), []


class PaperExecution(Agent):
    id, name, role = "execution", "Paper Execution", "Simulated fills, stops, targets, trailing stops — internal simulator only"
    interval = 60.0

    def run(self, eng):
        with eng.db.session() as s:
            n_open = s.scalar(select(func.count()).select_from(Position).where(Position.status == "open", Position.book == "live"))
            n_closed = s.scalar(select(func.count()).select_from(Position).where(Position.status == "closed", Position.book == "live"))
            n_shadow = s.scalar(select(func.count()).select_from(Position).where(Position.book == "shadow"))
        audit = eng.broker.audit()
        if not audit["ok"]:
            eng.db.incident("error", self.id, f"accounting audit mismatch: {audit}")
            raise RuntimeError("accounting audit mismatch")
        return f"{n_open} open, {n_closed} closed live trades, {n_shadow} forward-test trades; ledger audit OK", []


class PerformanceAnalyst(Agent):
    id, name, role = "performance", "Performance Analyst", "Compares live results with backtests; promotes, down-weights and retires strategies"
    interval = 120.0

    def run(self, eng):
        promoted = retired = 0
        now = eng.now()
        with eng.db.session() as s:
            strategies = list(s.scalars(select(Strategy).where(Strategy.stage != "retired")))
        for st in strategies:
            with eng.db.session() as s:
                closed = list(s.scalars(select(Position).where(Position.strategy_id == st.id,
                                                               Position.status == "closed")))
            shadow = [p for p in closed if p.book == "shadow"]
            live = [p for p in closed if p.book == "live"]
            stage, weight, note = st.stage, st.weight, st.note
            if st.stage == "forward":
                pnl = sum(p.realized_pnl_eur for p in shadow)
                hours = (now - st.created_at).total_seconds() / 3600
                if len(shadow) >= eng.s.forward_min_trades and hours >= eng.s.forward_min_hours and pnl > 0:
                    stage, note = "live", f"promoted: {len(shadow)} forward trades, net €{pnl:+.2f} on €{eng.s.shadow_notional_eur:.0f} notional"
                    promoted += 1
                elif len(shadow) >= eng.s.forward_max_trades and pnl <= 0:
                    stage, note = "retired", f"failed forward test: {len(shadow)} trades, net €{pnl:+.2f}"
                    retired += 1
            elif st.stage == "live" and live:
                pnl = sum(p.realized_pnl_eur for p in live)
                avg = float(np.mean([p.realized_pnl_eur / p.entry_notional_eur for p in live]))
                if len(live) >= eng.s.retire_min_trades and pnl < -eng.s.retire_loss_pct_of_equity * eng.s.initial_capital:
                    stage, note = "retired", f"retired: {len(live)} live trades, net €{pnl:+.2f} vs backtest {st.expected_trade_pct:+.2%}/trade"
                    retired += 1
                elif len(live) >= 3:
                    weight = 0.5 if avg < 0 else 0.75 if avg < st.expected_trade_pct / 2 else 1.0
                    note = f"live avg {avg:+.2%}/trade vs backtest {st.expected_trade_pct:+.2%}; weight {weight:.2f}"
            if (stage, weight, note) != (st.stage, st.weight, st.note):
                with eng.db.session() as s:
                    row = s.get(Strategy, st.id)
                    row.stage, row.weight, row.note, row.updated_at = stage, weight, note, now
        return f"{len(strategies)} active strategies reviewed; {promoted} promoted, {retired} retired", []


class Supervisor(Agent):
    id, name, role = "supervisor", "Autonomous Supervisor", "Watches agents, data feeds, database and risk limits; records incidents"
    interval = 60.0

    def __init__(self):
        super().__init__()
        self._down: set[str] = set()

    def run(self, eng):
        now, problems = eng.now(), []
        for name, hlt in eng.hub.health.items():
            ok = hlt["last_ok"] is not None and (now - hlt["last_ok"]).total_seconds() < 600
            if not ok and name not in self._down:
                self._down.add(name)
                eng.db.incident("error", self.id, f"data provider '{name}' is not delivering quotes: {hlt['last_error'] or 'no successful poll yet'}")
            elif ok and name in self._down:
                self._down.discard(name)
                eng.db.incident("info", self.id, f"data provider '{name}' recovered", recovered=True)
            if not ok:
                problems.append(f"{name} down")
        stale = [i.symbol for i in UNIVERSE if i.tradable and is_market_open(i, now) and not eng.hub.is_fresh(i.symbol, now)]
        if stale:
            problems.append(f"{len(stale)} open-market instruments without fresh data")
        failed = [a.id for a in eng.agents if a.status == "error"]
        if failed:
            problems.append("agents in error (will retry): " + ", ".join(failed))
        eng.db.set("heartbeat", now.isoformat())      # also proves the database is writable
        if eng.loop_lag > 3 * eng.s.cycle_seconds:
            problems.append(f"engine cycle slow ({eng.loop_lag:.0f}s)")
        return ("all systems nominal" if not problems else "; ".join(problems)), []


def build_agents() -> list[Agent]:
    agents = [MarketScanner(), TechnicalAnalyst(), MomentumTrader(), ScalpingAgent(), SwingAgent(),
              CryptoIntelligence(), ForexIntelligence(), NewsSentiment(), EliteTraderIntelligence(),
              StrategyOptimizer(), RiskManagerAgent(), PaperExecution(), PerformanceAnalyst(), Supervisor()]
    return agents
