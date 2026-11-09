"""Exploitation : journaux structurés, alertes gratuites (Telegram optionnel), horloge."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import safety


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                           "level": record.levelname, "msg": safety.redact(record.getMessage())}, ensure_ascii=False)


def setup_logging(log_dir: Path) -> logging.Logger:
    log = logging.getLogger("quantum_edge")
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / "quantum_edge.jsonl", encoding="utf-8")
    fh.setFormatter(JsonFormatter())
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(fh)
    log.addHandler(sh)
    return log


class Alerter:
    """Alerte dans les journaux + base de données + Telegram (gratuit) si configuré."""

    def __init__(self, db, log: logging.Logger, telegram_token: str = "", chat_id: str = ""):
        self.db, self.log, self.token, self.chat = db, log, telegram_token, chat_id

    def __call__(self, message: str, level: str = "warning"):
        self.log.warning(f"[ALERTE] {message}")
        self.db.event(level, "alert", message)
        if self.token and self.chat:
            try:
                requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                              json={"chat_id": self.chat, "text": f"Quantum Edge (DÉMO) — {message}"}, timeout=10)
            except Exception as e:
                self.log.error(safety.redact(f"[ALERTE] Telegram indisponible : {type(e).__name__}"))


def clock_status(client=None, max_offset_s: float = 30.0) -> dict:
    """Compare l'horloge locale à l'en-tête Date d'un serveur (eToro si disponible)."""
    offset = getattr(client, "server_time_offset", None) if client is not None else None
    source = "eToro"
    if offset is None:
        source = "worldtimeapi/https"
        try:
            t0 = time.time()
            r = requests.head("https://www.google.com", timeout=5)
            import email.utils
            srv = email.utils.parsedate_to_datetime(r.headers["Date"]).timestamp()
            offset = srv - (t0 + time.time()) / 2
        except Exception:
            return {"verified": False, "offset_s": None, "blocking": False, "source": "aucune (hors ligne)"}
    return {"verified": True, "offset_s": round(offset, 2), "blocking": abs(offset) > max_offset_s, "source": source}
