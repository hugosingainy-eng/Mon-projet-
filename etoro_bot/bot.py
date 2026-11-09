"""Boucle principale : le bot trade du lundi au vendredi, tout seul."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from .agents.committee import Committee, find_candidates
from .agents.grok import GrokAgent, apply_grok
from .agents.history import SetupLibrary
from .agents.risk import PortfolioState, risk_gate, size_position
from .broker import EtoroDemoBroker, Ledger, PaperBroker
from .config import BotConfig
from .strategies import get_strategies


def portfolio_state(ledger: Ledger, prices: dict) -> PortfolioState:
    return PortfolioState(
        equity=ledger.equity(prices), cash=ledger.cash,
        peak_equity=ledger.d["peak_equity"], week_start_equity=ledger.d["week_start_equity"],
        open_symbols={p["symbol"] for p in ledger.positions}, exposure=ledger.exposure(),
    )


def execute_decisions(decisions, broker, prices, cfg: BotConfig, when=None, log=print):
    """Passe chaque décision approuvée au risk manager puis au courtier."""
    opened = []
    for dec in decisions:
        if not dec.approved:
            continue
        state = portfolio_state(broker.ledger, prices)
        ok, why = risk_gate(state, cfg.risk)
        if not ok:
            log(f"  [risk] {why}")
            break
        amount = size_position(dec, state, cfg.risk)
        if amount <= 0:
            log(f"  [risk] {dec.candidate.symbol}/{dec.candidate.strategy} ignoré : {'; '.join(dec.reasons)}")
            continue
        dec.amount = amount
        price = prices.get(dec.candidate.symbol, dec.candidate.price)
        pos = broker.open(dec, amount, price, leverage=cfg.risk.leverage, when=when)
        opened.append(pos)
        c = dec.candidate
        log(f"  [ORDRE] {'ACHAT' if c.direction > 0 else 'VENTE'} {c.symbol} {amount:.2f}$ @ {price:.2f} "
            f"stop {pos['stop']:.2f} objectif {pos['target']:.2f} | {c.strategy} "
            f"| MC: E={dec.mc.expected_r:+.2f}R, P(gain)={dec.mc.p_win:.0%}")
    return opened


class TradingBot:
    def __init__(self, cfg: BotConfig, source, client=None):
        self.cfg = cfg
        self.source = source
        os.makedirs(cfg.state_dir, exist_ok=True)
        os.makedirs(cfg.log_dir, exist_ok=True)
        ledger = Ledger(cfg.risk.starting_capital, os.path.join(cfg.state_dir, f"ledger-{cfg.mode}.json"))
        if cfg.mode == "demo":
            self.broker = EtoroDemoBroker(ledger, client)
        else:
            self.broker = PaperBroker(ledger)
        self.client = client
        self.grok = GrokAgent()
        self.last_scan_day = ledger.d.get("last_scan_day", "")

    def log(self, msg):
        line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} {msg}"
        print(line, flush=True)
        with open(os.path.join(self.cfg.log_dir, "bot.log"), "a") as f:
            f.write(line + "\n")

    def prices(self, data=None) -> dict:
        syms = list(self.cfg.watchlist)
        if self.client is not None:
            try:
                return self.client.last_prices(syms)
            except Exception as e:
                self.log(f"[prix] erreur API ({e}), repli sur les dernières clôtures")
        data = data or self.source.load(syms, 30)
        return {s: float(df["close"].iloc[-1]) for s, df in data.items()}

    # ---------------------------------------------------------------- étapes
    def manage_positions(self, prices):
        led = self.broker.ledger
        self.broker.sync(prices)
        self.broker.check_exits(prices)
        led.save()

    def scan(self):
        cfg = self.cfg
        t0 = time.time()
        self.log("=== SCAN : chargement des données ===")
        data = self.source.load(list(cfg.watchlist), cfg.history_bars)
        prices = {s: float(df["close"].iloc[-1]) for s, df in data.items()}
        if self.client is not None:
            prices.update(self.prices())
        led = self.broker.ledger
        now = datetime.now(timezone.utc)
        eq = led.mark(prices, now)

        # sortie temporelle : un trade qui ne fonctionne pas dans le temps imparti est coupé
        for p in list(led.positions):
            p["bars_held"] += 1
            if p["bars_held"] >= cfg.sim.horizon_bars and p["symbol"] in prices:
                pnl = self.broker.close(p, prices[p["symbol"]], "temps écoulé")
                self.log(f"  [SORTIE] {p['symbol']} temps écoulé, P&L {pnl:+.2f}$")

        costs = {s: cfg.cost_for(s) for s in data}
        lib = SetupLibrary(data, get_strategies(cfg.risk.allow_short), cfg.sim.horizon_bars, costs)
        cands = find_candidates(lib, cfg)
        self.log(f"{len(cands)} setups détectés par les agents stratégies")

        friday_cutoff = now.weekday() == 4 and now.hour >= cfg.no_new_trades_friday_after_utc
        with Committee(lib, cfg) as com:
            decisions = com.review(cands)
        self.consult_grok(decisions)
        for d in decisions:
            c = d.candidate
            verdict = "✅ VALIDÉ" if d.approved else "❌ rejeté"
            self.log(f"  {verdict} {c.symbol:5s} {c.strategy:24s} E={d.mc.expected_r:+.2f}R "
                     f"P(gain)={d.mc.p_win:.0%} PF={d.history.profit_factor:.2f} n={d.history.n_own}+{d.history.n_pool} "
                     + ("" if d.approved else "| " + "; ".join(d.reasons)))
        if friday_cutoff:
            self.log("  vendredi soir : pas de nouvelle position avant le week-end")
        else:
            execute_decisions(decisions, self.broker, prices, cfg, log=self.log)

        eq = led.mark(prices, now)
        led.d["last_scan_day"] = now.strftime("%Y-%m-%d")
        led.save()
        with open(os.path.join(cfg.log_dir, f"decisions-{now:%Y-%m-%d}.json"), "w") as f:
            json.dump([d.to_dict() for d in decisions], f, indent=2, default=str)
        self.log(f"Capital du bot : {eq:.2f}$ (départ {led.d['starting_capital']:.2f}$) | "
                 f"positions ouvertes : {len(led.positions)} | {com.total_paths:,} simulations "
                 f"Monte-Carlo en {time.time() - t0:.1f}s")
        self.last_scan_day = led.d["last_scan_day"]

    def consult_grok(self, decisions):
        """Grok n'enquête que sur les trades déjà validés par les chiffres (coût maîtrisé)."""
        approved = [d for d in decisions if d.approved]
        if not approved:
            return
        if not self.grok.enabled:
            self.log("  [grok] XAI_API_KEY absente : pas d'analyse des actualités")
            return
        for d in approved:
            rep = self.grok.ask(d.candidate, self.cfg.sim.horizon_bars)
            apply_grok(d, rep, self.cfg.sim.horizon_bars)
            c = d.candidate
            if rep.used:
                self.log(f"  [grok] {c.symbol}: sentiment {rep.sentiment:+.2f}, risque {rep.event_risk}, "
                         f"{rep.sources} recherches X/web -> {'OK' if d.approved else 'VETO'} | {rep.summary}")
            else:
                self.log(f"  [grok] {c.symbol}: indisponible ({rep.error}), décision inchangée")
        decisions.sort(key=lambda d: (d.approved, d.conviction, d.mc.expected_r), reverse=True)

    def report(self):
        led = self.broker.ledger
        closed = led.d["closed"]
        wins = [c for c in closed if c["pnl"] > 0]
        self.log(f"Trades clôturés : {len(closed)} | gagnants : {len(wins)} | "
                 f"P&L réalisé : {sum(c['pnl'] for c in closed):+.2f}$")
        for p in led.positions:
            self.log(f"  ouvert : {p['symbol']} {p['strategy']} {p['amount']:.2f}$ entrée {p['entry']:.2f} "
                     f"stop {p['stop']:.2f} objectif {p['target']:.2f}")

    # ---------------------------------------------------------------- boucle
    def run_forever(self):
        cfg = self.cfg
        self.log(f"Bot démarré en mode {cfg.mode.upper()} avec {cfg.risk.starting_capital}$ virtuels")
        while True:
            now = datetime.now(timezone.utc)
            try:
                if now.weekday() in cfg.trading_days:
                    self.manage_positions(self.prices())
                    scan_due = (now.hour, now.minute) >= (cfg.scan_hour_utc, cfg.scan_minute_utc)
                    if scan_due and self.last_scan_day != now.strftime("%Y-%m-%d"):
                        self.scan()
                        self.report()
            except KeyboardInterrupt:
                raise
            except Exception as e:  # le bot ne doit jamais mourir sur une erreur réseau
                self.log(f"[erreur] {type(e).__name__}: {e}")
            time.sleep(cfg.check_every_minutes * 60)
