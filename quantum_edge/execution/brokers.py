"""Back-ends d'exécution.

* SimulatedBroker : exécution 100 % locale (aucun appel réseau), pour s'entraîner
  avant d'avoir des clés. Tout ce qu'il produit est étiqueté SIMULATED.
* EtoroDemoBroker : ordres envoyés au compte DÉMO eToro. Un ordre n'est "confirmé"
  que si la position apparaît réellement dans le portefeuille démo.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .. import safety
from .etoro_client import ApiError, _get


@dataclass
class OrderResult:
    state: str                      # confirmed | rejected | uncertain
    broker_order_id: str | None = None
    broker_position_id: str | None = None
    fill_price: float | None = None
    units: float | None = None
    message: str = ""
    raw: dict = field(default_factory=dict)


class SimulatedBroker:
    name = "simulated"
    simulated = True

    def __init__(self, slippage: float = 0.0005):
        self.slippage = slippage
        self._n = 0

    def submit_open(self, symbol, amount, price, stop, target, client_key) -> OrderResult:
        safety.check_order(True, 1, amount, amount)
        self._n += 1
        fill = price * (1 + self.slippage)
        return OrderResult("confirmed", f"SIM-O{self._n}", f"SIM-P{self._n}", fill, amount / fill,
                           "exécution simulée")

    def close(self, position: dict, price: float) -> OrderResult:
        return OrderResult("confirmed", fill_price=price * (1 - self.slippage), message="clôture simulée")

    def remote_positions(self) -> list[dict] | None:
        return None   # pas de courtier distant : rien à rapprocher


class EtoroDemoBroker:
    name = "etoro_demo"
    simulated = False

    def __init__(self, client, confirm_attempts: int = 4, confirm_wait: float = 2.0):
        self.client = client
        self.confirm_attempts = confirm_attempts
        self.confirm_wait = confirm_wait

    @staticmethod
    def _ids(resp) -> tuple[str | None, str | None]:
        order = position = None
        stack = [resp]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                order = order or _get(x, "orderId", "orderID")
                position = position or _get(x, "positionId", "positionID")
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
            elif isinstance(x, list):
                stack.extend(x)
        return (str(order) if order is not None else None, str(position) if position is not None else None)

    def _find(self, order_id, position_id):
        for p in self.client.positions():
            if position_id and str(_get(p, "positionId", "positionID")) == position_id:
                return p
            if order_id and str(_get(p, "orderId", "orderID")) == order_id:
                return p
        return None

    def submit_open(self, symbol, amount, price, stop, target, client_key) -> OrderResult:
        safety.check_order(True, 1, amount, amount)
        try:
            resp = self.client.open_by_amount(symbol, amount, stop, target, leverage=1, is_buy=True)
        except ApiError as e:
            if 400 <= e.status < 500:
                return OrderResult("rejected", message=str(e))
            return OrderResult("uncertain", message=str(e))
        except Exception as e:  # délai dépassé, coupure... : l'ordre a PEUT-ÊTRE été exécuté
            return OrderResult("uncertain", message=f"{type(e).__name__}: {e}")
        oid, pid = self._ids(resp)
        for _ in range(self.confirm_attempts):
            time.sleep(self.confirm_wait)
            try:
                p = self._find(oid, pid)
            except Exception:
                p = None
            if p is not None:
                rate = _get(p, "openRate", "rate")
                units = _get(p, "units", "amountInUnits")
                return OrderResult("confirmed", oid, str(_get(p, "positionId", "positionID")),
                                   float(rate) if rate else price, float(units) if units else None,
                                   "position visible dans le portefeuille démo", resp if isinstance(resp, dict) else {})
        return OrderResult("uncertain", oid, pid, message="ordre envoyé mais position non visible : à rapprocher",
                           raw=resp if isinstance(resp, dict) else {})

    def close(self, position: dict, price: float) -> OrderResult:
        pid = position.get("broker_position_id")
        if not pid:
            return OrderResult("rejected", message="pas d'identifiant de position eToro")
        try:
            self.client.close_position(pid, position["symbol"])
        except ApiError as e:
            if 400 <= e.status < 500:
                return OrderResult("rejected", message=str(e))
            return OrderResult("uncertain", message=str(e))
        except Exception as e:
            return OrderResult("uncertain", message=f"{type(e).__name__}: {e}")
        for _ in range(self.confirm_attempts):
            time.sleep(self.confirm_wait)
            try:
                if self._find(None, str(pid)) is None:
                    return OrderResult("confirmed", fill_price=price, message="position fermée (prix estimé)")
            except Exception:
                pass
        return OrderResult("uncertain", message="clôture envoyée, position encore visible")

    def remote_positions(self) -> list[dict] | None:
        return self.client.positions()

