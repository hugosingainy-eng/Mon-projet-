"""Configuration centrale du bot.

Tous les paramètres de risque sont volontairement prudents : la priorité d'un
bon trader est de survivre (protéger le capital), la rentabilité vient ensuite.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # optionnel
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


# Classe d'actif -> coûts aller-retour estimés (spread + frais), en fraction.
# eToro : actions/ETF ~0,15 % de spread aller-retour, crypto 1 % par côté.
ASSET_COSTS = {
    "stock": 0.0015,
    "etf": 0.0010,
    "crypto": 0.0200,
    "commodity": 0.0010,
    "index": 0.0008,
    "fx": 0.0004,
}

# Frais overnight approximatifs par jour pour les positions CFD (short / levier).
OVERNIGHT_FEE_PER_DAY = 0.0002

DEFAULT_WATCHLIST = {
    # symbole eToro : classe d'actif
    "SPY": "etf",
    "QQQ": "etf",
    "AAPL": "stock",
    "MSFT": "stock",
    "NVDA": "stock",
    "AMZN": "stock",
    "GOOGL": "stock",
    "META": "stock",
    "TSLA": "stock",
    "AMD": "stock",
    "AVGO": "stock",
    "JPM": "stock",
    "XOM": "stock",
    "LLY": "stock",
    "GLD": "etf",
    "BTC": "crypto",
    "ETH": "crypto",
}


@dataclass
class RiskConfig:
    starting_capital: float = 100.0      # budget virtuel alloué au bot
    risk_per_trade: float = 0.01         # 1 % du capital risqué par trade (jusqu'à x2 si forte conviction)
    max_risk_per_trade: float = 0.02
    max_position_frac: float = 0.30      # max 30 % du capital dans une seule position
    max_open_positions: int = 5
    max_total_exposure: float = 1.0      # pas plus de 100 % du capital investi
    leverage: int = 1                    # pas de levier par défaut
    min_position_usd: float = 10.0       # minimum eToro
    weekly_loss_limit: float = 0.06      # stop des nouvelles entrées si -6 % sur la semaine
    max_drawdown_kill: float = 0.20      # coupe tout si -20 % depuis le plus haut
    allow_short: bool = True             # shorts = CFD sur eToro (frais overnight)
    kelly_fraction: float = 0.25         # quart de Kelly, jamais Kelly plein


@dataclass
class SimulationConfig:
    mc_paths: int = 50_000               # trajectoires Monte-Carlo par trade candidat
    horizon_bars: int = 15               # durée max d'un trade (en barres journalières)
    shrinkage: float = 0.40              # part des trajectoires "sans edge" (anti sur-optimisation)
    min_hist_trades: int = 20            # nb minimum d'occurrences historiques du setup
    min_profit_factor: float = 1.20
    min_expected_r: float = 0.10         # espérance minimale en multiples du risque (R)
    min_p_win: float = 0.38
    max_p_big_loss: float = 0.15         # proba max de perdre > 1,5 R (gaps)
    min_tstat: float = 1.0               # robustesse statistique de l'edge historique
    workers: int = max(1, (os.cpu_count() or 2) - 1)
    seed: int | None = None


@dataclass
class BotConfig:
    mode: str = os.getenv("BOT_MODE", "paper")       # paper | demo
    api_key: str = os.getenv("ETORO_API_KEY", "")
    user_key: str = os.getenv("ETORO_USER_KEY", "")
    base_url: str = os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com")
    watchlist: dict = field(default_factory=lambda: dict(DEFAULT_WATCHLIST))
    benchmark: str = "SPY"
    history_bars: int = 750                          # ~3 ans de données journalières
    scan_hour_utc: int = 20                          # scan des signaux à 20h UTC (fin de séance US)
    scan_minute_utc: int = 15
    check_every_minutes: int = 15                    # surveillance des positions
    trading_days: tuple = (0, 1, 2, 3, 4)            # lundi -> vendredi
    no_new_trades_friday_after_utc: int = 18         # pas de nouvelle position juste avant le week-end
    state_dir: str = "state"
    log_dir: str = "logs"
    risk: RiskConfig = field(default_factory=RiskConfig)
    sim: SimulationConfig = field(default_factory=SimulationConfig)

    def cost_for(self, symbol: str) -> float:
        return ASSET_COSTS.get(self.watchlist.get(symbol, "stock"), 0.0015)
