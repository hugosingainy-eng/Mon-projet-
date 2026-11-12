# Quantum Edge AI — HTTP / WebSocket API

Base URL: `http://127.0.0.1:8000`. All timestamps are ISO-8601 UTC strings. All money values are EUR
unless a `currency` field says otherwise. Any numeric field may be `null` when the value is not
available — the UI must show "—" in that case and never invent a value.

## Read endpoints

### `GET /api/health`
`{"ok": true, "mode": "paper", "version": "1.0.0"}`

### `GET /api/state`
```json
{
  "server_time": "2026-01-01T10:00:00+00:00",
  "experiment": {
    "status": "idle | running | paused | stopped | halted | completed",
    "mode": "paper",
    "started_at": null, "ends_at": null,
    "duration_days": 5, "elapsed_seconds": 0, "remaining_seconds": 432000,
    "halt_reason": null
  },
  "portfolio": {
    "currency": "EUR", "initial_capital": 1000.0, "equity": 1000.0, "cash": 1000.0,
    "invested": 0.0, "positions_value": 0.0, "realized_pnl": 0.0, "unrealized_pnl": 0.0,
    "fees": 0.0, "slippage": 0.0, "fx_costs": 0.0,
    "total_return_pct": 0.0, "daily_return_pct": 0.0, "max_drawdown_pct": 0.0
  },
  "trading": {
    "open_positions": 0, "closed_trades": 0, "wins": 0, "losses": 0,
    "win_rate": null, "profit_factor": null, "avg_duration_minutes": null, "expectancy": null
  },
  "lab": {
    "running": false, "target": 10000, "completed": 0, "passed": 0, "progress_pct": 0.0,
    "phase": "idle", "last_run_at": null, "message": ""
  }
}
```

### `GET /api/positions`
Array of `{id, instrument, name, asset_class, side ("long"|"short"), qty, entry_price, current_price,
currency, entry_notional_eur, value_eur, unrealized_pnl_eur, unrealized_pct, stop_price, take_profit,
strategy_id, strategy, opened_at}`

### `GET /api/trades?limit=200`
Closed trades, newest first: `{id, instrument, asset_class, side, qty, entry_price, exit_price, currency,
pnl_eur, pnl_pct, fees_eur, slippage_eur, fx_cost_eur, opened_at, closed_at, duration_minutes,
exit_reason, strategy}` (`pnl_eur` is net of all costs).

### `GET /api/equity`
Array of `{ts, equity, cash}` oldest first.

### `GET /api/market`
Array of `{instrument, name, asset_class ("crypto"|"equity"|"etf"|"forex"|"index"|"commodity"),
tradable, price, bid, ask, change_pct, volume, volatility_pct, regime ("trend_up"|"trend_down"|"range"|
"volatile"|null), provider, last_update, market_open, stale}`

### `GET /api/lab/top?limit=20`
Array of `{id, strategy, instrument, timeframe, method ("grid"|"random"|"bayesian"|"evolutionary"|"revalidation"),
params (object), trades, net_return_pct, max_drawdown_pct, sharpe, sortino, profit_factor,
val_return_pct, val_sharpe, test_return_pct, test_sharpe, stability, cost_pct, evaluation, score}`.
The unprefixed metrics cover the whole history; `train_return_pct` / `train_sharpe`, `val_*` and `test_*`
are the chronological segments. Every `*_pct` field is in percent units (1.25 means 1.25%); `win_rate`,
`confidence`, `stability` and `weight` are fractions (0..1).
`evaluation` is one of `PASS`, `FAIL_TRAIN`, `FAIL_VALIDATION`, `FAIL_TEST`, `INSUFFICIENT_TRADES`.

### `GET /api/lab/summary`
`{"by_evaluation": {"PASS": 0}, "by_method": {"grid": 0}, "by_family": {"ma_cross": 0}}`

### `GET /api/strategies`
Deployed strategies: `{id, experiment_id, strategy, instrument, timeframe, stage ("forward"|"live"|
"retired"), weight, live_trades, live_pnl_eur, shadow_trades, shadow_pnl_eur, expected_trade_pct, note,
updated_at}`

### `GET /api/agents`
14 agents: `{id, name, role, status ("idle"|"running"|"ok"|"error"|"disabled"), last_run, activity,
errors, last_error}`

### `GET /api/signals?limit=100`
`{ts, agent, instrument, direction ("long"|"short"|"neutral"), confidence (0..1), summary}`

### `GET /api/decisions?limit=100`
Risk-manager decisions: `{ts, instrument, side, strategy, approved, reason, notional_eur}`

### `GET /api/incidents?limit=100`
`{ts, severity ("info"|"warning"|"error"), component, message, recovered}`

### `GET /api/news?limit=50`
`{ts, instrument, title, publisher, url, sentiment (-1..1)}`

### `GET /api/elite`
```json
{
  "principles": [{"trader": "", "principle": "", "families": [""], "source": ""}],
  "filings": [{"institution": "", "form": "13F-HR", "report_date": "", "filing_date": "", "url": "", "freshness_days": 0}],
  "holdings": [{"institution": "", "issuer": "", "value_usd": 0, "shares": 0, "report_date": "", "filing_date": "", "source": "", "freshness_days": 0, "confidence": "high"}]
}
```
13F data is delayed by design; `freshness_days` is the age of the *report date*, never "current".

### `GET /api/report` / `GET /api/report.html`
Full performance report as JSON, or as a downloadable HTML file.

## Control endpoints

`POST /api/control/{action}` with optional JSON body `{"confirm": true}`.
Actions: `start`, `pause`, `resume`, `stop`, `emergency_stop`, `run_experiments`, `reset`.
`reset` and `emergency_stop` require `{"confirm": true}`.
Response: `{"ok": true|false, "message": "..."}`.

## WebSocket

`WS /ws` pushes `{"type": "state", "data": <same object as GET /api/state>}` every 2 seconds.
