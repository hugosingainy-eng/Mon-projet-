"""Actualités gratuites via flux RSS publics (sans clé API), horodatées.

Le score de sentiment est un simple lexique financier (inspiré de Loughran-McDonald).
C'est un indicateur grossier, utilisé seulement comme garde-fou, jamais comme
raison d'acheter.
"""
from __future__ import annotations

import email.utils
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import requests

FEEDS = {
    "yahoo": "https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US",
    "google": "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en",
}
FED_FEED = "https://www.federalreserve.gov/feeds/press_all.xml"
UA = {"User-Agent": "quantum-edge-research/1.0"}

POS = {"beat", "beats", "surge", "surges", "record", "upgrade", "upgraded", "raises", "growth", "strong",
       "outperform", "rally", "soars", "jumps", "approval", "approved", "buyback", "profit", "gains", "bullish"}
NEG = {"miss", "misses", "plunge", "plunges", "downgrade", "downgraded", "cuts", "lawsuit", "probe",
       "investigation", "recall", "fraud", "weak", "warning", "warns", "slump", "falls", "drops", "bearish",
       "layoffs", "bankruptcy", "fine", "fined", "halt", "sues", "sued", "decline", "loss", "losses", "tariff"}
RISK = {"earnings", "fomc", "fed", "cpi", "inflation", "payrolls", "jobs report", "guidance", "sec", "doj",
        "antitrust", "merger", "acquisition", "fda", "trial", "rate decision", "war", "sanctions"}


@dataclass
class Headline:
    title: str
    published: datetime
    source: str


def _parse(xml_text: str, source: str) -> list[Headline]:
    out = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        pub = item.findtext("pubDate")
        try:
            ts = email.utils.parsedate_to_datetime(pub) if pub else None
        except Exception:
            ts = None
        if title and ts:
            out.append(Headline(title, ts.astimezone(timezone.utc), source))
    return out


def fetch_headlines(symbol: str, days: int = 7, timeout: int = 10) -> tuple[list[Headline], list[str]]:
    """Retourne (titres, erreurs). Aucune donnée inventée : une source en panne = erreur listée."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    heads, errors = [], []
    for name, url in FEEDS.items():
        try:
            r = requests.get(url.format(sym=quote_plus(symbol), q=quote_plus(f"{symbol} stock")),
                             headers=UA, timeout=timeout)
            r.raise_for_status()
            heads += [h for h in _parse(r.text, name) if h.published >= since]
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}")
    seen, uniq = set(), []
    for h in sorted(heads, key=lambda h: h.published, reverse=True):
        k = h.title.lower()[:80]
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    return uniq, errors


def fetch_fed(days: int = 10, timeout: int = 10) -> tuple[list[Headline], list[str]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        r = requests.get(FED_FEED, headers=UA, timeout=timeout)
        r.raise_for_status()
        return [h for h in _parse(r.text, "federalreserve.gov") if h.published >= since], []
    except Exception as e:
        return [], [f"fed: {type(e).__name__}"]


def _words(t: str) -> list[str]:
    return re.findall(r"[a-z]+", t.lower())


def score(headlines: list[Headline]) -> dict:
    pos = neg = risk = 0
    for h in headlines:
        w = _words(h.title)
        pos += sum(x in POS for x in w)
        neg += sum(x in NEG for x in w)
        low = h.title.lower()
        risk += sum(k in low for k in RISK)
    tot = pos + neg
    return {
        "n": len(headlines),
        "sentiment": (pos - neg) / tot if tot else 0.0,
        "risk_mentions": risk,
        "positive_words": pos,
        "negative_words": neg,
    }
