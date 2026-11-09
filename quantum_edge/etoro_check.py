"""Vérification pas à pas de l'intégration eToro (lecture seule, aucun ordre).

Usage : python -m quantum_edge etoro-check
Teste : authentification, recherche d'instrument, bougies, prix, portefeuille démo,
horloge. Ne passe JAMAIS d'ordre. Le résultat est enregistré dans reports/etoro_check.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


def run_check(s) -> dict:
    from .execution.etoro_client import EtoroDemoClient

    out = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "steps": {}}

    def step(name, fn):
        try:
            res = fn()
            out["steps"][name] = {"ok": True, "result": res}
            print(f"✅ {name}: {res}")
        except Exception as e:
            out["steps"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            print(f"❌ {name}: {type(e).__name__}: {e}")

    if not (s.etoro_api_key and s.etoro_user_key):
        print("❌ Clés absentes : renseigne ETORO_API_KEY et ETORO_USER_KEY dans .env (voir README).")
        out["steps"]["credentials"] = {"ok": False, "error": "absentes"}
    else:
        c = EtoroDemoClient(s.etoro_api_key, s.etoro_user_key, s.etoro_base_url)
        step("recherche instrument AAPL", lambda: c.instrument_id("AAPL"))
        step("bougies journalières AAPL", lambda: f"{len(c.candles('AAPL', 'OneDay', 30))} bougies")
        step("bougies 1h AAPL", lambda: f"{len(c.candles('AAPL', 'OneHour', 30))} bougies")
        step("prix en direct", lambda: c.rates(["AAPL", "SPY"]))
        step("portefeuille démo", lambda: f"{len(c.positions())} positions ouvertes")
        step("horloge", lambda: f"décalage serveur {c.server_time_offset} s")
    path = s.paths["reports"] / "etoro_check.json"
    path.write_text(json.dumps(out, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"\nRésultat enregistré : {path}")
    print("Si une route échoue (404), compare-la avec https://api-portal.etoro.com et corrige ENDPOINTS "
          "dans quantum_edge/execution/etoro_client.py.")
    return out
