"""Client minimal de l'API publique eToro (compte DÉMO uniquement).

Doc officielle : https://api-portal.etoro.com
Authentification : en-têtes `x-api-key` (clé publique) + `x-user-key` (clé
utilisateur générée dans Paramètres > Trading > API Key Management, environnement
"Virtual/Demo") + `x-request-id` (UUID unique par requête).

⚠️ eToro fait évoluer ses routes (certaines v1 sont "deprecated" au profit de
/api/v2/trading/execution/demo/orders). Tous les chemins sont regroupés dans
ENDPOINTS ci-dessous : vérifie-les dans la doc et ajuste-les si besoin.
Ce client refuse volontairement toute route "real" : pas d'argent réel.
"""
from __future__ import annotations

import time
import uuid

import pandas as pd
import requests

ENDPOINTS = {
    "search": "/api/v1/market-data/search",
    "candles": "/api/v1/market-data/instruments/{instrument_id}/history/candles/desc/OneDay/{count}",
    "rates": "/api/v1/market-data/instruments/rates",
    "open_by_amount": "/api/v1/trading/execution/demo/market-open-orders/by-amount",
    "close_position": "/api/v1/trading/execution/demo/market-close-orders/positions/{position_id}",
    "portfolio": "/api/v1/trading/info/demo/portfolio",
    "pnl": "/api/v1/trading/info/demo/pnl",
}


def _get(d: dict, *names, default=None):
    """Lecture tolérante aux variations de casse (InstrumentID / instrumentId ...)."""
    if not isinstance(d, dict):
        return default
    low = {k.lower(): v for k, v in d.items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return default


def _find_list(obj, key_hint: str):
    """Trouve récursivement la première liste de dicts contenant `key_hint`."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and _get(obj[0], key_hint) is not None:
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = _find_list(v, key_hint)
            if r is not None:
                return r
    if isinstance(obj, list):
        for v in obj:
            r = _find_list(v, key_hint)
            if r is not None:
                return r
    return None


class EtoroDemoClient:
    def __init__(self, api_key: str, user_key: str, base_url: str = "https://public-api.etoro.com"):
        if not api_key or not user_key:
            raise ValueError("ETORO_API_KEY et ETORO_USER_KEY sont requis (voir .env.example)")
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"x-api-key": api_key, "x-user-key": user_key,
                               "Content-Type": "application/json"})
        self._ids: dict[str, int] = {}

    def _req(self, method, path, **kw):
        if "/real/" in path:
            raise RuntimeError("Routes de trading réel interdites dans ce bot.")
        for attempt in range(4):
            r = self.s.request(method, self.base + path, timeout=20,
                               headers={"x-request-id": str(uuid.uuid4())}, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json() if r.content else {}
        r.raise_for_status()

    # --------------------------------------------------------------- marché
    def instrument_id(self, symbol: str) -> int:
        if symbol in self._ids:
            return self._ids[symbol]
        data = self._req("GET", ENDPOINTS["search"],
                         params={"internalSymbolFull": symbol, "fields": "instrumentId,internalSymbolFull"})
        items = _find_list(data, "instrumentId") or _find_list(data, "internalInstrumentId") or []
        for it in items:
            if str(_get(it, "internalSymbolFull", "symbolFull", default="")).upper() == symbol.upper():
                iid = int(_get(it, "instrumentId", "internalInstrumentId"))
                self._ids[symbol] = iid
                return iid
        raise KeyError(f"instrument introuvable sur eToro : {symbol}")

    def candles(self, symbol: str, count: int) -> pd.DataFrame:
        iid = self.instrument_id(symbol)
        rows = []
        # l'API limite le nombre de bougies par appel
        data = self._req("GET", ENDPOINTS["candles"].format(instrument_id=iid, count=min(count, 1000)))
        items = _find_list(data, "close") or []
        for c in items:
            rows.append({
                "date": _get(c, "fromDate", "date", "time"),
                "open": _get(c, "open"), "high": _get(c, "high"), "low": _get(c, "low"),
                "close": _get(c, "close"), "volume": _get(c, "volume", default=0) or 0,
            })
        df = pd.DataFrame(rows).set_index("date")
        return df

    def last_prices(self, symbols) -> dict:
        ids = {self.instrument_id(s): s for s in symbols}
        data = self._req("GET", ENDPOINTS["rates"], params={"instrumentIds": ",".join(map(str, ids))})
        out = {}
        for r in _find_list(data, "instrumentId") or []:
            iid = int(_get(r, "instrumentId"))
            bid, ask = _get(r, "bid"), _get(r, "ask")
            px = _get(r, "lastExecution") or ((bid + ask) / 2 if bid and ask else bid or ask)
            if iid in ids and px:
                out[ids[iid]] = float(px)
        return out

    # --------------------------------------------------------------- trading démo
    def open_position(self, symbol: str, is_buy: bool, amount: float, leverage: int,
                      stop_loss: float, take_profit: float) -> dict:
        body = {
            "InstrumentID": self.instrument_id(symbol),
            "IsBuy": bool(is_buy),
            "Leverage": int(leverage),
            "Amount": round(float(amount), 2),
            "StopLossRate": round(float(stop_loss), 6),
            "TakeProfitRate": round(float(take_profit), 6),
            "IsTslEnabled": False,
        }
        return self._req("POST", ENDPOINTS["open_by_amount"], json=body)

    def close_position(self, position_id, symbol: str) -> dict:
        body = {"InstrumentId": self.instrument_id(symbol), "UnitsToDeduct": None}
        return self._req("POST", ENDPOINTS["close_position"].format(position_id=position_id), json=body)

    def portfolio(self) -> dict:
        return self._req("GET", ENDPOINTS["portfolio"])

    def open_positions(self) -> list[dict]:
        return _find_list(self.portfolio(), "positionId") or []
