"""Horaires de la bourse de New York (NYSE/Nasdaq) pour actions et ETF US."""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

# Jours fériés NYSE (à vérifier chaque année sur nyse.com/markets/hours-calendars).
HOLIDAYS = {
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
    date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31),
    date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24),
}
OPEN, CLOSE = time(9, 30), time(16, 0)


def ny_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(NY)).astimezone(NY)


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def is_market_open(now: datetime | None = None) -> bool:
    n = ny_now(now)
    return is_trading_day(n.date()) and OPEN <= n.time() < CLOSE


def minutes_to_close(now: datetime | None = None) -> float:
    n = ny_now(now)
    close = n.replace(hour=16, minute=0, second=0, microsecond=0)
    return (close - n).total_seconds() / 60
