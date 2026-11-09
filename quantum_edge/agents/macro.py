"""Agent 4 — Analyste macroéconomique.

Sources gratuites et horodatées :
  * config/macro_events.csv : calendrier (FOMC, CPI, emploi...) que tu peux vérifier ;
  * flux RSS de la Réserve fédérale (communiqués) ;
  * dates de résultats des entreprises via yfinance.
Une information manquante n'est jamais inventée : elle est signalée "inconnue".
"""
from __future__ import annotations

from datetime import date, timedelta

from ..marketdata import calendar as cal
from ..marketdata import news
from .base import NEUTRAL, SUPPORT, VETO, Agent


class MacroAgent(Agent):
    name = "4_macro"
    role = "Analyste macroéconomique"

    def __init__(self, events_path, offline: bool = False):
        self.events_path = events_path
        self.offline = offline
        self._fed_cache = None

    def fed_headlines(self):
        if self._fed_cache is None:
            self._fed_cache = ([], ["mode hors ligne"]) if self.offline else news.fetch_fed()
        return self._fed_cache

    def analyze(self, symbol: str, asset_class: str, horizon_days: int, require_earnings: bool, today: date):
        events = cal.load_macro_events(self.events_path)
        soon = [e for e in cal.events_between(events, today, today + timedelta(days=2)) if e.importance == "high"]
        if self.offline:
            ed, status = None, "unknown"
        elif asset_class == "stock":
            ed, status = cal.next_earnings(symbol)
        else:
            ed, status = None, "none"
        fed, fed_err = self.fed_headlines()
        window_end = today + timedelta(days=int(horizon_days * 1.4) + 1)
        details = {
            "high_impact_events_48h": [f"{e.day} {e.name} ({e.source})" for e in soon],
            "calendar_file_events": len(events),
            "next_earnings": str(ed) if ed else None, "earnings_status": status,
            "fed_headlines": [f"{h.published:%Y-%m-%d} {h.title}" for h in fed[:5]], "source_errors": fed_err,
        }
        if not events:
            details["warning"] = "calendrier macro vide : remplis config/macro_events.csv"
        if soon:
            return self.report(symbol, VETO, "événement macro majeur dans les 48 h : " +
                               ", ".join(e.name for e in soon), 0.8, today, **details)
        if ed and today <= ed <= window_end:
            return self.report(symbol, VETO, f"résultats le {ed}, pendant la durée du trade (risque de gap)", 0.9,
                               today, **details)
        if asset_class == "stock" and status == "unknown" and require_earnings:
            return self.report(symbol, VETO, "date des résultats inconnue : prudence, pas de trade", 0.6, today,
                               **details)
        if not events:
            return self.report(symbol, NEUTRAL, "aucun événement connu, mais calendrier macro vide", 0.3, today,
                               **details)
        return self.report(symbol, SUPPORT, "pas d'événement à haut risque identifié pendant le trade", 0.6, today,
                           **details)
