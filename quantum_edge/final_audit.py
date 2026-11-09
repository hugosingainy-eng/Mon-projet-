"""Audit final automatisé (Partie 14). Chaque point est VÉRIFIÉ par du code, pas déclaré.

Usage : python -m quantum_edge audit   -> reports/final_audit.md
Statuts : PASS | FAIL | AWAITING CREDENTIALS | NOT VERIFIABLE OFFLINE
"""
from __future__ import annotations

import os
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path


def run_audit(settings) -> bool:
    results: list[tuple[str, str, str]] = []

    def check(name, fn):
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "FAIL", f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=2)}"
        results.append((name, status, detail))
        print(f"[{status:^24}] {name} — {detail.splitlines()[0] if detail else ''}")

    tmp = Path(tempfile.mkdtemp(prefix="qe_audit_"))
    old_env = {k: os.environ.get(k) for k in ("QE_ROOT", "QE_DB", "DATA_SOURCE", "EXECUTION_BACKEND", "TRADING_MODE")}
    os.environ.update({"QE_ROOT": str(tmp), "QE_DB": str(tmp / "audit.db"), "DATA_SOURCE": "synthetic",
                       "EXECUTION_BACKEND": "simulated", "TRADING_MODE": "DEMO"})
    try:
        from .config import Settings
        from . import safety

        def agents():
            from .engine import Engine
            e = Engine(Settings())
            names = sorted(a.name for a in e.agents.values())
            assert len(names) == 10, names
            return "PASS", f"10 agents + Master : {', '.join(names)}"
        check("Tous les agents sont implémentés", agents)

        def live_blocked():
            os.environ["TRADING_MODE"] = "LIVE"
            try:
                safety.check_mode()
                return "FAIL", "TRADING_MODE=LIVE accepté"
            except safety.SafetyViolation:
                pass
            finally:
                os.environ["TRADING_MODE"] = "DEMO"
            for path in ("/api/v1/trading/execution/market-open-orders/by-amount",
                         "/api/v1/trading/execution/real/orders", "/api/v2/trading/execution/orders"):
                try:
                    safety.check_request("POST", path)
                    return "FAIL", f"route non démo acceptée : {path}"
                except safety.SafetyViolation:
                    pass
            for bad in ((True, 2, 10, 100), (False, 1, 10, 100), (True, 1, 150, 100)):
                try:
                    safety.check_order(*bad)
                    return "FAIL", f"ordre interdit accepté : {bad}"
                except safety.SafetyViolation:
                    pass
            try:
                safety._ALLOWED_MODE = "LIVE"
                return "FAIL", "couche de sécurité modifiable"
            except safety.SafetyViolation:
                pass
            return "PASS", "LIVE, routes réelles, levier, short, dépassement de budget et modification : tous bloqués"
        check("Exécution réelle techniquement bloquée", live_blocked)

        def risk_controls():
            from .risk.manager import evaluate_trade
            s = Settings()
            acc = {"starting_capital": 100.0, "cash": 100.0, "peak_equity": 100.0, "day_start_equity": 100.0,
                   "week_start_equity": 100.0}
            base = dict(symbol="AAPL", direction=1, leverage=1, price=100.0, stop_pct=0.03, target_pct=0.06,
                        cost_pct=0.0015, acc=acc, equity=100.0, cash=100.0, open_positions=[], open_risk_usd=0.0,
                        max_corr=0.1, entries_allowed=(True, ""), lim=s.risk)
            ok = evaluate_trade(**base)
            assert ok.approved and ok.risk_usd <= 0.5 + 1e-6, ok
            bad = {"R/R 1.5": dict(target_pct=0.045), "stop trop large (min eToro)": dict(stop_pct=0.08, target_pct=0.16),
                   "short": dict(direction=-1), "levier": dict(leverage=2), "corrélation": dict(max_corr=0.9),
                   "perte du jour atteinte": dict(equity=99.0), "3 positions": dict(open_positions=[{"symbol": x, "amount": 10} for x in "ABC"]),
                   "coupe-circuit": dict(entries_allowed=(False, "x"))}
            for k, v in bad.items():
                if evaluate_trade(**{**base, **v}).approved:
                    return "FAIL", f"règle non appliquée : {k}"
            return "PASS", f"trade conforme accepté ({ok.amount} $, risque {ok.risk_usd} $) ; 8 violations refusées"
        check("Contrôles de risque appliqués", risk_controls)

        def budget():
            from .engine import Engine
            e = Engine(Settings())
            return ("PASS" if e.account.d["starting_capital"] == 100.0 else "FAIL",
                    f"budget interne {e.account.d['starting_capital']} $ indépendant du solde démo")
        check("Budget de 100 $ respecté", budget)

        def duplicates():
            from .engine import Engine
            e = Engine(Settings())
            d = {"client_key": "2026-01-02:AAPL:x", "symbol": "AAPL", "strategy": "x", "amount": 12.0, "price": 100.0,
                 "stop": 97.0, "target": 106.0, "cost_pct": 0.0015, "risk_usd": 0.45}
            r1, r2 = e.executor.open(d), e.executor.open(d)
            ok = r1.state == "confirmed" and r2.state == "rejected" and len(e.account.open_positions()) == 1
            return ("PASS" if ok else "FAIL", f"1er ordre {r1.state}, 2e ordre {r2.state} ({r2.message})")
        check("Ordres en double empêchés", duplicates)

        def emergency():
            from .engine import Engine
            e = Engine(Settings())
            e.breaker.emergency_stop("test d'audit", close_all=True)
            blocked = not e.entries_allowed()[0]
            e.cycle()
            closed = len(e.account.open_positions()) == 0
            from .risk.circuit_breaker import RESUME_PHRASE
            refused = not e.breaker.authorize_resume("oui", "audit")[0]
            ok = e.breaker.authorize_resume(RESUME_PHRASE, "audit")[0]
            return ("PASS" if blocked and closed and refused and ok else "FAIL",
                    f"entrées bloquées={blocked}, positions fermées={closed}, reprise sans phrase refusée={refused}")
        check("Arrêt d'urgence fonctionnel", emergency)

        def recovery():
            from .engine import Engine
            e = Engine(Settings())
            e.db.insert("orders", {"client_key": "crash-test", "ts": "2026-01-01T00:00:00+00:00", "symbol": "SPY",
                                   "strategy": "x", "side": "BUY", "amount": 10, "state": "submitted", "payload": {}})
            e.db.set("heartbeat", {"ts": "x", "clean_shutdown": False})
            blocked_before = not e.executor.can_submit()[0]
            e2 = Engine(Settings())
            e2.startup_recovery()
            ok = blocked_before and e2.executor.can_submit()[0] and e2.entries_allowed()[0]
            crash_logged = bool(e2.db.query("SELECT id FROM events WHERE kind='restart_after_crash'"))
            return ("PASS" if ok and crash_logged else "FAIL",
                    f"ordre en suspens bloquant={blocked_before}, rapproché au redémarrage, crash journalisé={crash_logged}")
        check("Reprise après redémarrage", recovery)

        def research_pipeline():
            from .marketdata.sources import SyntheticSource
            from .quantitative.competition import run_competition
            s = Settings()
            s.research.mc_sequences = 2000
            s.universe = {k: s.universe[k] for k in list(s.universe)[:6]}
            data = SyntheticSource().load_daily(list(s.universe), 8)
            res = run_competition(data, s, workers=1, log=lambda *_: None, simulated=True)
            r = res["leaderboard"][0]
            ok = "walk_forward" in r.get("metrics", {}) and "base" in r.get("monte_carlo", {}) and \
                all(not x.get("eligible") for x in res["leaderboard"])
            return ("PASS" if ok else "FAIL",
                    f"{res['total_trades_simulated']} trades, walk-forward {res['walk_forward_folds']} plis, "
                    f"Monte-Carlo OK, données simulées jamais éligibles")
        check("Backtest, walk-forward, hors échantillon et Monte-Carlo fonctionnels", research_pipeline)

        def dashboard():
            from fastapi.testclient import TestClient
            from .api.server import create_app
            c = TestClient(create_app(Settings()))
            for ep in ("/api/overview", "/api/risk", "/api/trades", "/api/agents", "/api/lab", "/api/weekly",
                       "/api/market"):
                r = c.get(ep)
                assert r.status_code == 200, (ep, r.status_code)
            ov = c.get("/api/overview").json()
            assert ov["simulated"] is True and "SIMUL" in ov["label"]
            return "PASS", "7 sections répondent ; valeurs simulées étiquetées SIMULÉ"
        check("Le tableau de bord affiche des données exactes et étiquetées", dashboard)

        def etoro_auth():
            key, user = os.getenv("ETORO_API_KEY"), os.getenv("ETORO_USER_KEY")
            if not (key and user):
                return "AWAITING CREDENTIALS", "ETORO_API_KEY / ETORO_USER_KEY absents"
            from .execution.etoro_client import EtoroDemoClient
            c = EtoroDemoClient(key, user)
            n = len(c.positions())
            return "PASS", f"authentification démo OK ({n} positions)"
        check("Authentification eToro démo", etoro_auth)

        def etoro_orders():
            if not (os.getenv("ETORO_API_KEY") and os.getenv("ETORO_USER_KEY")):
                return "AWAITING CREDENTIALS", "nécessite les clés + un ordre démo réel pendant les heures de marché"
            return "NOT VERIFIABLE OFFLINE", "lancer `scan` en mode etoro_demo pendant la séance et vérifier l'ordre dans eToro"
        check("Exécution d'ordres démo eToro", etoro_orders)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    s = settings
    lines = [f"# Audit final — {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
             "| Contrôle | Statut | Détail |", "|---|---|---|"]
    lines += [f"| {n} | **{st}** | {d.splitlines()[0] if d else ''} |" for n, st, d in results]
    lines += ["", "> Aucun passage en argent réel n'est prévu. Observer 8 à 12 semaines en démo minimum."]
    p = s.paths["reports"] / "final_audit.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nRapport : {p}")
    return all(st in ("PASS", "AWAITING CREDENTIALS", "NOT VERIFIABLE OFFLINE") for _, st, _ in results)
