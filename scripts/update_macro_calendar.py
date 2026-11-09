"""Ajoute les réunions du FOMC au calendrier macro depuis le site officiel de la Fed.

Best effort : la page peut changer. Le script AFFICHE ce qu'il a trouvé et ne
remplace jamais les lignes existantes. Vérifie toujours le résultat.
Usage : python scripts/update_macro_calendar.py
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

import requests

URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
CSV = Path(__file__).resolve().parent.parent / "config" / "macro_events.csv"
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}


MEETING = re.compile(r"fomc-meeting__month[^>]*>\s*<strong>([A-Za-z]+)(?:/([A-Za-z]+))?</strong>.*?"
                     r"fomc-meeting__date[^>]*>\s*(\d{1,2})(?:-(\d{1,2}))?", re.S)
SHORT = {m[:3]: i for m, i in MONTHS.items()}


def _month(name: str) -> int | None:
    return MONTHS.get(name) or SHORT.get(name[:3].title())


def parse(html: str) -> list[date]:
    """Retourne le jour de décision (dernier jour) de chaque réunion, par année."""
    out = []
    parts = re.split(r"(\d{4}) FOMC Meetings", html)
    for i in range(1, len(parts) - 1, 2):
        year, body = int(parts[i]), parts[i + 1]
        for m1, m2, d1, d2 in MEETING.findall(body):
            month = _month(m2) if (m2 and d2 and int(d2) < int(d1)) else _month(m1)
            try:
                out.append(date(year, month, int(d2 or d1)))
            except (TypeError, ValueError):
                continue
    return sorted(set(out))


def main():
    try:
        html = requests.get(URL, timeout=20, headers={"User-Agent": "quantum-edge-research/1.0"}).text
    except Exception as e:
        sys.exit(f"Impossible de joindre {URL} ({e}). Ajoute les dates à la main dans {CSV}.")
    found = [d for d in parse(html) if d >= date.today()]
    if not found:
        sys.exit("Aucune date trouvée (structure de la page modifiée ?). Ajoute les dates à la main.")
    existing = CSV.read_text(encoding="utf-8")
    new = [d for d in found if d.isoformat() not in existing]
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for d in new:
            w.writerow([d.isoformat(), "FOMC décision de taux", "high", URL])
    print(f"{len(new)} date(s) FOMC ajoutée(s) : {[d.isoformat() for d in new]}")
    print("Vérifie-les sur le site de la Fed. Ajoute aussi CPI et emploi (bls.gov) à la main.")


if __name__ == "__main__":
    main()
