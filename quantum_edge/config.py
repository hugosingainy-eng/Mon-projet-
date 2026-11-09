"""Configuration de Quantum Edge AI.

Les limites de risque sont des PLAFONDS stricts, pas des objectifs.
Les valeurs de sécurité (mode démo, pas de levier, pas de short) sont aussi
imposées dans `safety.py` : modifier ce fichier ne suffit pas à les contourner.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

CODE_ROOT = Path(__file__).resolve().parent.parent     # code, frontend, config/
ROOT = Path(os.getenv("QE_ROOT", CODE_ROOT))             # données, journaux, rapports

# Coûts aller-retour estimés (spread + frais) par classe d'actif.
# eToro : actions US ~0 commission mais spread ; ETF idem ; crypto 1 % par côté.
ASSET_COSTS = {"stock": 0.0015, "etf": 0.0010, "crypto": 0.0200, "commodity": 0.0010}
SLIPPAGE_PER_SIDE = 0.0005

# Univers par défaut : actions et ETF US très liquides (gratuits sur Yahoo, disponibles
# sur eToro). La crypto est exclue : ses frais (2 % aller-retour) dépassent le risque
# autorisé de 0,50 $ par trade sur un budget de 100 $.
DEFAULT_UNIVERSE = {
    "SPY": "etf", "QQQ": "etf", "IWM": "etf", "DIA": "etf", "GLD": "etf", "TLT": "etf",
    "XLE": "etf", "XLF": "etf", "XLK": "etf", "XLV": "etf",
    "AAPL": "stock", "MSFT": "stock", "NVDA": "stock", "AMZN": "stock", "GOOGL": "stock",
    "META": "stock", "JPM": "stock", "XOM": "stock", "LLY": "stock", "COST": "stock",
}


@dataclass(frozen=True)
class RiskLimits:
    """Partie 2/7 du cahier des charges. Valeurs en fraction du capital initial."""
    starting_capital: float = 100.0
    risk_per_trade: float = 0.005      # 0,50 $
    daily_loss: float = 0.01           # 1 $
    weekly_loss: float = 0.025         # 2,50 $
    max_drawdown: float = 0.05         # 5 $
    max_positions: int = 3
    min_reward_risk: float = 2.0
    max_position_frac: float = 0.40    # 40 $ max par position
    max_total_exposure: float = 1.0    # jamais plus que le capital
    max_correlation: float = 0.70      # corrélation max avec une position ouverte
    max_cost_to_risk: float = 0.25     # les coûts ne doivent pas manger >25 % du risque
    min_order_usd: float = 10.0        # minimum eToro (à vérifier par instrument)


@dataclass
class ResearchConfig:
    history_years: int = 10
    train_frac: float = 0.60
    valid_frac: float = 0.20           # le reste (20 %) = test final
    wf_train_bars: int = 756           # 3 ans
    wf_test_bars: int = 252            # 1 an
    min_trades_oos: int = 30
    min_profit_factor: float = 1.15
    min_ev_r: float = 0.05
    min_wf_consistency: float = 0.50
    min_param_stability: float = 0.50
    max_risk_of_ruin: float = 0.50     # P(drawdown >= 5 %) sur 100 trades
    mc_sequences: int = 20_000
    seed: int = 42


@dataclass
class SimConfig:
    candidate_paths: int = 50_000      # Monte-Carlo par trade candidat
    horizon_bars: int = 15
    shrinkage: float = 0.40
    min_expected_r: float = 0.05
    max_p_big_loss: float = 0.15


@dataclass
class Settings:
    trading_mode: str = field(default_factory=lambda: os.getenv("TRADING_MODE", "DEMO"))
    execution_backend: str = field(default_factory=lambda: os.getenv("EXECUTION_BACKEND", "simulated"))  # simulated | etoro_demo
    data_source: str = field(default_factory=lambda: os.getenv("DATA_SOURCE", "yahoo"))                  # yahoo | etoro | csv | synthetic
    etoro_api_key: str = field(default_factory=lambda: os.getenv("ETORO_API_KEY", ""))
    etoro_user_key: str = field(default_factory=lambda: os.getenv("ETORO_USER_KEY", ""))
    etoro_base_url: str = field(default_factory=lambda: os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com"))
    xai_api_key: str = field(default_factory=lambda: os.getenv("XAI_API_KEY", ""))                       # Grok : optionnel, payant
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    dashboard_token: str = field(default_factory=lambda: os.getenv("DASHBOARD_TOKEN", ""))
    root: Path = field(default_factory=lambda: Path(os.getenv("QE_ROOT", ROOT)))
    db_path: Path = field(default_factory=lambda: Path(os.getenv("QE_DB", Path(os.getenv("QE_ROOT", ROOT)) / "data" / "quantum_edge.db")))
    universe: dict = field(default_factory=lambda: dict(DEFAULT_UNIVERSE))
    benchmark: str = "SPY"
    max_data_age_days: int = 4          # au-delà, la donnée journalière est périmée
    loop_seconds: int = 300             # surveillance toutes les 5 minutes
    scan_time_ny: tuple = (15, 35)      # scan 25 min avant la clôture de New York
    report_time_ny: tuple = (16, 30)
    require_earnings_check: bool = True
    risk: RiskLimits = field(default_factory=RiskLimits)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    sim: SimConfig = field(default_factory=SimConfig)

    def cost_for(self, symbol: str) -> float:
        return ASSET_COSTS.get(self.universe.get(symbol, "stock"), 0.0015)

    def asset_class(self, symbol: str) -> str:
        return self.universe.get(symbol, "stock")

    @property
    def paths(self) -> dict:
        p = {k: self.root / k for k in ("data", "logs", "reports", "research")}
        for v in p.values():
            v.mkdir(parents=True, exist_ok=True)
        return p
