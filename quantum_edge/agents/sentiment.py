"""Agent 5 — Analyste du sentiment.

Gratuit par défaut : titres d'actualité RSS (Yahoo Finance, Google News) notés par
lexique financier + anomalie de volume. Grok (xAI, payant) est OPTIONNEL : activé
seulement si XAI_API_KEY est renseignée.

Statistiques d'investisseurs eToro : l'API publique documente des données sur les
utilisateurs (Popular Investors), mais ces routes n'ont pas pu être vérifiées ; la
fonction `evaluate_investor` note un investisseur à partir de statistiques fournies,
sans jamais copier ses trades.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..marketdata import news
from .base import NEUTRAL, OPPOSE, SUPPORT, VETO, Agent


def evaluate_investor(stats: dict) -> dict:
    """Note 0-100 d'un investisseur : régularité, drawdown, exposition, concentration,
    performance dans plusieurs régimes. `stats` : monthly_returns (liste), max_drawdown (fraction),
    avg_exposure (fraction), top_position_weight (fraction), regime_returns (dict régime->rendement)."""
    m = np.asarray(stats.get("monthly_returns", []), float)
    if len(m) < 12:
        return {"score": 0.0, "verdict": "historique insuffisant (< 12 mois)"}
    consistency = float((m > 0).mean())
    sharpe = float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else 0.0
    dd = float(stats.get("max_drawdown", 1.0))
    conc = float(stats.get("top_position_weight", 1.0))
    expo = float(stats.get("avg_exposure", 1.0))
    regimes = stats.get("regime_returns", {})
    regime_ok = float(np.mean([v > 0 for v in regimes.values()])) if regimes else 0.0
    score = (30 * consistency + 20 * np.clip(sharpe / 2, 0, 1) + 20 * np.clip(1 - dd / 0.4, 0, 1)
             + 10 * np.clip(1 - conc / 0.5, 0, 1) + 10 * np.clip(1 - max(expo - 0.8, 0) / 0.2, 0, 1)
             + 10 * regime_ok)
    return {"score": round(float(score), 1), "consistency": consistency, "sharpe": sharpe, "max_drawdown": dd,
            "concentration": conc, "regime_robustness": regime_ok,
            "verdict": "solide" if score >= 70 else "moyen" if score >= 50 else "faible"}


class SentimentAgent(Agent):
    name = "5_sentiment"
    role = "Analyste du sentiment"

    def __init__(self, grok=None, offline: bool = False):
        self.grok = grok
        self.offline = offline

    def analyze(self, symbol: str, daily: pd.DataFrame, candidate=None, horizon: int = 15):
        heads, errors = ([], ["mode hors ligne"]) if self.offline else news.fetch_headlines(symbol)
        sc = news.score(heads)
        v20 = daily["volume"].iloc[-21:-1].mean()
        vol_ratio = float(daily["volume"].iloc[-1] / v20) if v20 > 0 else None
        details = {"headlines": [f"{h.published:%Y-%m-%d %H:%M} [{h.source}] {h.title}" for h in heads[:8]],
                   "news_score": sc, "volume_ratio": vol_ratio, "source_errors": errors,
                   "etoro_investor_stats": "non disponibles (routes non vérifiées)", "grok": None}
        if self.grok is not None and self.grok.enabled and candidate is not None:
            g = self.grok.ask(candidate, horizon)
            details["grok"] = g.__dict__
            if g.used and (g.veto or g.event_risk == "high"):
                return self.report(symbol, VETO, f"Grok : {g.summary}", 0.7, daily.index[-1], **details)
        if not heads:
            return self.report(symbol, NEUTRAL, "aucune actualité récente disponible", None, daily.index[-1],
                               **details)
        s = sc["sentiment"]
        if s <= -0.6 and sc["n"] >= 5:
            return self.report(symbol, VETO, f"actualité très négative ({s:+.2f} sur {sc['n']} titres)", 0.6,
                               daily.index[-1], **details)
        if s < -0.3:
            return self.report(symbol, OPPOSE, f"actualité plutôt négative ({s:+.2f})", 0.4, daily.index[-1],
                               **details)
        return self.report(symbol, SUPPORT if s > 0.2 else NEUTRAL, f"sentiment {s:+.2f} sur {sc['n']} titres",
                           0.3, daily.index[-1], **details)
