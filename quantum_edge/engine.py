"""Moteur principal : relie données, agents, risque, exécution, base de données.

Cycle (toutes les 5 minutes, du lundi au vendredi) :
  arrêt d'urgence ? -> rapprochement -> surveillance des positions -> limites de
  perte / coupe-circuit -> instantané du capital -> scan quotidien 25 min avant
  la clôture de New York -> rapports quotidien / hebdomadaire -> sauvegarde.
Au démarrage : mode RÉCUPÉRATION (aucune entrée tant que le rapprochement n'a pas réussi).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd

from . import safety
from .agents.macro import MacroAgent
from .agents.master import Candidate, decide
from .agents.quant import QuantAgent
from .agents.regime import RegimeAgent
from .agents.sentiment import SentimentAgent
from .agents.specialists import (ExecutionAgentChecks, MonteCarloAgent, PerformanceAuditorAgent,
                                 RiskManagerAgent, StrategyTesterAgent)
from .agents.technical import TechnicalAgent
from .config import CODE_ROOT, SLIPPAGE_PER_SIDE, Settings
from .database.db import Database, now_iso
from .execution import market_hours as mh
from .execution.brokers import EtoroDemoBroker, SimulatedBroker
from .execution.executor import Executor
from .marketdata.quality import check_daily
from .marketdata.sources import make_source
from .ops import Alerter, clock_status, setup_logging
from .quantitative.library import StrategyLibrary
from .quantitative.setup_history import conditional_paths
from .risk.account import Account
from .risk.circuit_breaker import CircuitBreaker
from .risk.manager import limit_breaches
from .risk.portfolio import max_correlation, portfolio_risk
from .strategies.catalog import FAMILY_BY_NAME, compute_signals
from . import indicators as ind


class AwaitingCredentials(RuntimeError):
    pass


class Engine:
    def __init__(self, settings: Settings | None = None, offline: bool = False):
        safety.check_mode()
        self.s = s = settings or Settings()
        self.paths = s.paths
        self.db = Database(s.db_path)
        self.log_ = setup_logging(self.paths["logs"])
        self.alert = Alerter(self.db, self.log_, s.telegram_token, s.telegram_chat_id)
        self.simulated_data = s.data_source == "synthetic"
        self.offline = offline or self.simulated_data
        self.client = None
        if s.etoro_api_key and s.etoro_user_key:
            from .execution.etoro_client import EtoroDemoClient
            self.client = EtoroDemoClient(s.etoro_api_key, s.etoro_user_key, s.etoro_base_url)
        if s.execution_backend == "etoro_demo":
            if self.client is None:
                raise AwaitingCredentials("EXECUTION_BACKEND=etoro_demo mais ETORO_API_KEY / ETORO_USER_KEY absents.")
            self.broker = EtoroDemoBroker(self.client)
        else:
            self.broker = SimulatedBroker(SLIPPAGE_PER_SIDE)
        if s.data_source == "etoro" and self.client is None:
            raise AwaitingCredentials("DATA_SOURCE=etoro nécessite les clés API eToro.")
        self.source = make_source(s.data_source, s, self.client)
        self.account = Account(self.db, s.risk.starting_capital, self.broker.simulated or self.simulated_data)
        self.breaker = CircuitBreaker(self.db, self.alert)
        self.executor = Executor(self.db, self.account, self.broker, s, self.log, self.alert)
        self.library = StrategyLibrary(self.paths["research"], simulated=self.simulated_data)
        grok = None
        if s.xai_api_key:
            from .agents.grok import GrokAgent
            grok = GrokAgent(s.xai_api_key)
        self.agents = {
            "regime": RegimeAgent(), "technical": TechnicalAgent(), "quant": QuantAgent(),
            "macro": MacroAgent(CODE_ROOT / "config" / "macro_events.csv", offline=self.offline),
            "sentiment": SentimentAgent(grok, offline=self.offline), "tester": StrategyTesterAgent(),
            "mc": MonteCarloAgent(), "risk": RiskManagerAgent(), "execution": ExecutionAgentChecks(),
            "auditor": PerformanceAuditorAgent(),
        }
        self.db.set("system", {"mode": "DEMO", "backend": self.broker.name, "data_source": s.data_source,
                               "simulated": self.account.simulated, "started": now_iso()})

    def log(self, msg: str):
        self.log_.info(safety.redact(msg))

    # ------------------------------------------------------------ données
    def load(self, years: int = 3) -> dict:
        return self.source.load_daily(list(self.s.universe), years, log=self.log)

    @staticmethod
    def bars_from(data: dict) -> dict:
        return {s: {"price": float(df["close"].iloc[-1]), "high": float(df["high"].iloc[-1]),
                    "low": float(df["low"].iloc[-1]), "bar_date": str(df.index[-1].date())} for s, df in data.items()}

    # ------------------------------------------------------------ récupération
    def startup_recovery(self, prices: dict | None = None):
        hb = self.db.get("heartbeat")
        if hb and not hb.get("clean_shutdown"):
            self.db.event("warning", "restart_after_crash", f"redémarrage après arrêt non propre ({hb.get('ts')})")
            self.alert("Redémarrage après un arrêt inattendu : rapprochement des positions avant toute entrée.")
        self.db.set("recovery", {"active": True, "since": now_iso()})
        try:
            rep = self.executor.reconcile(prices or {})
            self.db.event("info", "reconcile", "rapprochement au démarrage", rep)
            self.db.set("recovery", {"active": False, "done": now_iso(), "report": rep})
            self.log(f"[récupération] rapprochement terminé : {rep}")
        except Exception as e:
            self.db.event("error", "reconcile_failed", f"{type(e).__name__}: {e}")
            self.log(f"[récupération] ÉCHEC du rapprochement ({e}) : entrées bloquées")

    def entries_allowed(self) -> tuple[bool, str]:
        rec = self.db.get("recovery", {})
        if rec.get("active"):
            return False, "mode récupération : rapprochement non terminé"
        return self.breaker.entries_allowed()

    # ------------------------------------------------------------ risque global
    def update_risk_state(self, prices: dict, now: datetime):
        if self.db.get("resume_pending_baseline_reset"):
            self.account.reset_baselines(prices)
            self.db.set("resume_pending_baseline_reset", False)
        acc = self.account.roll_periods(prices, now)
        eq = self.account.equity(prices)
        breaches = limit_breaches(acc, eq, self.s.risk)
        if breaches and not self.breaker.state["tripped"]:
            self.breaker.trip("; ".join(breaches), {"equity": eq})
            try:
                self.executor.reconcile(prices)
            except Exception as e:
                self.db.event("error", "reconcile_failed", str(e))
        return acc, eq

    # ------------------------------------------------------------ scan
    def scan(self, data: dict | None = None, require_open: bool | None = None, now: datetime | None = None) -> list:
        t0 = time.time()
        now = now or datetime.now(timezone.utc)
        require_open = (not self.offline) if require_open is None else require_open
        data = data or self.load(3)
        bars = self.bars_from(data)
        self.db.set("market_snapshot", bars)
        prices = {k: v["price"] for k, v in bars.items()}
        acc, eq = self.update_risk_state(prices, now)
        prod = self.library.production_specs()
        scan_id = self.db.insert("scans", {"ts": now_iso(), "simulated": int(self.account.simulated),
                                           "n_candidates": 0, "n_approved": 0, "mc_paths": 0, "seconds": 0})
        if not prod:
            self.log("[scan] aucune stratégie validée en production : NO TRADE (lance d'abord `research`).")
            self.db.update("scans", {"id": scan_id}, {"summary": "aucune stratégie validée"})
            return []
        bench = data.get(self.s.benchmark)
        ctx = {"bench": bench}
        cands = []
        for spec, entry in prod:
            fam = FAMILY_BY_NAME[spec.family]
            for sym, df in data.items():
                sig = compute_signals(spec, df, ctx)
                if not bool(sig["entry"].iloc[-1]):
                    continue
                price = float(df["close"].iloc[-1])
                cands.append((Candidate(
                    symbol=sym, strategy_id=spec.id, strategy_label=spec.label(), family=spec.family,
                    inspired_by=fam.inspired_by, hypothesis=fam.hypothesis, price=price,
                    stop_pct=float(sig["stop_dist"].iloc[-1]) / price, target_pct=float(sig["target_dist"].iloc[-1]) / price,
                    vol=float(ind.realized_vol(df["close"], 20).iloc[-1]), cost_pct=self.s.cost_for(sym),
                    date=str(df.index[-1].date())), spec, entry))
        cands.sort(key=lambda x: -x[2].get("score", 0))
        self.log(f"[scan] {len(cands)} signaux sur {len(data)} actifs et {len(prod)} stratégies validées")
        clock = clock_status(self.client) if not self.offline else {"verified": False, "blocking": False,
                                                                      "source": "hors ligne"}
        decisions, paths = [], 0
        seq_mc = (self.library.latest_run() or {}).get("leaderboard", [])
        seq_by_family = {r["family"]: r.get("monte_carlo", {}).get("base") for r in seq_mc}
        for cand, spec, entry in cands:
            md = self.evaluate(cand, spec, entry, data, ctx, clock, require_open, now, seq_by_family)
            paths += next((r.details["trade"]["paths"] for r in md.reports if r.agent == "7_monte_carlo"), 0)
            rec = md.to_record(md.amount * cand.cost_pct)
            self.db.insert("decisions", {"ts": now_iso(), "scan_id": scan_id, "symbol": cand.symbol,
                                         "strategy": cand.strategy_label, "decision": md.decision,
                                         "authorized": int(md.authorized), "confidence": md.confidence, "payload": rec})
            for r in md.reports:
                self.db.insert("agent_reports", {"ts": now_iso(), "scan_id": scan_id, "agent": r.agent,
                                                 "symbol": cand.symbol, "status": r.vote, "conclusion": r.conclusion,
                                                 "confidence": r.confidence, "payload": r.details})
            verdict = "✅ BUY" if md.authorized else f"❌ {md.decision}"
            self.log(f"  {verdict} {cand.symbol:5s} {cand.family:20s} conf={md.confidence:.2f} "
                     + ("" if md.authorized else "| " + "; ".join(md.reasons[:3])))
            if md.authorized:
                res = self.executor.open({
                    "client_key": f"{cand.date}:{cand.symbol}:{cand.strategy_id}", "symbol": cand.symbol,
                    "strategy": cand.strategy_label, "amount": md.amount, "price": cand.price,
                    "stop": cand.stop_price, "target": cand.target_price, "cost_pct": cand.cost_pct,
                    "risk_usd": md.risk_usd, "bar_date": cand.date,
                    "regime": md.reports[0].details.get("market_regime", ""),
                    "hypothesis": {"family": cand.family, "text": cand.hypothesis, "inspired_by": cand.inspired_by},
                    "agents": {r.agent: {"vote": r.vote, "conclusion": r.conclusion} for r in md.reports},
                })
                if res.state != "confirmed":
                    self.log(f"  [exécution] {cand.symbol}: {res.state} — {res.message}")
            decisions.append(md)
        self.db.update("scans", {"id": scan_id}, {
            "n_candidates": len(cands), "n_approved": sum(d.authorized for d in decisions), "mc_paths": paths,
            "seconds": round(time.time() - t0, 1)})
        self.account.snapshot(prices)
        self.log(f"[scan] terminé : {sum(d.authorized for d in decisions)} trade(s) autorisé(s) sur {len(cands)}, "
                 f"{paths:,} trajectoires Monte-Carlo, {time.time() - t0:.1f}s")
        return decisions

    def evaluate(self, cand, spec, entry, data, ctx, clock, require_open, now, seq_by_family):
        s = self.s
        sym = cand.symbol
        df = data[sym]
        ts = pd.Timestamp(now)
        q = check_daily(df, ts.tz_convert(None) if ts.tzinfo else ts, s.max_data_age_days)
        reports = {}
        reports["1_regime"] = self.agents["regime"].analyze(sym, df, ctx["bench"], entry.get("allowed_regimes", []))
        intraday = {}
        if not self.offline:
            for tf in ("4h", "1h", "15m", "5m"):
                try:
                    intraday[tf] = self.source.intraday(sym, tf)
                except Exception:
                    intraday[tf] = None
        else:
            intraday = {tf: self.source.intraday(sym, tf) for tf in ("4h", "1h", "15m", "5m")}
        reports["2_technical"] = self.agents["technical"].analyze(sym, df, intraday, require_intraday=True)
        cond_z, n_own, n_pool = conditional_paths(spec, data, ctx, sym, s.sim.horizon_bars)
        reports["3_quant"] = self.agents["quant"].analyze(sym, entry, n_own, n_pool, df.index[-1])
        reports["4_macro"] = self.agents["macro"].analyze(sym, s.asset_class(sym), s.sim.horizon_bars,
                                                          s.require_earnings_check and not self.offline,
                                                          now.date())
        reports["5_sentiment"] = self.agents["sentiment"].analyze(sym, df, cand, s.sim.horizon_bars)
        reports["6_strategy_tester"] = self.agents["tester"].analyze(sym, entry)
        reports["7_monte_carlo"] = self.agents["mc"].analyze(
            sym, df, cand.stop_pct, cand.target_pct, cand.vol, cand.cost_pct, cond_z, s.sim.candidate_paths,
            s.sim.horizon_bars, s.sim.shrinkage, s.sim.min_expected_r, s.sim.max_p_big_loss,
            seq_by_family.get(cand.family))
        prices = {k: float(v["close"].iloc[-1]) for k, v in data.items()}
        acc = self.account.d
        eq = self.account.equity(prices)
        open_pos = self.account.open_positions()
        corr, _ = max_correlation(data, sym, [p["symbol"] for p in open_pos])
        open_risk = sum(max(0.0, p["units"] * (prices.get(p["symbol"], p["entry"]) - p["stop"])) for p in open_pos)
        rep_risk, verdict = self.agents["risk"].analyze(
            sym, direction=cand.direction, leverage=1, price=cand.price, stop_pct=cand.stop_pct,
            target_pct=cand.target_pct, cost_pct=cand.cost_pct, acc=acc, equity=eq, cash=acc["cash"],
            open_positions=open_pos, open_risk_usd=open_risk, max_corr=corr,
            entries_allowed=self.entries_allowed(), lim=s.risk)
        reports["8_risk_manager"] = rep_risk
        inst = (True, "simulé : non vérifié chez eToro")
        if self.client is not None:
            try:
                inst = (True, f"instrumentId {self.client.instrument_id(sym)}")
            except Exception as e:
                inst = (False, f"{type(e).__name__}: {e}")
        reports["9_execution"] = self.agents["execution"].analyze(
            sym, inst, mh.is_market_open(now), self.executor.can_submit(), clock, require_open)
        if sym in {p["symbol"] for p in open_pos}:
            md = decide(cand, reports, {"fresh": q.fresh, "quality": q.ok}, verdict)
            md.decision, md.authorized, md.amount = "HOLD", False, 0.0
            md.reasons.insert(0, "position déjà ouverte sur cet actif")
            return md
        return decide(cand, reports, {"fresh": q.fresh, "quality": q.ok}, verdict)

    # ------------------------------------------------------------ cycle
    def cycle(self, now: datetime | None = None, data: dict | None = None):
        now = now or datetime.now(timezone.utc)
        em = self.breaker.emergency
        data = data or self.load(2)
        bars = self.bars_from(data)
        self.db.set("market_snapshot", bars)
        prices = {k: v["price"] for k, v in bars.items()}
        if em["active"] and em["close_all"]:
            self.executor.close_all(prices, "arrêt d'urgence")
            self.breaker.acknowledge_close_all()
        try:
            rep = self.executor.reconcile(prices)
            if rep.get("closed_by_broker") or rep.get("confirmed") or rep.get("failed"):
                self.db.event("info", "reconcile", "rapprochement", rep)
        except Exception as e:
            self.db.event("error", "reconcile_failed", f"{type(e).__name__}: {e}")
        self.executor.monitor(bars, self.s.sim.horizon_bars)
        self.update_risk_state(prices, now)
        self.account.snapshot(prices)
        try:
            self.db.set("portfolio_risk", self.portfolio_risk(data))
        except Exception as e:
            self.db.event("error", "portfolio_risk", str(e))
        self.db.set("heartbeat", {"ts": now_iso(), "clean_shutdown": False})
        return prices

    def run_forever(self):
        from .reports import daily_report, weekly_report

        self.log(f"Quantum Edge AI démarré — MODE DÉMO — exécution : {self.broker.name} — "
                 f"budget {self.s.risk.starting_capital:.0f} $")
        self.startup_recovery()
        try:
            while True:
                now = datetime.now(timezone.utc)
                ny = mh.ny_now(now)
                try:
                    if mh.is_trading_day(ny.date()):
                        self.cycle(now)
                        day = ny.strftime("%Y-%m-%d")
                        if (ny.hour, ny.minute) >= self.s.scan_time_ny and self.db.get("last_scan_day") != day \
                                and mh.is_market_open(now):
                            self.scan(now=now)
                            self.db.set("last_scan_day", day)
                        if (ny.hour, ny.minute) >= self.s.report_time_ny and self.db.get("last_report_day") != day:
                            daily_report(self)
                            if ny.weekday() == 4:
                                weekly_report(self)
                            self.db.backup(self.paths["data"] / "backups")
                            self.db.set("last_report_day", day)
                    else:
                        self.db.set("heartbeat", {"ts": now_iso(), "clean_shutdown": False})
                except Exception as e:
                    self.db.event("error", "cycle_error", safety.redact(f"{type(e).__name__}: {e}"))
                    self.log(f"[erreur] {type(e).__name__}: {safety.redact(str(e))}")
                time.sleep(self.s.loop_seconds)
        finally:
            self.db.set("heartbeat", {"ts": now_iso(), "clean_shutdown": True})
            self.log("Arrêt propre.")

    def portfolio_risk(self, data: dict) -> dict:
        prices = {k: float(v["close"].iloc[-1]) for k, v in data.items()}
        return portfolio_risk(self.account.open_positions(), prices, data, self.account.equity(prices))
