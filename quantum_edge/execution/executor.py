"""Cœur de l'agent d'exécution : ordres idempotents, confirmation, surveillance,
rapprochement (reconciliation) après incident ou redémarrage.

Règles :
  * clé d'ordre unique (date:actif:stratégie) -> un même signal ne peut jamais
    produire deux ordres, même après un crash (contrainte UNIQUE en base) ;
  * tant qu'un ordre est à l'état incertain, AUCUN nouvel ordre n'est envoyé ;
  * un ordre n'est considéré exécuté qu'après confirmation du courtier.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from ..database.db import Database, now_iso
from .brokers import OrderResult

PENDING = ("intent", "submitted", "uncertain")


class Executor:
    def __init__(self, db: Database, account, broker, settings, log=print, alert=None):
        self.db, self.account, self.broker, self.settings = db, account, broker, settings
        self.log = log
        self.alert = alert or (lambda *a, **k: None)

    # ------------------------------------------------------------ garde-fous
    def pending_orders(self) -> list[dict]:
        return self.db.query(f"SELECT * FROM orders WHERE state IN ({','.join('?' * len(PENDING))})", PENDING)

    def uncertain_positions(self) -> list[dict]:
        return self.db.query("SELECT * FROM positions WHERE state='closing_uncertain'")

    def can_submit(self) -> tuple[bool, str]:
        if self.pending_orders():
            return False, "un ordre précédent n'est pas encore rapproché"
        if self.uncertain_positions():
            return False, "une clôture est à l'état incertain"
        return True, ""

    # ------------------------------------------------------------ ouverture
    def open(self, d: dict) -> OrderResult:
        key = d["client_key"]
        if self.db.query("SELECT id FROM orders WHERE client_key=?", (key,)):
            return OrderResult("rejected", message=f"ordre en double bloqué ({key})")
        ok, why = self.can_submit()
        if not ok:
            return OrderResult("rejected", message=why)
        try:
            self.db.insert("orders", {"client_key": key, "ts": now_iso(), "symbol": d["symbol"],
                                      "strategy": d["strategy"], "side": "BUY", "amount": d["amount"],
                                      "stop": d["stop"], "target": d["target"], "state": "intent",
                                      "payload": d, "updated": now_iso()})
        except sqlite3.IntegrityError:
            return OrderResult("rejected", message=f"ordre en double bloqué ({key})")
        self.db.update("orders", {"client_key": key}, {"state": "submitted", "updated": now_iso()})
        res = self.broker.submit_open(d["symbol"], d["amount"], d["price"], d["stop"], d["target"], key)
        self.db.update("orders", {"client_key": key}, {"state": res.state, "broker_order_id": res.broker_order_id,
                                                        "broker_position_id": res.broker_position_id,
                                                        "updated": now_iso()})
        if res.state == "confirmed":
            self._book_open(d, res)
        elif res.state == "uncertain":
            self.db.event("critical", "order_uncertain", f"{d['symbol']}: {res.message}", {"key": key})
            self.alert(f"⚠️ Ordre {d['symbol']} à l'état INCERTAIN : plus aucun ordre avant rapprochement.")
        else:
            self.db.event("warning", "order_rejected", f"{d['symbol']}: {res.message}", {"key": key})
        return res

    def _book_open(self, d: dict, res: OrderResult):
        fill = res.fill_price or d["price"]
        units = res.units or d["amount"] / fill
        entry_fee = d["amount"] * d["cost_pct"] / 2
        self.account.debit_open(d["amount"], entry_fee)
        self.db.insert("positions", {
            "client_key": d["client_key"], "symbol": d["symbol"], "strategy": d["strategy"], "entry": fill,
            "units": units, "amount": d["amount"], "stop": d["stop"], "target": d["target"],
            "opened_ts": now_iso(), "bars_held": 0, "last_bar": d.get("bar_date", ""),
            "broker_position_id": res.broker_position_id, "state": "open", "fees": entry_fee,
            "risk_usd": d["risk_usd"], "regime": d.get("regime", ""), "hypothesis": d.get("hypothesis", {}),
            "agents": d.get("agents", {}), "simulated": int(self.broker.simulated),
        })
        self.log(f"  [EXÉCUTION] ACHAT {d['symbol']} {d['amount']:.2f} $ @ {fill:.4g} | stop {d['stop']:.4g} "
                 f"| objectif {d['target']:.4g} | {self.broker.name}")

    # ------------------------------------------------------------ clôture
    def close(self, p: dict, price: float, reason: str) -> OrderResult:
        res = self.broker.close(p, price)
        if res.state == "confirmed":
            self._book_close(p, res.fill_price or price, reason)
        elif res.state == "uncertain":
            self.db.update("positions", {"id": p["id"]}, {"state": "closing_uncertain"})
            self.db.event("critical", "close_uncertain", f"{p['symbol']}: {res.message}")
            self.alert(f"⚠️ Clôture {p['symbol']} incertaine : rapprochement requis.")
        else:
            self.db.event("error", "close_rejected", f"{p['symbol']}: {res.message}")
        return res

    def _book_close(self, p: dict, exit_px: float, reason: str):
        cost = self.settings.cost_for(p["symbol"])
        proceeds = p["units"] * exit_px
        exit_fee = proceeds * cost / 2
        pnl = proceeds - exit_fee - p["amount"] - (p["fees"] or 0.0)
        self.account.credit_close(proceeds, exit_fee, pnl)
        self.db.update("positions", {"id": p["id"]}, {
            "state": "closed", "exit": exit_px, "exit_ts": now_iso(), "reason": reason, "pnl": pnl,
            "fees": (p["fees"] or 0.0) + exit_fee, "r": pnl / p["risk_usd"] if p["risk_usd"] else 0.0})
        self.log(f"  [SORTIE] {p['symbol']} {reason} @ {exit_px:.4g} | P&L {pnl:+.2f} $")

    def close_all(self, prices: dict, reason: str):
        for p in self.account.open_positions():
            self.close(p, prices.get(p["symbol"], p["entry"]), reason)

    # ------------------------------------------------------------ surveillance
    def monitor(self, bars: dict, horizon: int):
        """bars : symbole -> {price, high, low, bar_date}. Stop / objectif (simulé) + sortie temporelle."""
        for p in self.account.open_positions():
            b = bars.get(p["symbol"])
            if not b:
                continue
            if self.broker.simulated:
                if b["low"] <= p["stop"]:
                    self.close(p, min(p["stop"], b["price"]) if b["price"] < p["stop"] else p["stop"], "stop-loss")
                    continue
                if b["high"] >= p["target"]:
                    self.close(p, p["target"], "take-profit")
                    continue
            if b.get("bar_date") and b["bar_date"] != p["last_bar"]:
                held = (p["bars_held"] or 0) + 1
                self.db.update("positions", {"id": p["id"]}, {"bars_held": held, "last_bar": b["bar_date"]})
                if held >= horizon:
                    self.close({**p, "bars_held": held}, b["price"], "sortie temporelle")

    # ------------------------------------------------------------ rapprochement
    def reconcile(self, prices: dict) -> dict:
        remote = self.broker.remote_positions()
        report = {"checked": remote is not None, "confirmed": 0, "failed": 0, "closed_by_broker": 0, "unknown": 0}
        if remote is None:
            for o in self.pending_orders():   # simulé : un ordre en attente n'a jamais été envoyé
                self.db.update("orders", {"client_key": o["client_key"]}, {"state": "failed", "updated": now_iso()})
                report["failed"] += 1
            for p in self.uncertain_positions():
                self.db.update("positions", {"id": p["id"]}, {"state": "open"})
            return report
        from .etoro_client import _get

        by_pid = {str(_get(r, "positionId", "positionID")): r for r in remote}
        by_oid = {str(_get(r, "orderId", "orderID")): r for r in remote if _get(r, "orderId", "orderID")}
        known = {p["broker_position_id"] for p in self.db.query("SELECT broker_position_id FROM positions")}
        for o in self.pending_orders():
            r = by_pid.get(str(o["broker_position_id"])) or by_oid.get(str(o["broker_order_id"]))
            if r is not None:
                pid = str(_get(r, "positionId", "positionID"))
                if pid not in known:
                    import json
                    d = json.loads(o["payload"])
                    rate = _get(r, "openRate", "rate")
                    self._book_open(d, OrderResult("confirmed", o["broker_order_id"], pid,
                                                   float(rate) if rate else d["price"], _get(r, "units")))
                    known.add(pid)
                self.db.update("orders", {"client_key": o["client_key"]},
                               {"state": "confirmed", "broker_position_id": pid, "updated": now_iso()})
                report["confirmed"] += 1
            else:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(o["ts"])
                if age > timedelta(minutes=15):
                    self.db.update("orders", {"client_key": o["client_key"]}, {"state": "failed", "updated": now_iso()})
                    self.db.event("critical", "order_failed",
                                  f"{o['symbol']}: aucune position trouvée après 15 min. Vérifie l'historique eToro.")
                    self.alert(f"⚠️ Ordre {o['symbol']} introuvable chez eToro après 15 min : vérification manuelle.")
                    report["failed"] += 1
        for p in self.account.open_positions() + self.uncertain_positions():
            if p["broker_position_id"] and str(p["broker_position_id"]) not in by_pid:
                px = prices.get(p["symbol"], p["entry"])
                near_stop = abs(px - p["stop"]) <= abs(px - p["target"])
                self._book_close(p, p["stop"] if near_stop else p["target"],
                                 ("stop-loss" if near_stop else "take-profit") + " (exécuté par eToro, prix estimé)")
                report["closed_by_broker"] += 1
            elif p["state"] == "closing_uncertain":
                self.db.update("positions", {"id": p["id"]}, {"state": "open"})
        report["unknown"] = len([k for k in by_pid if k not in known])
        return report
