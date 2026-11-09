"""Ligne de commande de Quantum Edge AI.

  python -m quantum_edge research            # compétition des stratégies (gratuit, Yahoo)
  python -m quantum_edge backtest            # backtest portefeuille sur la période de test
  python -m quantum_edge scan --now          # un scan immédiat (aucun ordre si marché fermé)
  python -m quantum_edge run                 # bot autonome (lun-ven)
  python -m quantum_edge dashboard           # tableau de bord http://127.0.0.1:8000
  python -m quantum_edge status | emergency-stop | resume | etoro-check | audit | report
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _settings(args):
    from .config import Settings

    if getattr(args, "data", None):
        os.environ["DATA_SOURCE"] = args.data
    return Settings()


def cmd_research(args):
    from .marketdata.sources import make_source
    from .quantitative.competition import run_competition
    from .quantitative.library import StrategyLibrary
    from .reports import research_report

    s = _settings(args)
    src = make_source(s.data_source, s)
    data = src.load_daily(list(s.universe), s.research.history_years)
    if s.benchmark not in data:
        sys.exit(f"Benchmark {s.benchmark} indisponible : impossible de continuer.")
    res = run_competition(data, s, workers=args.workers or max(1, (os.cpu_count() or 2) - 1),
                          simulated=src.simulated)
    lib = StrategyLibrary(s.paths["research"], simulated=src.simulated)
    p = lib.save_run(res)
    changes = lib.promote(res)
    rp = research_report(res, s.paths["reports"] / "research" / f"{p.stem}.md")
    print("\n".join(["", "Changements de production :"] + [f"  - {c}" for c in changes or ["aucun"]]))
    print(f"Résultats : {p}\nRapport   : {rp}")


def cmd_backtest(args):
    from .backtest import print_report, run_portfolio_backtest

    from .database.db import Database

    s = _settings(args)
    r = run_portfolio_backtest(s)
    print_report(r)
    curve = r.pop("equity_curve")
    r["equity_curve"] = [[str(d.date()), round(float(v), 4)] for d, v in curve.items()]
    Database(s.db_path).set("last_backtest", r)


def cmd_scan(args):
    from .engine import Engine

    e = Engine(_settings(args))
    e.startup_recovery()
    e.scan(require_open=not args.now)


def cmd_run(args):
    from .engine import Engine

    Engine(_settings(args)).run_forever()


def cmd_dashboard(args):
    import uvicorn

    host = args.host
    # Dans Docker, le port est publié uniquement sur 127.0.0.1 de la machine hôte (QE_IN_DOCKER=1).
    if host not in ("127.0.0.1", "localhost") and not os.getenv("DASHBOARD_TOKEN") and not os.getenv("QE_IN_DOCKER"):
        sys.exit("Refus : exposer le tableau de bord sur le réseau exige DASHBOARD_TOKEN.")
    uvicorn.run("quantum_edge.api.server:app", host=host, port=args.port, log_level="warning")


def cmd_status(args):
    from .config import Settings
    from .database.db import Database

    s = Settings()
    db = Database(s.db_path)
    print(json.dumps({"system": db.get("system"), "account": db.get("account"), "breaker": db.get("breaker"),
                      "emergency": db.get("emergency"),
                      "open_positions": db.query("SELECT symbol, amount, entry, stop, target FROM positions WHERE state='open'"),
                      "pending_orders": db.query("SELECT client_key, state FROM orders WHERE state IN ('intent','submitted','uncertain')")},
                     indent=2, ensure_ascii=False, default=str))


def cmd_emergency(args):
    from .config import Settings
    from .database.db import Database
    from .risk.circuit_breaker import CircuitBreaker

    CircuitBreaker(Database(Settings().db_path)).emergency_stop(args.reason, close_all=not args.keep_positions)
    print("Arrêt d'urgence enregistré. Le bot fermera les positions au prochain cycle." if not args.keep_positions
          else "Arrêt d'urgence enregistré (positions conservées).")


def cmd_resume(args):
    from .config import Settings
    from .database.db import Database
    from .risk.circuit_breaker import RESUME_PHRASE, CircuitBreaker

    print(f"Pour autoriser la reprise, tape exactement : {RESUME_PHRASE}")
    phrase = input("> ")
    operator = input("Ton nom : ")
    ok, msg = CircuitBreaker(Database(Settings().db_path)).authorize_resume(phrase, operator, args.note)
    print(msg)


def cmd_etoro_check(args):
    from .etoro_check import run_check

    run_check(_settings(args))


def cmd_audit(args):
    from .final_audit import run_audit

    sys.exit(0 if run_audit(_settings(args)) else 1)


def cmd_report(args):
    from .engine import Engine
    from .reports import daily_report, weekly_report

    e = Engine(_settings(args))
    print(daily_report(e))
    print(weekly_report(e))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="quantum_edge", description="Quantum Edge AI — trading multi-agents (DÉMO)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in [("research", cmd_research), ("backtest", cmd_backtest), ("scan", cmd_scan), ("run", cmd_run),
                     ("status", cmd_status), ("etoro-check", cmd_etoro_check), ("audit", cmd_audit),
                     ("report", cmd_report)]:
        p = sub.add_parser(name)
        p.add_argument("--data", choices=["yahoo", "etoro", "csv", "synthetic"])
        p.add_argument("--workers", type=int)
        p.add_argument("--now", action="store_true", help="scan immédiat, même marché fermé (aucun ordre réel)")
        p.set_defaults(fn=fn)
    p = sub.add_parser("dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(fn=cmd_dashboard)
    p = sub.add_parser("emergency-stop")
    p.add_argument("--reason", default="arrêt manuel")
    p.add_argument("--keep-positions", action="store_true")
    p.set_defaults(fn=cmd_emergency)
    p = sub.add_parser("resume")
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_resume)
    args = ap.parse_args(argv)
    args.fn(args)
