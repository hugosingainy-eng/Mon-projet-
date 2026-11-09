"""Client de l'API publique eToro — compte DÉMO uniquement.

Doc officielle : https://builders.etoro.com  et  https://api-portal.etoro.com
Authentification : en-têtes x-api-key, x-user-key, x-request-id (UUID par requête).

⚠️ Les routes ci-dessous n'ont PAS pu être vérifiées contre la documentation depuis
l'environnement de développement (accès réseau bloqué). Elles proviennent de la doc
publique telle que résumée par un moteur de recherche. Certaines routes v1 sont
"deprecated" au profit de POST /api/v2/trading/execution/demo/orders.
=> `python -m quantum_edge etoro-check` vérifie chaque route avant tout trading.

Toute requête passe par `safety.check_request` : impossible d'atteindre une route réelle.
"""
from __future__ import annotations

import email.utils
import threading
import time
import uuid
from datetime import datetime, timezone

import pandas as pd
import requests

from .. import safety

ENDPOINTS = {
    "search": "/api/v1/market-data/search",
    "candles": "/api/v1/market-data/instruments/{instrument_id}/history/candles/desc/{interval}/{count}",
    "rates": "/api/v1/market-data/instruments/rates",
    "open_by_amount": "/api/v1/trading/execution/demo/market-open-orders/by-amount",
    "close_position": "/api/v1/trading/execution/demo/market-close-orders/positions/{position_id}",
    "portfolio": "/api/v1/trading/info/demo/portfolio",
    "pnl": "/api/v1/trading/info/demo/pnl",
}


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def _get(d, *names, default=None):
    if not isinstance(d, dict):
        return default
    low = {k.lower(): v for k, v in d.items()}
    for n in names:
        if n.lower() in low and low[n.lower()] is not None:
            return low[n.lower()]
    return default


def find_list(obj, key_hint: str):
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and _get(obj[0], key_hint) is not None:
        return obj
    items = obj.values() if isinstance(obj, dict) else obj if isinstance(obj, list) else []
    for v in items:
        r = find_list(v, key_hint)
        if r is not None:
            return r
    return None


class EtoroDemoClient:
    MIN_INTERVAL = 0.25  # limitation de débit côté client (4 requêtes/s max)

    def __init__(self, api_key: str, user_key: str, base_url: str = "https://public-api.etoro.com",
                 timeout: int = 20, session=None):
        if not api_key or not user_key:
            raise ValueError("ETORO_API_KEY et ETORO_USER_KEY requis (voir .env.example).")
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.s = session or requests.Session()
        self._auth = {"x-api-key": api_key, "x-user-key": user_key}
        self._ids: dict[str, int] = {}
        self._lock = threading.Lock()
        self._last = 0.0
        self.server_time_offset: float | None = None

    def _req(self, method: str, path: str, **kw):
        safety.check_request(method, path)
        last_exc = None
        for attempt in range(4):
            with self._lock:
                wait = self.MIN_INTERVAL - (time.time() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.time()
            try:
                r = self.s.request(method, self.base + path, timeout=self.timeout,
                                   headers={**self._auth, "x-request-id": str(uuid.uuid4()),
                                            "Content-Type": "application/json"}, **kw)
            except (requests.ConnectionError, requests.Timeout) as e:
                last_exc = e
                time.sleep(2 ** attempt)
                continue
            self._record_clock(r)
            if r.status_code == 429 or r.status_code >= 500:
                last_exc = ApiError(r.status_code, safety.redact(r.text[:200]))
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise ApiError(r.status_code, safety.redact(r.text[:300]))
            return r.json() if r.content else {}
        raise last_exc or RuntimeError("échec de la requête")

    def _record_clock(self, r):
        d = r.headers.get("Date")
        if d:
            try:
                srv = email.utils.parsedate_to_datetime(d)
                self.server_time_offset = (srv - datetime.now(timezone.utc)).total_seconds()
            except Exception:
                pass

    # --------------------------------------------------------------- marché
    def instrument_id(self, symbol: str) -> int:
        if symbol in self._ids:
            return self._ids[symbol]
        data = self._req("GET", ENDPOINTS["search"], params={"internalSymbolFull": symbol})
        for it in find_list(data, "instrumentId") or find_list(data, "internalInstrumentId") or []:
            sym = str(_get(it, "internalSymbolFull", "symbolFull", "symbol", default="")).upper()
            if sym == symbol.upper():
                self._ids[symbol] = int(_get(it, "instrumentId", "internalInstrumentId"))
                return self._ids[symbol]
        raise KeyError(f"instrument introuvable sur eToro : {symbol}")

    def candles(self, symbol: str, interval: str, count: int) -> pd.DataFrame:
        iid = self.instrument_id(symbol)
        data = self._req("GET", ENDPOINTS["candles"].format(instrument_id=iid, interval=interval, count=count))
        rows = [{"date": _get(c, "fromDate", "date", "time"), "open": _get(c, "open"), "high": _get(c, "high"),
                 "low": _get(c, "low"), "close": _get(c, "close"), "volume": _get(c, "volume", default=0)}
                for c in find_list(data, "close") or []]
        if not rows:
            raise ApiError(0, f"aucune bougie reçue pour {symbol}")
        return pd.DataFrame(rows).set_index("date")

    def rates(self, symbols) -> dict:
        ids = {self.instrument_id(s): s for s in symbols}
        data = self._req("GET", ENDPOINTS["rates"], params={"instrumentIds": ",".join(map(str, ids))})
        out = {}
        for r in find_list(data, "instrumentId") or []:
            iid = int(_get(r, "instrumentId"))
            bid, ask = _get(r, "bid"), _get(r, "ask")
            px = _get(r, "lastExecution") or ((bid + ask) / 2 if bid and ask else bid or ask)
            if iid in ids and px:
                out[ids[iid]] = {"price": float(px), "bid": bid, "ask": ask,
                                 "time": _get(r, "date", "time", "lastUpdate")}
        return out

    # --------------------------------------------------------------- trading démo
    def open_by_amount(self, symbol: str, amount: float, stop_loss: float, take_profit: float,
                       leverage: int = 1, is_buy: bool = True) -> dict:
        body = {"InstrumentID": self.instrument_id(symbol), "IsBuy": bool(is_buy), "Leverage": int(leverage),
                "Amount": round(float(amount), 2), "StopLossRate": round(float(stop_loss), 6),
                "TakeProfitRate": round(float(take_profit), 6), "IsTslEnabled": False}
        return self._req("POST", ENDPOINTS["open_by_amount"], json=body)

    def close_position(self, position_id, symbol: str) -> dict:
        body = {"InstrumentId": self.instrument_id(symbol), "UnitsToDeduct": None}
        return self._req("POST", ENDPOINTS["close_position"].format(position_id=position_id), json=body)

    def portfolio(self) -> dict:
        return self._req("GET", ENDPOINTS["portfolio"])

    def positions(self) -> list[dict]:
        return find_list(self.portfolio(), "positionId") or find_list(self.portfolio(), "positionID") or []
