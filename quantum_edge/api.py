"""FastAPI application: dashboard API, WebSocket and static frontend.

There is deliberately no endpoint that accepts an order: trades can only originate inside
the engine, pass the Risk Manager and be filled by the internal paper broker."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from . import __version__, elite, report
from .broker import PaperBroker
from .config import ROOT, Settings, load_settings
from .db import Decision, EquitySnapshot, Incident, News, Position, Signal
from .engine import Engine
from .instruments import BY_SYMBOL, UNIVERSE, is_market_open

ACTIONS = ("start", "pause", "resume", "stop", "emergency_stop", "run_experiments", "reset")


def create_app(settings: Settings | None = None, providers: dict | None = None,
               run_engine: bool = True) -> FastAPI:
    settings = settings or load_settings()
    eng = Engine(settings, providers)

    @asynccontextmanager
    async def lifespan(_app):
        if run_engine:
            eng.start_thread()
        yield
        eng.shutdown()

    app = FastAPI(title="Quantum Edge AI", version=__version__, lifespan=lifespan)
    app.state.engine = eng
    db = eng.db

    @app.get("/api/health")
    def health():
        return {"ok": True, "mode": settings.trading_mode, "version": __version__}

    @app.get("/api/state")
    def state():
        return eng.state_view()

    @app.get("/api/positions")
    def positions():
        out = []
        for p in eng.broker.open_positions("live"):
            value = PaperBroker.value(p)
            costs = p.fees_eur + p.fx_cost_eur
            out.append({"id": p.id, "instrument": p.instrument, "name": BY_SYMBOL[p.instrument].name,
                        "asset_class": p.asset_class, "side": "long" if p.side == 1 else "short", "qty": p.qty,
                        "entry_price": p.entry_price, "current_price": p.last_price, "currency": p.quote_ccy,
                        "entry_notional_eur": p.entry_notional_eur, "value_eur": value,
                        "unrealized_pnl_eur": value - p.entry_notional_eur - costs,
                        "unrealized_pct": (value - p.entry_notional_eur - costs) / p.entry_notional_eur * 100,
                        "stop_price": p.stop_price, "take_profit": p.take_profit, "strategy_id": p.strategy_id,
                        "strategy": p.strategy_name, "opened_at": p.opened_at.isoformat()})
        return out

    @app.get("/api/trades")
    def trades(limit: int = 200):
        with db.session() as s:
            rows = s.scalars(select(Position).where(Position.book == "live", Position.status == "closed")
                             .order_by(Position.closed_at.desc()).limit(min(limit, 2000))).all()
            return [report.trade_row(p) for p in rows]

    @app.get("/api/equity")
    def equity():
        with db.session() as s:
            rows = s.scalars(select(EquitySnapshot).order_by(EquitySnapshot.ts)).all()
        step = max(1, len(rows) // 1500)
        rows = rows[::step] + (rows[-1:] if rows and (len(rows) - 1) % step else [])
        return [{"ts": r.ts.isoformat(), "equity": r.equity, "cash": r.cash} for r in rows]

    @app.get("/api/market")
    def market():
        now, out = eng.now(), []
        for inst in UNIVERSE:
            q = eng.hub.quote(inst.symbol)
            stats = eng.market_stats.get(inst.symbol, {})
            out.append({"instrument": inst.symbol, "name": inst.name, "asset_class": inst.asset_class,
                        "tradable": inst.tradable, "price": q.price if q else None,
                        "bid": q.bid if q else None, "ask": q.ask if q else None,
                        "change_pct": q.change_pct if q else None, "volume": q.volume if q else None,
                        "volatility_pct": stats.get("volatility_pct"), "regime": stats.get("regime"),
                        "provider": q.source if q else inst.provider, "currency": inst.quote_ccy,
                        "last_update": q.ts.isoformat() if q else None, "market_open": is_market_open(inst, now),
                        "stale": not eng.hub.is_fresh(inst.symbol, now), "note": inst.note})
        return out

    @app.get("/api/lab/top")
    def lab_top(limit: int = 20):
        return report.lab_top(db, min(limit, 200))

    @app.get("/api/lab/summary")
    def lab_summary():
        return report.lab_summary(db)

    @app.get("/api/strategies")
    def strategies():
        return report.strategy_rows(db)

    @app.get("/api/agents")
    def agents():
        return [a.info() for a in eng.agents]

    def _recent(model, limit, fn):
        with db.session() as s:
            return [fn(r) for r in s.scalars(select(model).order_by(model.ts.desc()).limit(min(limit, 1000)))]

    @app.get("/api/signals")
    def signals(limit: int = 100):
        return _recent(Signal, limit, lambda r: {"ts": r.ts.isoformat(), "agent": r.agent, "instrument": r.instrument,
                                                 "direction": r.direction, "confidence": r.confidence, "summary": r.summary})

    @app.get("/api/decisions")
    def decisions(limit: int = 100):
        return _recent(Decision, limit, lambda r: {"ts": r.ts.isoformat(), "instrument": r.instrument, "side": r.side,
                                                   "strategy": r.strategy, "approved": r.approved, "reason": r.reason,
                                                   "notional_eur": r.notional_eur})

    @app.get("/api/incidents")
    def incidents(limit: int = 100):
        return _recent(Incident, limit, lambda r: {"ts": r.ts.isoformat(), "severity": r.severity,
                                                   "component": r.component, "message": r.message, "recovered": r.recovered})

    @app.get("/api/news")
    def news(limit: int = 50):
        return _recent(News, limit, lambda r: {"ts": r.ts.isoformat(), "instrument": r.instrument, "title": r.title,
                                               "publisher": r.publisher, "url": r.url, "sentiment": r.sentiment})

    @app.get("/api/elite")
    def elite_view():
        return elite.snapshot(db)

    @app.get("/api/report")
    def report_json():
        return JSONResponse(report.build(eng))

    @app.get("/api/report.html")
    def report_html():
        return HTMLResponse(report.to_html(report.build(eng)),
                            headers={"Content-Disposition": 'attachment; filename="quantum_edge_report.html"'})

    @app.post("/api/control/{action}")
    def control(action: str, body: dict | None = Body(default=None)):
        if action not in ACTIONS:
            return {"ok": False, "message": f"unknown action '{action}'"}
        ok, message = eng.control(action, confirm=bool((body or {}).get("confirm")))
        return {"ok": ok, "message": message}

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        try:
            while True:
                data = await asyncio.to_thread(eng.state_view)
                await sock.send_json({"type": "state", "data": data})
                await asyncio.sleep(2)
        except (WebSocketDisconnect, RuntimeError):
            pass

    dist = ROOT / "frontend" / "dist"
    if (dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="dashboard")
    return app
