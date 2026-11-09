"""Contrôles de fraîcheur et de qualité des données (checks 1 et 2 du moteur de décision)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class QualityReport:
    ok: bool
    fresh: bool
    last_bar: str
    age_days: float
    issues: list = field(default_factory=list)


def check_daily(df: pd.DataFrame, now: pd.Timestamp, max_age_days: int) -> QualityReport:
    issues = []
    if df is None or len(df) == 0:
        return QualityReport(False, False, "", float("inf"), ["aucune donnée"])
    last = df.index[-1]
    age = float(np.busday_count(last.date(), now.date())) if now.date() > last.date() else 0.0
    fresh = age <= max_age_days
    if not fresh:
        issues.append(f"dernière barre vieille de {age:.0f} jours ouvrés")
    tail = df.iloc[-260:]
    if tail[["open", "high", "low", "close"]].isna().any().any():
        issues.append("valeurs manquantes")
    if (tail["high"] < tail["low"]).any() or (tail["close"] <= 0).any():
        issues.append("barres incohérentes (high<low ou prix<=0)")
    r = np.log(tail["close"]).diff().abs()
    if (r > 0.40).any():
        issues.append("saut de prix > 40 % (split non ajusté ou donnée erronée)")
    flat = (tail["close"].diff() == 0).rolling(5).sum().max()
    if flat and flat >= 5:
        issues.append("prix figé 5 jours de suite")
    gaps = tail.index.to_series().diff().dt.days.max()
    if gaps and gaps > 6:
        issues.append(f"trou de {gaps} jours dans l'historique récent")
    return QualityReport(fresh and not issues, fresh, str(last.date()), age, issues)


def check_intraday(df: pd.DataFrame | None, now: pd.Timestamp, max_age: pd.Timedelta) -> bool:
    if df is None or len(df) < 30:
        return False
    return (now - df.index[-1]) <= max_age and not df["close"].iloc[-30:].isna().any()
