"""Moteur de simulation de trades, identique pour toutes les stratégies en compétition.

Règles d'exécution (prudentes) :
  * entrée à la clôture de la barre du signal (ou à l'ouverture suivante si delay=1) ;
  * stop-loss touché si le plus bas <= stop ; sortie au stop, ou à l'ouverture si gap ;
  * objectif touché si le plus haut >= objectif ; sortie à l'objectif (ordre limite) ;
  * si stop ET objectif sont dans la même barre : on suppose le STOP (pire cas) ;
  * sortie à la clôture après `max_hold` barres ;
  * coûts = spread aller-retour + slippage à l'entrée et à la sortie ;
  * pas de nouvelle entrée tant que le trade précédent n'est pas clos (pas d'empilement).
Résultat en R = gain net / risque prévu (distance au stop + coûts).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class TradeCosts:
    spread_rt: float          # coût aller-retour
    slippage: float = 0.0005  # par côté


def simulate_trades(df: pd.DataFrame, sig: pd.DataFrame, costs: TradeCosts, max_hold: int = 15,
                    delay: int = 0, symbol: str = "", strategy_id: str = "",
                    regimes: pd.Series | None = None) -> pd.DataFrame:
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    entry = sig["entry"].to_numpy(bool)
    sd = sig["stop_dist"].to_numpy(float)
    td = sig["target_dist"].to_numpy(float)
    dates = df.index
    n = len(df)
    rows = []
    i = 0
    while i < n - 1:
        if not entry[i]:
            i += 1
            continue
        k = i + delay
        if k >= n - 1:
            break
        px = o[k] if delay else c[k]
        fill = px * (1 + costs.slippage)
        stop = fill - sd[i]
        tgt = fill + td[i]
        risk_pct = sd[i] / fill + costs.spread_rt + 2 * costs.slippage
        exit_px, reason, j = None, "time", min(k + max_hold, n - 1)
        for t in range(k + 1, min(k + max_hold, n - 1) + 1):
            if l[t] <= stop:
                exit_px, reason, j = min(o[t], stop), "stop", t
                break
            if h[t] >= tgt:
                exit_px, reason, j = max(o[t], tgt) if o[t] > tgt else tgt, "target", t
                break
        if exit_px is None:
            exit_px = c[j]
        gross = exit_px * (1 - costs.slippage) / fill - 1
        net = gross - costs.spread_rt
        rows.append({
            "symbol": symbol, "strategy": strategy_id,
            "entry_date": dates[k], "exit_date": dates[j], "entry": fill, "exit": exit_px,
            "stop": stop, "target": tgt, "bars": j - k, "reason": reason,
            "ret": net, "risk_pct": risk_pct, "r": net / risk_pct,
            "regime": regimes.iloc[i] if regimes is not None and i < len(regimes) else "",
        })
        i = j + 1
    return pd.DataFrame(rows)
