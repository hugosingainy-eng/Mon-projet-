"""Configuration. Every value can be overridden in `config.json` (see config.example.json)
or with an environment variable `QE_<UPPERCASE_NAME>` (JSON-encoded for non-strings)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The only trading mode this software supports. There is no live mode to switch to.
PAPER_MODE = "paper"


class SecurityError(RuntimeError):
    """Raised when the paper-only guarantees would be violated."""


@dataclass
class Settings:
    # --- experiment -------------------------------------------------------------------
    trading_mode: str = PAPER_MODE
    initial_capital: float = 1000.0
    base_currency: str = "EUR"
    duration_days: float = 5.0
    db_path: str = str(ROOT / "data" / "quantum_edge.db")
    host: str = "127.0.0.1"
    port: int = 8000

    # --- loop timing (seconds) --------------------------------------------------------
    cycle_seconds: float = 60.0
    crypto_quote_seconds: float = 60.0
    yahoo_quote_seconds: float = 120.0
    agent_seconds: float = 300.0
    news_seconds: float = 1800.0
    elite_seconds: float = 86400.0
    snapshot_seconds: float = 60.0
    relab_hours: float = 24.0

    # --- data -------------------------------------------------------------------------
    crypto_exchanges: list = field(default_factory=lambda: ["binance", "kraken"])          # live quotes
    crypto_history_exchanges: list = field(default_factory=lambda: ["binance", "bitstamp", "kraken"])
    max_quote_age: dict = field(default_factory=lambda: {
        "crypto": 180, "equity": 1200, "etf": 1200, "forex": 600, "index": 1200, "commodity": 1200})
    sec_user_agent: str = ""  # SEC EDGAR requires a contact User-Agent; empty = Elite filings disabled

    # --- cost model (basis points, per side) -----------------------------------------
    fee_bps: dict = field(default_factory=lambda: {
        "crypto": 10.0, "equity": 5.0, "etf": 5.0, "forex": 0.5, "index": 2.0, "commodity": 2.0})
    slippage_bps: dict = field(default_factory=lambda: {
        "crypto": 5.0, "equity": 3.0, "etf": 3.0, "forex": 1.0, "index": 3.0, "commodity": 3.0})
    # used only when the provider gives no real bid/ask
    half_spread_bps: dict = field(default_factory=lambda: {
        "crypto": 2.0, "equity": 2.0, "etf": 2.0, "forex": 1.0, "index": 2.0, "commodity": 3.0})
    fx_cost_bps: float = 5.0            # charged on each conversion EUR <-> quote currency
    short_borrow_bps_per_day: float = 3.0

    # --- risk limits ("aggressive, no leverage") --------------------------------------
    allow_short: bool = True
    allow_fractional: bool = True
    max_position_pct: float = 0.25
    max_exposure_pct: float = 1.0
    max_positions: int = 8
    max_class_exposure_pct: float = 0.6   # correlated-exposure proxy: same asset class + direction
    risk_per_trade_pct: float = 0.02
    max_daily_loss_pct: float = 0.06
    max_drawdown_pct: float = 0.20
    max_spread_bps: float = 30.0
    min_bar_turnover_eur: float = 20000.0
    min_notional_eur: float = 20.0
    agent_veto_threshold: float = 1.2

    # --- strategy lab -----------------------------------------------------------------
    lab_target: int = 10000
    lab_timeframes: list = field(default_factory=lambda: ["5m", "15m", "1h"])
    # a five-day experiment needs strategies that actually trade: minimum average number of
    # trades per calendar day (over the whole backtest) for a configuration to be deployed
    lab_min_trades_per_day: float = 1.0
    lab_crypto_bars: int = 12000
    lab_min_bars: int = 600
    lab_seed: int = 42
    lab_train: float = 0.6
    lab_val: float = 0.2
    lab_min_trades_train: int = 30
    lab_min_trades_oos: int = 8
    lab_deploy_top: int = 12
    lab_deploy_per_instrument: int = 2

    # --- forward test / adaptive learning ---------------------------------------------
    forward_min_trades: int = 2
    forward_min_hours: float = 6.0
    forward_max_trades: int = 6
    shadow_notional_eur: float = 100.0
    retire_min_trades: int = 4
    retire_loss_pct_of_equity: float = 0.02

    def cost_per_side(self, asset_class: str, quote_ccy: str) -> float:
        """Fractional one-way cost used by the backtester (fee + slippage + half spread + FX)."""
        bps = (self.fee_bps[asset_class] + self.slippage_bps[asset_class]
               + self.half_spread_bps[asset_class])
        if quote_ccy != self.base_currency and asset_class != "forex":
            bps += self.fx_cost_bps
        return bps / 1e4


def load_settings(path: str | None = None) -> Settings:
    s = Settings()
    cfg_path = Path(path or os.environ.get("QE_CONFIG", ROOT / "config.json"))
    data = {}
    if cfg_path.exists():
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    for f in fields(Settings):
        env = os.environ.get("QE_" + f.name.upper())
        if env is not None:
            try:
                data[f.name] = json.loads(env)
            except json.JSONDecodeError:
                data[f.name] = env
        if f.name in data:
            cur = getattr(s, f.name)
            val = data[f.name]
            if isinstance(cur, dict) and isinstance(val, dict):
                cur.update(val)
            else:
                setattr(s, f.name, type(cur)(val) if isinstance(cur, (int, float)) and not isinstance(cur, bool) else val)
    validate_paper_only(s)
    return s


def validate_paper_only(s: Settings) -> None:
    """Startup validation: refuse to run in anything but paper mode, with no leverage and
    with no broker credentials present in the environment."""
    if s.trading_mode != PAPER_MODE:
        raise SecurityError(f"trading_mode={s.trading_mode!r} is not supported: paper trading only")
    if s.max_exposure_pct > 1.0:
        raise SecurityError("max_exposure_pct > 1.0 would be leverage, which is disabled")
    for key in os.environ:
        k = key.upper()
        if k.startswith("QE_") and any(t in k for t in ("API_KEY", "APIKEY", "SECRET", "PASSWORD")):
            raise SecurityError(f"credential-like variable {key} found; this app never uses broker credentials")
