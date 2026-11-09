"""Moteur de sortie vectorisé : applique stop / objectif / sortie temporelle à des
milliers (ou millions) de trajectoires en une seule passe numpy."""
from __future__ import annotations

import numpy as np


def simulate_exits(logret: np.ndarray, direction: int, stop_pct, target_pct):
    """logret : (N, H) rendements log barre par barre après l'entrée.
    stop_pct / target_pct : scalaires ou tableaux (N,).

    Retourne (rendement du trade, barres tenues, sortie: 0=temps 1=stop 2=objectif).
    Le stop est évalué sur la clôture : si le prix "gappe" au-delà du stop, la perte
    réelle (plus grande) est conservée -> estimation prudente.
    """
    logret = np.atleast_2d(logret)
    n, h = logret.shape
    stop_pct = np.broadcast_to(np.asarray(stop_pct, dtype=float), (n,))
    target_pct = np.broadcast_to(np.asarray(target_pct, dtype=float), (n,))

    ret = direction * np.expm1(np.cumsum(logret, axis=1))      # P&L latent à chaque barre
    hit_stop = ret <= -stop_pct[:, None]
    hit_tgt = ret >= target_pct[:, None]

    big = h + 1
    first_stop = np.where(hit_stop.any(1), hit_stop.argmax(1), big)
    first_tgt = np.where(hit_tgt.any(1), hit_tgt.argmax(1), big)

    out = ret[:, -1].copy()
    bars = np.full(n, h, dtype=float)
    kind = np.zeros(n, dtype=np.int8)

    stop_first = (first_stop < big) & (first_stop <= first_tgt)
    tgt_first = (first_tgt < big) & (first_tgt < first_stop)

    idx = np.arange(n)
    out[stop_first] = ret[idx[stop_first], first_stop[stop_first]]
    bars[stop_first] = first_stop[stop_first] + 1
    kind[stop_first] = 1

    out[tgt_first] = target_pct[tgt_first]                    # ordre limite : rempli à l'objectif
    bars[tgt_first] = first_tgt[tgt_first] + 1
    kind[tgt_first] = 2
    return out, bars, kind
