"""Coupe-circuit global et arrêt d'urgence.

Quand une limite est atteinte : plus aucune entrée, rapprochement des positions,
incident enregistré, alerte envoyée. La reprise exige une AUTORISATION EXPLICITE
de l'opérateur (phrase de confirmation), jamais automatique.
"""
from __future__ import annotations

from ..database.db import Database, now_iso

RESUME_PHRASE = "JE CONFIRME LA REPRISE EN DEMO"


class CircuitBreaker:
    KEY = "breaker"
    EMERGENCY = "emergency"

    def __init__(self, db: Database, alert=None):
        self.db = db
        self.alert = alert or (lambda *a, **k: None)

    @property
    def state(self) -> dict:
        return self.db.get(self.KEY, {"tripped": False, "reason": "", "at": None})

    @property
    def emergency(self) -> dict:
        return self.db.get(self.EMERGENCY, {"active": False, "close_all": False, "reason": "", "at": None})

    def entries_allowed(self) -> tuple[bool, str]:
        if self.emergency["active"]:
            return False, f"ARRÊT D'URGENCE actif : {self.emergency['reason']}"
        if self.state["tripped"]:
            return False, f"COUPE-CIRCUIT déclenché : {self.state['reason']} (autorisation requise)"
        return True, ""

    def trip(self, reason: str, payload: dict | None = None):
        if self.state["tripped"]:
            return
        self.db.set(self.KEY, {"tripped": True, "reason": reason, "at": now_iso()})
        self.db.event("critical", "circuit_breaker", reason, payload)
        self.alert(f"🛑 COUPE-CIRCUIT : {reason}. Nouvelles entrées bloquées. Reprise = autorisation explicite.")

    def emergency_stop(self, reason: str, close_all: bool = True):
        self.db.set(self.EMERGENCY, {"active": True, "close_all": close_all, "reason": reason, "at": now_iso()})
        self.db.event("critical", "emergency_stop", reason, {"close_all": close_all})
        self.alert(f"🚨 ARRÊT D'URGENCE : {reason} (fermeture des positions : {close_all})")

    def acknowledge_close_all(self):
        e = self.emergency
        e["close_all"] = False
        self.db.set(self.EMERGENCY, e)

    def authorize_resume(self, phrase: str, operator: str, note: str = "") -> tuple[bool, str]:
        if phrase.strip() != RESUME_PHRASE:
            return False, f"Phrase incorrecte. Tape exactement : {RESUME_PHRASE}"
        if not operator.strip():
            return False, "Nom de l'opérateur requis."
        self.db.set(self.KEY, {"tripped": False, "reason": "", "at": None})
        self.db.set(self.EMERGENCY, {"active": False, "close_all": False, "reason": "", "at": None})
        self.db.event("warning", "resume_authorized", f"Reprise autorisée par {operator}", {"note": note})
        self.db.set("resume_pending_baseline_reset", True)
        return True, "Reprise autorisée. Les références de perte seront réinitialisées au prochain cycle."
