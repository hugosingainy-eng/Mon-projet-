"""Grok (xAI) — OPTIONNEL et PAYANT, désactivé par défaut (pas de XAI_API_KEY).
Utilisé par l'agent sentiment comme source supplémentaire.

Les statistiques ne voient pas les annonces à venir : résultats trimestriels, procès,
décision de la Fed, scandale, rumeur qui enflamme X... Grok a accès en temps réel à X
(Twitter) et au web : on lui demande d'enquêter sur chaque trade validé par le comité.

Rôle limité : il peut seulement contribuer à un VETO, jamais déclencher un trade.
Si la clé API est absente ou si Grok ne répond pas, le bot continue sans lui.
Grok n'est pas utilisé en backtest : il connaît le futur des dates passées.

Doc : https://docs.x.ai  (API "Responses" + outils serveur x_search / web_search)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

XAI_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1") + "/responses"

SYSTEM = (
    "Tu es l'analyste news et sentiment d'un desk de trading professionnel. "
    "Tu es sceptique, factuel et tu cites des faits récents vérifiables. "
    "Ta mission : protéger le trader contre les risques d'événements que l'analyse "
    "technique ne voit pas. Utilise la recherche X et web. "
    "Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour."
)

PROMPT = """Trade envisagé aujourd'hui ({date}) par le bot :
- Actif : {symbol} (sur eToro)
- Sens : {side}
- Stratégie : {strategy} (inspirée de {inspired_by})
- Prix : {price:.4g}, stop {stop:.4g}, objectif {target:.4g}
- Durée maximale : {horizon} jours de bourse

Cherche sur X et sur le web les informations des 7 derniers jours et les événements
prévus pendant la durée du trade : résultats trimestriels, annonces, procès,
régulateurs, dirigeants, macro (Fed, CPI, emploi) qui touchent cet actif.

Réponds avec ce JSON exactement :
{{
  "sentiment": nombre de -1 (très négatif pour l'actif) à 1 (très positif),
  "event_risk": "low" | "medium" | "high",
  "earnings_in_days": nombre de jours avant les prochains résultats, ou null,
  "key_events": ["fait court et daté", "..."],
  "veto": true si tu déconseilles fortement ce trade, sinon false,
  "summary": "2 phrases maximum, en français"
}}"""


@dataclass
class GrokReport:
    used: bool = False
    sentiment: float = 0.0
    event_risk: str = "unknown"
    earnings_in_days: int | None = None
    veto: bool = False
    key_events: list = field(default_factory=list)
    summary: str = ""
    sources: int = 0           # nb de recherches réellement faites par Grok
    error: str = ""


def _output_text(resp: dict) -> str:
    if isinstance(resp.get("output_text"), str):
        return resp["output_text"]
    parts = []
    for item in resp.get("output", []) or []:
        for c in item.get("content", []) or []:
            if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                parts.append(c.get("text", ""))
    if not parts and resp.get("choices"):          # format chat-completions éventuel
        parts.append(resp["choices"][0]["message"]["content"])
    return "\n".join(parts)


def _count_searches(resp: dict) -> int:
    return sum(1 for it in resp.get("output", []) or []
               if isinstance(it, dict) and "search" in str(it.get("type", "")))


def parse_report(text: str) -> GrokReport:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("pas de JSON dans la réponse de Grok")
    d = json.loads(m.group(0))
    e = d.get("earnings_in_days")
    return GrokReport(
        used=True,
        sentiment=max(-1.0, min(1.0, float(d.get("sentiment", 0) or 0))),
        event_risk=str(d.get("event_risk", "unknown")).lower(),
        earnings_in_days=int(e) if isinstance(e, (int, float)) else None,
        veto=bool(d.get("veto", False)),
        key_events=[str(x) for x in (d.get("key_events") or [])][:6],
        summary=str(d.get("summary", ""))[:400],
    )


class GrokAgent:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 120):
        self.api_key = api_key if api_key is not None else os.getenv("XAI_API_KEY", "")
        self.model = model or os.getenv("GROK_MODEL", "grok-4.7")
        self.timeout = timeout
        self._cache: dict = {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def ask(self, cand, horizon: int) -> GrokReport:
        if not self.enabled:
            return GrokReport(error="XAI_API_KEY absente : agent Grok désactivé")
        key = (cand.symbol, cand.direction, cand.date)
        if key in self._cache:
            return self._cache[key]
        prompt = PROMPT.format(
            date=cand.date or datetime.now(timezone.utc).date(), symbol=cand.symbol,
            side="ACHAT (long)" if cand.direction > 0 else "VENTE À DÉCOUVERT (short)",
            strategy=cand.strategy, inspired_by=cand.inspired_by, price=cand.price,
            stop=cand.stop_price, target=cand.target_price, horizon=horizon,
        )
        body = {
            "model": self.model,
            "input": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "tools": [{"type": "x_search"}, {"type": "web_search"}],
            "temperature": 0.1,
        }
        try:
            r = requests.post(XAI_URL, json=body, timeout=self.timeout,
                              headers={"Authorization": f"Bearer {self.api_key}"})
            r.raise_for_status()
            resp = r.json()
            rep = parse_report(_output_text(resp))
            rep.sources = _count_searches(resp)
        except Exception as e:  # Grok indisponible -> on continue sans lui
            rep = GrokReport(error=f"{type(e).__name__}: {e}"[:300])
        self._cache[key] = rep
        return rep
