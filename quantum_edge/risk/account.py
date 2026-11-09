"""Comptabilité du budget virtuel de 100 $ (indépendant du solde démo eToro)."""
from __future__ import annotations

from datetime import datetime

from ..database.db import Database, now_iso


class Account:
    KEY = "account"

    def __init__(self, db: Database, starting_capital: float, simulated: bool):
        self.db = db
        self.simulated = simulated
        acc = db.get(self.KEY)
        if acc is None:
            acc = {"starting_capital": starting_capital, "cash": starting_capital, "realized": 0.0, "fees": 0.0,
                   "peak_equity": starting_capital, "day_key": "", "day_start_equity": starting_capital,
                   "week_key": "", "week_start_equity": starting_capital, "created": now_iso()}
            db.set(self.KEY, acc)

    @property
    def d(self) -> dict:
        return self.db.get(self.KEY)

    def _save(self, d):
        self.db.set(self.KEY, d)

    def open_positions(self) -> list[dict]:
        return self.db.query("SELECT * FROM positions WHERE state='open' ORDER BY id")

    def closed_positions(self) -> list[dict]:
        return self.db.query("SELECT * FROM positions WHERE state='closed' ORDER BY exit_ts")

    def exposure(self) -> float:
        return sum(p["amount"] for p in self.open_positions())

    def unrealized(self, prices: dict) -> float:
        return sum(p["units"] * prices.get(p["symbol"], p["entry"]) - p["amount"] for p in self.open_positions())

    def equity(self, prices: dict) -> float:
        d = self.d
        return d["cash"] + sum(p["units"] * prices.get(p["symbol"], p["entry"]) for p in self.open_positions())

    # ------------------------------------------------------------ mouvements
    def debit_open(self, amount: float, entry_fee: float):
        d = self.d
        d["cash"] -= amount + entry_fee
        d["fees"] += entry_fee
        self._save(d)

    def credit_close(self, proceeds: float, exit_fee: float, pnl: float):
        d = self.d
        d["cash"] += proceeds - exit_fee
        d["fees"] += exit_fee
        d["realized"] += pnl
        self._save(d)

    # ------------------------------------------------------------ périodes
    def roll_periods(self, prices: dict, now: datetime) -> dict:
        d = self.d
        eq = self.equity(prices)
        day = now.strftime("%Y-%m-%d")
        iso = now.isocalendar()
        week = f"{iso[0]}-W{iso[1]:02d}"
        if d["day_key"] != day:
            d["day_key"], d["day_start_equity"] = day, eq
        if d["week_key"] != week:
            d["week_key"], d["week_start_equity"] = week, eq
        d["peak_equity"] = max(d["peak_equity"], eq)
        self._save(d)
        return d

    def reset_baselines(self, prices: dict):
        """Appelé UNIQUEMENT après une autorisation explicite de reprise."""
        d = self.d
        eq = self.equity(prices)
        d["day_start_equity"] = d["week_start_equity"] = d["peak_equity"] = eq
        self._save(d)

    def snapshot(self, prices: dict) -> dict:
        d = self.d
        eq = self.equity(prices)
        snap = {"ts": now_iso(), "equity": eq, "cash": d["cash"], "realized": d["realized"],
                "unrealized": self.unrealized(prices), "fees": d["fees"], "exposure": self.exposure(),
                "drawdown": 1 - eq / d["peak_equity"] if d["peak_equity"] else 0.0, "simulated": int(self.simulated)}
        self.db.insert("equity", snap)
        return snap
