"""Calendrier macro (fichier local vérifiable) et dates de résultats (yfinance, gratuit).

Rien n'est inventé : si une date n'est pas connue, on renvoie None et l'agent
macro le signale ("inconnu").
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass
class MacroEvent:
    day: date
    name: str
    importance: str  # high | medium | low
    source: str


def load_macro_events(path: Path) -> list[MacroEvent]:
    if not path.exists():
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(r for r in f if not r.startswith("#")):
            try:
                out.append(MacroEvent(datetime.strptime(row["date"].strip(), "%Y-%m-%d").date(),
                                      row["event"].strip(), row.get("importance", "high").strip().lower(),
                                      row.get("source", "").strip()))
            except Exception:
                continue
    return out


def events_between(events: list[MacroEvent], start: date, end: date) -> list[MacroEvent]:
    return [e for e in events if start <= e.day <= end]


def next_earnings(symbol: str) -> tuple[date | None, str]:
    """(date, statut). statut = 'ok' | 'none' (pas d'entreprise, ex. ETF) | 'unknown'."""
    try:
        import yfinance as yf

        t = yf.Ticker(symbol)
        try:
            df = t.get_earnings_dates(limit=8)
        except Exception:
            df = None
        today = date.today()
        if df is not None and len(df):
            future = sorted(d.date() for d in df.index.to_pydatetime() if d.date() >= today)
            if future:
                return future[0], "ok"
        cal = t.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                ds = [d for d in (ed if isinstance(ed, list) else [ed]) if isinstance(d, date)]
                ds = [d for d in ds if d >= today]
                if ds:
                    return min(ds), "ok"
        return None, "unknown"
    except Exception:
        return None, "unknown"
