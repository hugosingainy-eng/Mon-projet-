"""API du tableau de bord (FastAPI + WebSocket). Lecture seule, sauf l'arrêt
d'urgence et la reprise autorisée. Ne renvoie JAMAIS de clé API.
Toute valeur issue d'une simulation est étiquetée `simulated: true` / "SIMULÉ"."""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import CODE_ROOT, Settings
from ..database.db import Database
from ..quantitative.library import StrategyLibrary
from ..risk.circuit_breaker import RESUME_PHRASE, CircuitBreaker

FRONT = CODE_ROOT / "frontend" / "dashboard"


class EmergencyIn(BaseModel):
    reason: str = "arrêt depuis le tableau de bord"
    close_all: bool = True


class ResumeIn(BaseModel):
    phrase: str
    operator: str
    note: str = ""


def _j(x):
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return x
    return x


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings()
    db = Database(s.db_path)
    app = FastAPI(title="Quantum Edge AI — DÉMO", docs_url="/api/docs")

    def system():
        return db.get("system", {}) or {}

    def simulated() -> bool:
        sysi = system()
        return bool(sysi.get("simulated", True))

    def label():
        return "SIMULÉ (aucun ordre eToro)" if simulated() else "DÉMO eToro (argent virtuel)"

    def auth(token: str | None):
        if s.dashboard_token and token != s.dashboard_token:
            raise HTTPException(401, "jeton invalide")

    @app.get("/api/overview")
    def overview():
        acc = db.get("account") or {"starting_capital": s.risk.starting_capital, "cash": s.risk.starting_capital,
                                     "realized": 0.0, "fees": 0.0, "peak_equity": s.risk.starting_capital,
                                     "day_start_equity": s.risk.starting_capital,
                                     "week_start_equity": s.risk.starting_capital}
        last = db.query("SELECT * FROM equity ORDER BY id DESC LIMIT 1")
        eq = last[0]["equity"] if last else acc["cash"]
        unreal = last[0]["unrealized"] if last else 0.0
        n_open = db.query("SELECT COUNT(*) n FROM positions WHERE state='open'")[0]["n"]
        return {
            "label": label(), "simulated": simulated(), "mode": "DEMO", "system": system(),
            "starting_capital": acc["starting_capital"], "equity": eq, "balance": acc["cash"],
            "realized": acc["realized"], "unrealized": unreal, "fees": acc["fees"],
            "daily_pnl": eq - acc["day_start_equity"], "weekly_pnl": eq - acc["week_start_equity"],
            "total_return": eq / acc["starting_capital"] - 1,
            "drawdown": 1 - eq / acc["peak_equity"] if acc["peak_equity"] else 0.0,
            "open_positions": n_open, "last_update": last[0]["ts"] if last else None,
            "heartbeat": db.get("heartbeat"), "breaker": db.get("breaker"), "emergency": db.get("emergency"),
            "recovery": db.get("recovery"),
        }

    @app.get("/api/equity")
    def equity():
        return {"simulated": simulated(),
                "points": db.query("SELECT ts, equity, drawdown FROM equity ORDER BY id DESC LIMIT 2000")[::-1]}

    @app.get("/api/market")
    def market():
        scan = db.query("SELECT * FROM scans ORDER BY id DESC LIMIT 1")
        snap = db.get("market_snapshot", {})
        rows = []
        if scan:
            for d in db.query("SELECT symbol, strategy, decision, confidence, payload FROM decisions WHERE scan_id=?",
                              (scan[0]["id"],)):
                p = _j(d["payload"])
                ag = p.get("agents", {})
                rows.append({"symbol": d["symbol"], "strategy": d["strategy"], "decision": d["decision"],
                             "regime": ag.get("1_regime", {}).get("details", {}).get("market_regime"),
                             "volatility": ag.get("1_regime", {}).get("details", {}).get("volatility_state"),
                             "technical": ag.get("2_technical", {}).get("conclusion"),
                             "price": p.get("entry_conditions")})
        return {"simulated": simulated(), "last_scan": scan[0] if scan else None, "opportunities": rows,
                "prices": snap}

    @app.get("/api/agents")
    def agents():
        scan = db.query("SELECT * FROM scans WHERE n_candidates > 0 ORDER BY id DESC LIMIT 1") or \
            db.query("SELECT * FROM scans ORDER BY id DESC LIMIT 1")
        if not scan:
            return {"scan": None, "decisions": []}
        out = []
        for d in db.query("SELECT * FROM decisions WHERE scan_id=?", (scan[0]["id"],)):
            p = _j(d["payload"])
            out.append({"symbol": d["symbol"], "strategy": d["strategy"], "decision": d["decision"],
                        "authorized": bool(d["authorized"]), "confidence": d["confidence"],
                        "reasons": p.get("reasons", []), "disagreements": p.get("agent_disagreements", []),
                        "checks": p.get("checks", {}),
                        "agents": [{"agent": k, "vote": v["vote"], "conclusion": v["conclusion"],
                                    "confidence": v["confidence"]} for k, v in p.get("agents", {}).items()]})
        return {"scan": scan[0], "decisions": out, "simulated": simulated()}

    @app.get("/api/trades")
    def trades():
        pos = db.query("SELECT id, symbol, strategy, entry, units, amount, stop, target, opened_ts, state, exit, "
                       "exit_ts, reason, pnl, fees, r, risk_usd, regime, hypothesis, simulated, broker_position_id "
                       "FROM positions ORDER BY id DESC LIMIT 500")
        for p in pos:
            p["hypothesis"] = _j(p["hypothesis"])
        return {"simulated": simulated(), "positions": pos,
                "orders": db.query("SELECT client_key, ts, symbol, amount, state, broker_order_id FROM orders "
                                   "ORDER BY id DESC LIMIT 200")}

    @app.get("/api/lab")
    def lab():
        lib_real = StrategyLibrary(s.paths["research"], simulated=False)
        lib_sim = StrategyLibrary(s.paths["research"], simulated=True)
        run = lib_real.latest_run()
        return {"latest_run": {k: v for k, v in (run or {}).items() if k != "equity_curve"} if run else None,
                "production": lib_real.production(), "production_simulated": lib_sim.production(),
                "last_backtest": db.get("last_backtest")}

    @app.get("/api/risk")
    def risk():
        acc = db.get("account") or {}
        last = db.query("SELECT * FROM equity ORDER BY id DESC LIMIT 1")
        eq = last[0]["equity"] if last else acc.get("cash", s.risk.starting_capital)
        cap = acc.get("starting_capital", s.risk.starting_capital)
        L = s.risk
        return {
            "simulated": simulated(),
            "limits": {"risk_per_trade": L.risk_per_trade * cap, "daily_loss": L.daily_loss * cap,
                       "weekly_loss": L.weekly_loss * cap, "max_drawdown": L.max_drawdown * cap,
                       "max_positions": L.max_positions, "min_reward_risk": L.min_reward_risk,
                       "max_correlation": L.max_correlation, "leverage": 1, "shorts": False},
            "usage": {"daily_loss": max(0.0, acc.get("day_start_equity", eq) - eq),
                      "weekly_loss": max(0.0, acc.get("week_start_equity", eq) - eq),
                      "drawdown": max(0.0, acc.get("peak_equity", eq) - eq)},
            "portfolio": db.get("portfolio_risk", {}), "breaker": db.get("breaker"), "emergency": db.get("emergency"),
            "resume_phrase": RESUME_PHRASE,
            "events": db.query("SELECT ts, level, kind, message FROM events WHERE level IN ('critical','error','warning') "
                               "ORDER BY id DESC LIMIT 50"),
        }

    @app.get("/api/weekly")
    def weekly():
        w = db.get("last_weekly")
        closed = db.query("SELECT pnl, r, strategy FROM positions WHERE state='closed' AND exit_ts >= datetime('now','-7 days')")
        rej = db.query("SELECT COUNT(*) n FROM decisions WHERE authorized=0 AND ts >= datetime('now','-7 days')")[0]["n"]
        return {"simulated": simulated(), "last_report": w, "live_week": {"closed": closed, "rejected": rej}}

    @app.post("/api/emergency-stop")
    def emergency_stop(body: EmergencyIn, x_dashboard_token: str | None = Header(default=None)):
        auth(x_dashboard_token)
        CircuitBreaker(db).emergency_stop(body.reason, body.close_all)
        return {"ok": True, "message": "Arrêt d'urgence enregistré : appliqué au prochain cycle du bot."}

    @app.post("/api/resume")
    def resume(body: ResumeIn, x_dashboard_token: str | None = Header(default=None)):
        auth(x_dashboard_token)
        ok, msg = CircuitBreaker(db).authorize_resume(body.phrase, body.operator, body.note)
        if not ok:
            raise HTTPException(400, msg)
        return {"ok": True, "message": msg}

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        try:
            while True:
                await sock.send_json({"overview": overview(), "risk": risk()})
                await asyncio.sleep(5)
        except (WebSocketDisconnect, RuntimeError):
            return

    if FRONT.exists():
        app.mount("/static", StaticFiles(directory=FRONT), name="static")

        @app.get("/")
        def index():
            return FileResponse(FRONT / "index.html")

    return app


app = create_app()
