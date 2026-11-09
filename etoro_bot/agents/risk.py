"""Agent "risk manager" : il a le dernier mot.

Règles (inspirées de Paul Tudor Jones, Stanley Druckenmiller, Ed Seykota) :
  * on risque une petite fraction fixe du capital par trade (1 %, 2 % max) ;
  * on augmente la taille seulement quand la conviction est forte ;
  * jamais plus d'un quart de Kelly ;
  * limite de perte hebdomadaire et coupe-circuit sur drawdown.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import RiskConfig
from .base import Decision


@dataclass
class PortfolioState:
    equity: float
    cash: float
    peak_equity: float
    week_start_equity: float
    open_symbols: set
    exposure: float  # montant total investi


def risk_gate(state: PortfolioState, cfg: RiskConfig) -> tuple[bool, str]:
    if state.peak_equity > 0 and state.equity < state.peak_equity * (1 - cfg.max_drawdown_kill):
        return False, "COUPE-CIRCUIT : drawdown maximal atteint, plus aucune nouvelle position"
    if state.week_start_equity > 0 and state.equity < state.week_start_equity * (1 - cfg.weekly_loss_limit):
        return False, "limite de perte hebdomadaire atteinte, pause jusqu'à lundi"
    if len(state.open_symbols) >= cfg.max_open_positions:
        return False, "nombre maximal de positions ouvertes atteint"
    return True, ""


def size_position(dec: Decision, state: PortfolioState, cfg: RiskConfig) -> float:
    c = dec.candidate
    if c.symbol in state.open_symbols:
        dec.reasons.append("déjà une position sur cet actif")
        return 0.0
    risk_frac = cfg.risk_per_trade * (0.5 + dec.conviction) * dec.regime.risk_multiplier
    risk_frac = min(risk_frac, cfg.max_risk_per_trade)
    amount = state.equity * risk_frac / c.stop_pct          # taille pour risquer risk_frac
    kelly_cap = max(0.0, dec.mc.kelly) * cfg.kelly_fraction * state.equity
    amount = min(amount, kelly_cap if kelly_cap > 0 else amount)
    amount = min(amount, state.equity * cfg.max_position_frac)
    room = state.equity * cfg.max_total_exposure - state.exposure
    amount = min(amount, room, state.cash)
    if amount < cfg.min_position_usd:
        dec.reasons.append(f"taille {amount:.2f}$ < minimum {cfg.min_position_usd}$")
        return 0.0
    return round(amount, 2)
