"""Exécution des ordres + registre (ledger) du budget virtuel du bot.

Le compte démo eToro contient 100 000 $ virtuels : le bot ne gère que son propre
budget (100 $ par défaut) et suit lui-même ses positions et son P&L.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone


class Ledger:
    def __init__(self, starting_capital: float, path: str | None = None):
        self.path = path
        self.d = {
            "starting_capital": starting_capital,
            "cash": starting_capital,
            "peak_equity": starting_capital,
            "week_key": "",
            "week_start_equity": starting_capital,
            "positions": [],
            "closed": [],
        }
        if path and os.path.exists(path):
            with open(path) as f:
                self.d.update(json.load(f))

    def save(self):
        if self.path:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.d, f, indent=2, default=str)
            os.replace(tmp, self.path)

    # ------------------------------------------------------------ lecture
    @property
    def positions(self) -> list:
        return self.d["positions"]

    @property
    def cash(self) -> float:
        return self.d["cash"]

    def position_value(self, p, price: float) -> float:
        return p["amount"] * (1 + p["direction"] * (price / p["entry"] - 1) * p.get("leverage", 1))

    def equity(self, prices: dict) -> float:
        return self.cash + sum(self.position_value(p, prices.get(p["symbol"], p["entry"]))
                               for p in self.positions)

    def exposure(self) -> float:
        return sum(p["amount"] for p in self.positions)

    # ------------------------------------------------------------ écriture
    def record_open(self, dec, amount: float, entry: float, when: str, broker_id=None, leverage=1):
        c = dec.candidate
        p = {
            "id": str(uuid.uuid4())[:8], "broker_id": broker_id, "symbol": c.symbol,
            "strategy": c.strategy, "direction": c.direction, "amount": amount,
            "entry": entry, "leverage": leverage,
            "stop": entry * (1 - c.direction * c.stop_pct),
            "target": entry * (1 + c.direction * c.target_pct),
            "cost_pct": c.cost_pct, "opened": when, "bars_held": 0,
            "mc_expected_r": dec.mc.expected_r, "mc_p_win": dec.mc.p_win,
        }
        self.d["cash"] -= amount
        self.positions.append(p)
        return p

    def record_close(self, p, price: float, when: str, reason: str, fees: float = 0.0):
        value = self.position_value(p, price) - p["amount"] * p["cost_pct"] - fees
        self.d["cash"] += value
        self.positions.remove(p)
        pnl = value - p["amount"]
        risk = p["amount"] * abs(p["entry"] - p["stop"]) / p["entry"]
        self.d["closed"].append({**p, "exit": price, "closed": when, "reason": reason,
                                 "pnl": pnl, "r": pnl / risk if risk > 0 else 0.0})
        return pnl

    def mark(self, prices: dict, now: datetime):
        eq = self.equity(prices)
        self.d["peak_equity"] = max(self.d["peak_equity"], eq)
        wk = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]}"
        if wk != self.d["week_key"]:
            self.d["week_key"] = wk
            self.d["week_start_equity"] = eq
        return eq


def _now_str():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PaperBroker:
    """Simulation locale : aucun ordre n'est envoyé nulle part."""
    name = "paper"

    def __init__(self, ledger: Ledger):
        self.ledger = ledger

    def open(self, dec, amount, price, leverage=1, when=None):
        return self.ledger.record_open(dec, amount, price, when or _now_str(), leverage=leverage)

    def close(self, p, price, reason, when=None):
        return self.ledger.record_close(p, price, when or _now_str(), reason)

    def check_exits(self, prices: dict, when=None):
        """Simule les ordres stop-loss / take-profit côté courtier."""
        for p in list(self.ledger.positions):
            px = prices.get(p["symbol"])
            if px is None:
                continue
            d = p["direction"]
            if d * (px - p["stop"]) <= 0:
                self.close(p, px, "stop", when)
            elif d * (px - p["target"]) >= 0:
                self.close(p, p["target"], "target", when)

    def sync(self, prices):
        pass


class EtoroDemoBroker(PaperBroker):
    """Envoie les ordres au compte DÉMO eToro (stop-loss et take-profit inclus)."""
    name = "etoro-demo"

    def __init__(self, ledger: Ledger, client):
        super().__init__(ledger)
        self.client = client

    @staticmethod
    def _extract_id(resp):
        from .etoro_client import _get
        for key in ("positionId", "positionID", "orderId", "orderID"):
            v = _get(resp, key)
            if v is None and isinstance(resp, dict):
                for sub in resp.values():
                    v = _get(sub, key) if isinstance(sub, dict) else None
                    if v is not None:
                        break
            if v is not None:
                return v
        return None

    def open(self, dec, amount, price, leverage=1, when=None):
        c = dec.candidate
        resp = self.client.open_position(c.symbol, c.direction > 0, amount, leverage,
                                         c.stop_price, c.target_price)
        return self.ledger.record_open(dec, amount, price, when or _now_str(),
                                       broker_id=self._extract_id(resp), leverage=leverage)

    def close(self, p, price, reason, when=None):
        if p.get("broker_id") is not None:
            self.client.close_position(p["broker_id"], p["symbol"])
        return self.ledger.record_close(p, price, when or _now_str(), reason)

    def check_exits(self, prices, when=None):
        pass  # stop-loss / take-profit sont exécutés par eToro

    def sync(self, prices):
        """Détecte les positions fermées par eToro (stop ou objectif touché)."""
        from .etoro_client import _get
        open_now = self.client.open_positions()
        live = {str(_get(p, "positionId", "positionID")) for p in open_now}
        live |= {str(_get(p, "orderId", "orderID")) for p in open_now}
        for p in list(self.ledger.positions):
            if p.get("broker_id") is None or str(p["broker_id"]) in live:
                continue
            px = prices.get(p["symbol"], p["entry"])
            near_stop = abs(px - p["stop"]) < abs(px - p["target"])
            exit_px = p["stop"] if near_stop else p["target"]
            self.ledger.record_close(p, exit_px, _now_str(), "stop (eToro)" if near_stop else "target (eToro)")
