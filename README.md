# Quantum Edge AI

Autonomous multi-market quantitative research and **paper-trading** laboratory.
It scans crypto, stocks, ETFs and forex, runs 10,000+ strategy experiments, forward-tests the
survivors on live prices and trades a **virtual €1,000** portfolio for five days — with a real-time
dashboard.

> **Paper trading only.** There is no live mode, no broker connection, no order endpoint and no
> credential field anywhere in the code. Nothing here is financial advice, and simulated results do
> not predict real-money results.

## Démarrage rapide (Windows)

1. Installez [Python 3.11 ou plus récent](https://www.python.org/downloads/) (cochez « Add Python to PATH »).
2. Téléchargez ce dépôt, puis double-cliquez dans l'ordre :

| Fichier | Rôle |
|---|---|
| `install.bat` | crée l'environnement et installe les dépendances (une seule fois) |
| `selfcheck.bat` | vérifie depuis votre ordinateur que chaque source de données répond |
| `start.bat` | lance l'application dans sa propre fenêtre et ouvre http://127.0.0.1:8000 |
| `stop.bat` | arrête l'application (l'expérience reprend au prochain `start.bat`) |
| `test.bat` | lance la suite de tests |

3. Dans le tableau de bord, onglet **System** → **START**. Le laboratoire lance alors les 10 000
   expériences, puis le trading simulé démarre tout seul.

Pour que les 5 jours soient continus, désactivez la mise en veille de l'ordinateur. Si l'ordinateur
redémarre, relancez `start.bat` : le portefeuille, l'historique et l'horloge sont conservés.

## Quick start (any OS)

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt      # macOS/Linux: .venv/bin/python
.venv\Scripts\python -m quantum_edge selfcheck               # test the live data sources
.venv\Scripts\python -m quantum_edge                         # run; dashboard on http://127.0.0.1:8000
.venv\Scripts\python -m quantum_edge stop                    # stop the process
.venv\Scripts\python -m pytest tests -q                      # run the tests
```

Node.js is **not** needed: the built dashboard is committed in `frontend/dist`.
Settings: copy `config.example.json` to `config.json` (all keys optional).

## What happens after START

1. **Research** — the Strategy Optimizer downloads history (15m and 1h bars) and runs 10,000
   distinct configurations across 20 strategy families using grid, random, Bayesian (Optuna TPE) and
   evolutionary search. Each one is scored on chronological train / validation / untouched-test
   segments, after costs.
2. **Forward test** — the best `PASS` configurations trade a *shadow* book on live prices with no
   capital. Only those that are profitable there are promoted.
3. **Live paper trading** — promoted strategies propose trades; the Risk Manager approves, resizes
   or rejects every one; the internal simulator fills approved orders at observed prices plus
   fees, spread, slippage and FX costs.
4. **Adaptation** — the Performance Analyst compares live results with the backtest, down-weights
   or retires strategies, and research is re-run every 24 hours.
5. **End** — after five days positions are closed and `data/reports/final_report.html` is written.

No trade is ever opened just to be active: if no validated strategy signals, nothing is traded.

## Honest limits

- **Not verified against live feeds by the author.** The software was built in a sandbox without
  access to market-data hosts. All 66 automated tests pass, but they use offline synthetic series.
  Run `selfcheck` first; it tests every provider from your machine.
- **Data.** Crypto comes from public exchange endpoints via CCXT (Binance, then Kraken; EUR pairs).
  Everything else comes from Yahoo Finance, which is unofficial, can be delayed or rate-limited and
  has no bid/ask (a modelled spread is used). Intraday history is short there (15m: 60 days).
- **Not tradable ≠ not visible.** Raw indices and futures are monitored only; index and commodity
  exposure is traded through ETFs (SPY, QQQ, GLD, USO…).
- **Simulation assumptions.** Short selling, fractional quantities and immediate fills at the quoted
  price are assumed. Prices are polled about once a minute: no high-frequency trading is simulated.
- **Statistics.** Among 10,000 experiments some pass by luck, and five days is far too short to
  prove an edge. Treat the result as an experiment, not as evidence of a money-making system.
- **Not implemented.** Economic calendar and interest-rate expectations (no free keyless source),
  on-chain data, Alpaca. 13F ingestion is included but off until you set `sec_user_agent`
  (the SEC requires a contact string); it was not tested against the live SEC site.

More: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/API.md](docs/API.md)
