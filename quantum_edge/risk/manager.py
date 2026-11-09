"""Risk Manager : droit de veto ABSOLU. Le Master Agent ne peut pas le contourner.

Règles (plafonds stricts) :
  * risque par trade <= 0,5 % (0,50 $), coûts inclus ;
  * perte journalière <= 1 %, hebdomadaire <= 2,5 %, drawdown <= 5 % -> coupe-circuit ;
  * le risque cumulé jusqu'aux stops de toutes les positions ne peut pas dépasser
    la perte journalière encore autorisée (même si tout touche le stop le même jour,
    la limite de 1 % est respectée) ;
  * 3 positions max, une seule par actif, corrélation <= 0,70 ;
  * ratio gain/risque >= 2:1, coûts <= 25 % du risque ;
  * pas de levier, pas de short, minimum d'ordre eToro respecté sinon REJET ;
  * le risque ne monte jamais pour "se refaire".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..config import SLIPPAGE_PER_SIDE, RiskLimits


@dataclass
class RiskVerdict:
    approved: bool
    amount: float = 0.0
    risk_usd: float = 0.0
    reasons: list = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    budget: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def limit_breaches(acc: dict, equity: float, lim: RiskLimits) -> list[str]:
    cap = acc["starting_capital"]
    out = []
    if acc["day_start_equity"] - equity >= lim.daily_loss * cap - 1e-9:
        out.append(f"perte journalière {acc['day_start_equity'] - equity:.2f} $ >= {lim.daily_loss * cap:.2f} $")
    if acc["week_start_equity"] - equity >= lim.weekly_loss * cap - 1e-9:
        out.append(f"perte hebdomadaire {acc['week_start_equity'] - equity:.2f} $ >= {lim.weekly_loss * cap:.2f} $")
    if acc["peak_equity"] - equity >= lim.max_drawdown * cap - 1e-9:
        out.append(f"drawdown {acc['peak_equity'] - equity:.2f} $ >= {lim.max_drawdown * cap:.2f} $")
    return out


def evaluate_trade(*, symbol: str, direction: int, leverage: int, price: float, stop_pct: float, target_pct: float,
                   cost_pct: float, acc: dict, equity: float, cash: float, open_positions: list[dict],
                   open_risk_usd: float, max_corr: float, entries_allowed: tuple, lim: RiskLimits) -> RiskVerdict:
    cap = acc["starting_capital"]
    slip = 2 * SLIPPAGE_PER_SIDE
    risk_frac_per_unit = stop_pct + cost_pct + slip
    rr = target_pct / stop_pct if stop_pct > 0 else 0.0
    cost_to_risk = (cost_pct + slip) / risk_frac_per_unit if risk_frac_per_unit > 0 else 1.0

    day_left = lim.daily_loss * cap - max(0.0, acc["day_start_equity"] - equity)
    week_left = lim.weekly_loss * cap - max(0.0, acc["week_start_equity"] - equity)
    dd_left = lim.max_drawdown * cap - max(0.0, acc["peak_equity"] - equity)
    loss_budget = min(day_left, week_left, dd_left) - open_risk_usd
    risk_usd = min(lim.risk_per_trade * cap, lim.risk_per_trade * equity, loss_budget)

    amount = risk_usd / risk_frac_per_unit if risk_usd > 0 and risk_frac_per_unit > 0 else 0.0
    room = lim.max_total_exposure * equity - sum(p["amount"] for p in open_positions)
    amount = min(amount, lim.max_position_frac * equity, room, cash)
    amount = round(max(amount, 0.0), 2)
    real_risk = amount * risk_frac_per_unit

    checks = {
        "entrées autorisées (coupe-circuit / urgence)": entries_allowed[0],
        "achat uniquement (short désactivé)": direction > 0,
        "sans levier": leverage == 1,
        f"moins de {lim.max_positions} positions": len(open_positions) < lim.max_positions,
        "pas déjà investi sur cet actif": symbol not in {p["symbol"] for p in open_positions},
        f"ratio gain/risque ≥ {lim.min_reward_risk}": rr >= lim.min_reward_risk - 1e-9,
        f"coûts ≤ {lim.max_cost_to_risk:.0%} du risque": cost_to_risk <= lim.max_cost_to_risk,
        f"corrélation ≤ {lim.max_correlation}": max_corr <= lim.max_correlation,
        "budget de perte restant > 0": loss_budget > 0,
        f"taille ≥ minimum eToro ({lim.min_order_usd:.0f} $) pour le risque autorisé": amount >= lim.min_order_usd,
        "risque réel ≤ 0,5 % du capital": real_risk <= lim.risk_per_trade * cap + 1e-6,
    }
    reasons = [k for k, ok in checks.items() if not ok]
    if not entries_allowed[0]:
        reasons.insert(0, entries_allowed[1])
    return RiskVerdict(
        approved=not reasons, amount=amount if not reasons else 0.0, risk_usd=round(real_risk, 4),
        reasons=reasons, checks=checks,
        budget={"day_left": day_left, "week_left": week_left, "dd_left": dd_left, "open_risk": open_risk_usd,
                "loss_budget": loss_budget, "reward_risk": rr, "cost_to_risk": cost_to_risk},
    )
