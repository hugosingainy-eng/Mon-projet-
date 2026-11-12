"""Elite Trader Intelligence: public, delayed regulatory disclosures and documented principles.

Nothing here is a real-time position. A 13F reports holdings as of a quarter-end and is
published up to 45 days later; every record keeps both dates so its age is always visible."""
from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

from sqlalchemy import delete, select

from .data.base import AlternativeDataProvider
from .db import Database, Filing, Holding

# SEC Central Index Keys of the managers' filing entities. The displayed institution name is
# whatever the SEC returns for the CIK, so a wrong key cannot be passed off under a famous name.
MANAGERS = {
    "Warren Buffett": 1067983,          # Berkshire Hathaway
    "Jim Simons": 1037389,              # Renaissance Technologies
    "George Soros": 1029160,            # Soros Fund Management
    "Paul Tudor Jones": 923093,         # Tudor Investment Corp
    "Ray Dalio": 1350694,               # Bridgewater Associates
    "Stanley Druckenmiller": 1536411,   # Duquesne Family Office
}

# Generalizable principles -> testable strategy families in the lab. These are hypotheses to
# test, not claims that the trader's historical edge still exists.
PRINCIPLES = [
    {"trader": "Jim Simons (Renaissance)", "principle": "Many small, short-horizon statistical edges; mean reversion and pattern persistence tested on data, never on narrative.",
     "families": ["pairs_ratio", "rsi_reversion", "bb_reversion", "ensemble"], "source": "Public accounts of Renaissance's methods (e.g. G. Zuckerman, 'The Man Who Solved the Market', 2019)"},
    {"trader": "Paul Tudor Jones", "principle": "Trade with the long moving-average trend; defence first — cut losers quickly and seek asymmetric reward/risk.",
     "families": ["sma_trend", "ema_trend", "trend_pullback"], "source": "Public interviews (e.g. J. Schwager, 'Market Wizards', 1989)"},
    {"trader": "George Soros", "principle": "Reflexivity: self-reinforcing trends persist and then reverse sharply; size up when the thesis is confirmed by price.",
     "families": ["momentum_cont", "price_breakout", "regime_switch"], "source": "G. Soros, 'The Alchemy of Finance', 1987"},
    {"trader": "Stanley Druckenmiller", "principle": "Concentrate in the strongest assets, follow liquidity and relative strength, preserve capital.",
     "families": ["relative_strength", "mtf_confirm"], "source": "Public interviews and speeches"},
    {"trader": "Larry Williams", "principle": "Volatility breakouts: enter when price expands beyond a multiple of recent range; short holding periods.",
     "families": ["atr_breakout", "volatility_squeeze", "donchian"], "source": "L. Williams, 'Long-Term Secrets to Short-Term Trading', 1999"},
    {"trader": "Ray Dalio (Bridgewater)", "principle": "Balance risk, not capital, across uncorrelated exposures.",
     "families": [], "source": "Bridgewater public research on risk parity; applied here as risk-based sizing and correlated-exposure limits, not as a signal"},
    {"trader": "Warren Buffett", "principle": "Long-term ownership of businesses bought below intrinsic value.",
     "families": [], "source": "Berkshire Hathaway shareholder letters; not testable on a five-day horizon, so no strategy is derived"},
]


class EdgarProvider(AlternativeDataProvider):
    """SEC EDGAR 13F-HR filings. The SEC requires a User-Agent that identifies the requester."""

    def __init__(self, user_agent: str, db: Database):
        self.ua, self.db = user_agent, db

    def _get(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    def fetch(self) -> dict:
        added = 0
        for _trader, cik in MANAGERS.items():
            sub = json.loads(self._get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
            name = sub.get("name", f"CIK {cik}")
            rec = sub["filings"]["recent"]
            for form, acc, fdate, rdate in zip(rec["form"], rec["accessionNumber"], rec["filingDate"],
                                               rec["reportDate"]):
                if form != "13F-HR":
                    continue
                with self.db.session() as s:
                    known = s.scalar(select(Filing).where(Filing.accession == acc))
                if known:
                    break
                base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
                holdings = self._holdings(base)
                with self.db.session() as s:
                    s.execute(delete(Holding).where(Holding.institution == name))
                    s.execute(delete(Filing).where(Filing.institution == name))
                    s.add(Filing(institution=name, form=form, accession=acc, report_date=rdate,
                                 filing_date=fdate, url=base + "/"))
                    for issuer, (value, shares) in holdings:
                        s.add(Holding(accession=acc, institution=name, issuer=issuer, value_usd=value,
                                      shares=shares, report_date=rdate, filing_date=fdate, source=base + "/"))
                added += 1
                break      # only the latest 13F-HR per institution
        return {"new_filings": added}

    def _holdings(self, base: str, top: int = 15):
        index = json.loads(self._get(base + "/index.json"))
        names = [it["name"] for it in index["directory"]["item"]]
        xmls = [n for n in names if n.lower().endswith(".xml") and "primary_doc" not in n.lower()]
        if not xmls:
            return []
        return parse_info_table(self._get(f"{base}/{xmls[0]}"))[:top]


def parse_info_table(xml_bytes: bytes):
    """13F information table -> [(issuer, (value_usd, shares))] aggregated and sorted by value."""
    root = ET.fromstring(xml_bytes)
    agg: dict[str, list[float]] = {}
    for el in root.iter():
        if not el.tag.endswith("infoTable"):
            continue
        rec = {child.tag.split("}")[-1]: child for child in el}
        issuer = (rec["nameOfIssuer"].text or "").strip() if "nameOfIssuer" in rec else ""
        if not issuer:
            continue
        value = float((rec["value"].text or "0").replace(",", "")) if "value" in rec else 0.0
        shares = 0.0
        if "shrsOrPrnAmt" in rec:
            for c in rec["shrsOrPrnAmt"]:
                if c.tag.endswith("sshPrnamt"):
                    shares = float((c.text or "0").replace(",", ""))
        a = agg.setdefault(issuer, [0.0, 0.0])
        a[0] += value
        a[1] += shares
    return sorted(((k, (v[0], v[1])) for k, v in agg.items()), key=lambda x: -x[1][0])


def snapshot(db: Database) -> dict:
    today = date.today()

    def age(d: str) -> int | None:
        try:
            return (today - date.fromisoformat(d)).days
        except ValueError:
            return None

    with db.session() as s:
        filings = list(s.scalars(select(Filing).order_by(Filing.filing_date.desc())))
        holdings = list(s.scalars(select(Holding).order_by(Holding.institution, Holding.value_usd.desc())))
    return {
        "principles": PRINCIPLES,
        "filings": [{"institution": f.institution, "form": f.form, "report_date": f.report_date,
                     "filing_date": f.filing_date, "url": f.url, "freshness_days": age(f.report_date)}
                    for f in filings],
        "holdings": [{"institution": h.institution, "issuer": h.issuer, "value_usd": h.value_usd,
                      "shares": h.shares, "report_date": h.report_date, "filing_date": h.filing_date,
                      "source": h.source, "freshness_days": age(h.report_date),
                      "confidence": "high (regulatory filing, delayed)"} for h in holdings],
    }
