"""Persistance SQLite (gratuit, sans serveur). Mode WAL : le bot écrit pendant que
le tableau de bord lit. Tout l'état nécessaire à une reprise après crash est ici."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, simulated INTEGER,
    n_candidates INTEGER, n_approved INTEGER, mc_paths INTEGER, seconds REAL, summary TEXT);
CREATE TABLE IF NOT EXISTS agent_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, scan_id INTEGER,
    agent TEXT, symbol TEXT, status TEXT, conclusion TEXT, confidence REAL, payload TEXT);
CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, scan_id INTEGER,
    symbol TEXT, strategy TEXT, decision TEXT, authorized INTEGER, confidence REAL, payload TEXT);
CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, client_key TEXT UNIQUE, ts TEXT,
    symbol TEXT, strategy TEXT, side TEXT, amount REAL, stop REAL, target REAL, state TEXT,
    broker_order_id TEXT, broker_position_id TEXT, payload TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS positions (id INTEGER PRIMARY KEY AUTOINCREMENT, client_key TEXT UNIQUE,
    symbol TEXT, strategy TEXT, entry REAL, units REAL, amount REAL, stop REAL, target REAL,
    opened_ts TEXT, bars_held INTEGER DEFAULT 0, last_bar TEXT, broker_position_id TEXT, state TEXT,
    exit REAL, exit_ts TEXT, reason TEXT, pnl REAL, fees REAL, r REAL, risk_usd REAL,
    regime TEXT, hypothesis TEXT, agents TEXT, simulated INTEGER);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, level TEXT, kind TEXT,
    message TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS equity (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, equity REAL, cash REAL,
    realized REAL, unrealized REAL, fees REAL, exposure REAL, drawdown REAL, simulated INTEGER);
CREATE INDEX IF NOT EXISTS ix_pos_state ON positions(state);
CREATE INDEX IF NOT EXISTS ix_orders_state ON orders(state);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        try:
            yield c
        finally:
            c.close()

    # ------------------------------------------------------------- clé/valeur
    def get(self, key: str, default=None):
        with self.conn() as c:
            row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set(self, key: str, value) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO kv(key,value,updated) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET "
                      "value=excluded.value, updated=excluded.updated", (key, json.dumps(value, default=str), now_iso()))

    # ------------------------------------------------------------- génériques
    def insert(self, table: str, row: dict) -> int:
        row = {k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else v) for k, v in row.items()}
        cols = ",".join(row)
        q = ",".join("?" * len(row))
        with self.conn() as c:
            cur = c.execute(f"INSERT INTO {table}({cols}) VALUES({q})", tuple(row.values()))
            return int(cur.lastrowid)

    def update(self, table: str, where: dict, values: dict) -> int:
        values = {k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else v) for k, v in values.items()}
        sets = ",".join(f"{k}=?" for k in values)
        cond = " AND ".join(f"{k}=?" for k in where)
        with self.conn() as c:
            cur = c.execute(f"UPDATE {table} SET {sets} WHERE {cond}", (*values.values(), *where.values()))
            return cur.rowcount

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    def event(self, level: str, kind: str, message: str, payload: dict | None = None) -> int:
        return self.insert("events", {"ts": now_iso(), "level": level, "kind": kind, "message": message,
                                      "payload": payload or {}})

    # ------------------------------------------------------------- sauvegarde
    def backup(self, folder: Path, keep: int = 14) -> Path:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"quantum_edge-{datetime.now(timezone.utc):%Y%m%d-%H%M}.db"
        with self.conn() as src:
            b = sqlite3.connect(dest)
            src.backup(b)
            b.close()
        olds = sorted(folder.glob("quantum_edge-*.db"))
        for f in olds[:-keep]:
            f.unlink(missing_ok=True)
        return dest
