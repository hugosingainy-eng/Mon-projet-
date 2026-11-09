"""Couche de sécurité IMMUABLE : bloque toute exécution en argent réel.

Cette couche est appelée par le client HTTP eToro lui-même (point de passage
unique de toute requête). Aucun agent ne peut la contourner : les constantes ne
dépendent d'aucune configuration, et le module se protège contre la modification
de ses attributs à l'exécution.
"""
from __future__ import annotations

import os
import sys
import types

_ALLOWED_MODE = "DEMO"
_MAX_LEVERAGE = 1
_SHORTS_ENABLED = False
_EXECUTION_PATH_MARKERS = ("/execution/", "/orders", "market-open", "market-close", "limit-orders")
_FORBIDDEN_FRAGMENTS = ("/real/", "/real?", "/live/", "real-orders")


class SafetyViolation(RuntimeError):
    """Levée quand une action interdite est tentée. Ne jamais l'attraper pour continuer."""


def check_mode() -> None:
    mode = os.getenv("TRADING_MODE", "DEMO").strip().upper()
    if mode != _ALLOWED_MODE:
        raise SafetyViolation(f"TRADING_MODE={mode!r} refusé : seul DEMO est autorisé dans ce projet.")


def check_request(method: str, path: str) -> None:
    """Toute requête vers eToro passe ici avant d'être envoyée."""
    check_mode()
    p = path.lower()
    if any(f in p for f in _FORBIDDEN_FRAGMENTS):
        raise SafetyViolation(f"Route de trading réel bloquée : {path}")
    is_execution = any(m in p for m in _EXECUTION_PATH_MARKERS)
    if is_execution and "/demo" not in p:
        raise SafetyViolation(f"Ordre hors démo bloqué : {method} {path}")
    if method.upper() not in ("GET", "POST", "DELETE", "PUT"):
        raise SafetyViolation(f"Méthode HTTP inattendue : {method}")


def check_order(is_buy: bool, leverage: int, amount: float, budget_cash: float) -> None:
    check_mode()
    if leverage != _MAX_LEVERAGE:
        raise SafetyViolation(f"Levier {leverage} refusé : seul x1 est autorisé.")
    if not is_buy and not _SHORTS_ENABLED:
        raise SafetyViolation("Vente à découvert désactivée.")
    if amount <= 0 or amount > budget_cash + 1e-9:
        raise SafetyViolation(f"Montant {amount} hors du budget disponible ({budget_cash:.2f} $).")


def redact(text: str) -> str:
    """Retire les secrets connus d'un texte avant de l'écrire dans un log."""
    out = str(text)
    for var in ("ETORO_API_KEY", "ETORO_USER_KEY", "XAI_API_KEY", "TELEGRAM_BOT_TOKEN", "DASHBOARD_TOKEN"):
        v = os.getenv(var, "")
        if v and len(v) >= 4:
            out = out.replace(v, "***")
    return out


class _FrozenModule(types.ModuleType):
    def __setattr__(self, name, value):
        raise SafetyViolation(f"La couche de sécurité est immuable ({name}).")

    def __delattr__(self, name):
        raise SafetyViolation(f"La couche de sécurité est immuable ({name}).")


sys.modules[__name__].__class__ = _FrozenModule
