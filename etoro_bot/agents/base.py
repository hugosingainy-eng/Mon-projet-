"""Structures de données échangées entre les sous-agents."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Candidate:
    """Un setup détecté par un agent stratégie sur la dernière barre."""
    symbol: str
    strategy: str
    inspired_by: str
    direction: int
    price: float
    stop_pct: float
    target_pct: float
    vol: float          # volatilité réalisée journalière actuelle
    cost_pct: float
    date: str = ""

    @property
    def stop_price(self) -> float:
        return self.price * (1 - self.direction * self.stop_pct)

    @property
    def target_price(self) -> float:
        return self.price * (1 + self.direction * self.target_pct)


@dataclass
class HistoryReport:
    n_own: int = 0
    n_pool: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    mean_r: float = 0.0
    tstat: float = 0.0


@dataclass
class MonteCarloReport:
    paths: int = 0
    p_win: float = 0.0
    p_stop: float = 0.0
    p_target: float = 0.0
    p_big_loss: float = 0.0
    expected_return: float = 0.0
    expected_r: float = 0.0
    cvar5_r: float = 0.0
    median_bars: float = 0.0
    kelly: float = 0.0
    batch_agreement: float = 0.0   # part des sous-échantillons dont l'espérance est > 0


@dataclass
class RegimeReport:
    asset_regime: str = "neutral"     # bull | bear | neutral
    market_regime: str = "neutral"
    high_volatility: bool = False
    allowed: bool = True
    risk_multiplier: float = 1.0
    reason: str = ""


@dataclass
class Decision:
    candidate: Candidate
    history: HistoryReport
    mc: MonteCarloReport
    regime: RegimeReport
    approved: bool = False
    conviction: float = 0.0
    reasons: list = field(default_factory=list)
    amount: float = 0.0               # montant en $ décidé par le risk manager
    grok: object = None               # avis de l'agent Grok (actualités / sentiment)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["candidate"]["stop_price"] = self.candidate.stop_price
        d["candidate"]["target_price"] = self.candidate.target_price
        return d
