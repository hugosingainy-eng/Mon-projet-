# Architecture

One Python process: a FastAPI server, an engine thread (one cycle per minute) and a lab thread.
State lives in SQLite (`data/quantum_edge.db`); plain SQLAlchemy, so PostgreSQL works by setting
`db_path` to a database URL.

```
providers (read-only) ──► DataHub ──► agents ──► signals ─┐
   CCXT · Yahoo · EDGAR      │                            ▼
                             └──► Lab (10,000 experiments) ──► strategies: forward ─► live
                                                                         │
                                        proposal ──► Risk Manager ──► PaperBroker ──► fill log
```

| Module | Responsibility |
|---|---|
| `config.py` | settings, cost model, risk limits, paper-only startup validation |
| `instruments.py` | universe, `tradable` flag, market sessions |
| `data/` | provider interfaces; `ccxt_provider`, `yahoo_provider`; `hub` (quotes, candles, FX, staleness) |
| `indicators.py` | causal indicators (RSI, MACD, EMA/SMA, VWAP, Bollinger, ATR, ADX, StochRSI, Donchian, S/R, Fibonacci) |
| `strategies.py` | 20 strategy families + parameter spaces, shared by research and live trading |
| `backtest.py` | next-bar-open execution, stop/target/trailing, costs, train/val/test evaluation |
| `lab.py` | grid, random, Bayesian and evolutionary search; stores every experiment |
| `broker.py` | internal paper broker, EUR ledger, audit by replaying the fill log |
| `risk.py` | Risk Manager: the only gate to the broker |
| `agents.py` | the 14 agents |
| `engine.py` | orchestration, experiment clock, controls, restart recovery |
| `elite.py` | SEC 13F ingestion and documented principles → strategy families |
| `report.py`, `api.py` | reports, HTTP/WebSocket API, static dashboard |

## The 14 agents

Analysis agents (Market Scanner, Technical Analyst, Momentum, Scalping, Swing, Crypto, Forex,
News & Sentiment, Elite Trader Intelligence) emit structured signals with evidence. They do **not**
trade. Their combined view can veto a trade (strong opposing consensus), never force one.

Operational agents: Strategy Optimizer (runs the lab), Risk Manager (final authority),
Paper Execution (fills and ledger audit), Performance Analyst (promote / down-weight / retire),
Autonomous Supervisor (feeds, agents, database, incidents). A failing agent is isolated, logged
and retried; the engine loop keeps running.

The agents are deterministic rule-based modules, not language models, and "adaptive learning" here
means measured, rule-based re-allocation and periodic re-validation — nothing more is claimed.

## Research protocol

- Signals are computed at a bar's close and executed at the next bar's open.
- Tests assert that every indicator and every family gives identical past values when future data
  changes (no look-ahead).
- Segments are chronological: 60% train, 20% validation, 20% test.
- Bayesian and evolutionary search optimise the train segment only.
- Verdict: `PASS` needs positive net return and Sharpe ≥ 0.5 on train, Sharpe ≥ 1.0 on validation,
  positive return and Sharpe ≥ 0.5 on test, enough trades in each, and profit in at least half of
  six chronological slices. Ranking uses the *weakest* segment's Sharpe × stability.
- A test on pure random walks checks that fewer than 3% of configurations pass.

## Accounting

All amounts in EUR. `cash = 1000 + Σ fill.cash_delta` and
`equity = cash + Σ position value = 1000 + realized + unrealized`. The Paper Execution agent
replays the fill log every minute and raises an incident on any mismatch.

Per-side costs (configurable): fee (crypto 10 bps, stocks/ETFs 5, forex 0.5), slippage
(crypto 5, stocks 3, forex 1), real bid/ask spread when available otherwise a modelled half-spread,
5 bps per currency conversion, 3 bps/day short borrow.

## Risk limits (defaults)

25% of equity per position · 100% total exposure (no leverage; enforced at startup) · 8 positions ·
60% per asset class and direction · 2% equity risk per trade · new trades blocked after −6% in a
day or −20% from the equity peak · 30 bps maximum spread · minimum bar turnover · one position per
instrument · stale or missing price ⇒ no trade.

## Controls

START · PAUSE (no new trades, stops stay active, clock keeps running) · RESUME · STOP (flatten) ·
EMERGENCY STOP (halt + flatten now; positions on closed markets close at the first fresh price) ·
RUN 10,000 EXPERIMENTS · EXPORT REPORT · RESET PAPER PORTFOLIO (lab results are kept).

The five-day clock is wall-clock time from START and is stored in the database, so a restart
resumes the same experiment and logs the downtime.
