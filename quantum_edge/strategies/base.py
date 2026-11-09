"""Interface commune des stratégies (achat uniquement dans cette configuration).

Une stratégie = une famille + un jeu de paramètres. Elle produit, pour CHAQUE
barre, un signal d'entrée et des distances de stop / objectif. Les mêmes
règles servent au backtest, à la validation, au Monte-Carlo et au live.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class StrategySpec:
    family: str
    params: tuple                     # tuple trié de (clé, valeur) pour être hashable
    direction: int = +1

    @property
    def p(self) -> dict:
        return dict(self.params)

    @property
    def id(self) -> str:
        h = hashlib.sha1(json.dumps([self.family, self.params], default=str).encode()).hexdigest()[:8]
        return f"{self.family}:{h}"

    def label(self) -> str:
        return f"{self.family}(" + ", ".join(f"{k}={v}" for k, v in self.params) + ")"


@dataclass
class Family:
    name: str
    hypothesis: str
    inspired_by: str
    grid: dict = field(default_factory=dict)       # paramètre -> valeurs testées

    def specs(self) -> list[StrategySpec]:
        keys = sorted(self.grid)
        combos = [[]]
        for k in keys:
            combos = [c + [(k, v)] for c in combos for v in self.grid[k]]
        return [StrategySpec(self.name, tuple(c)) for c in combos]

    def signals(self, df: pd.DataFrame, p: dict, ctx: dict) -> pd.DataFrame:  # pragma: no cover
        raise NotImplementedError


def frame(df: pd.DataFrame, entry: pd.Series, stop_dist: pd.Series, rr: float) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["entry"] = entry.fillna(False).astype(bool)
    out["stop_dist"] = stop_dist
    out["target_dist"] = stop_dist * rr
    out["entry"] &= out["stop_dist"].gt(0) & out["stop_dist"].lt(df["close"] * 0.5)
    return out
