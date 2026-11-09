import numpy as np
import pandas as pd
import pytest

from etoro_bot.agents.base import Candidate
from etoro_bot.agents.committee import evaluate, find_candidates
from etoro_bot.agents.exits import simulate_exits
from etoro_bot.agents.history import SetupLibrary
from etoro_bot.agents.monte_carlo import run_monte_carlo
from etoro_bot.agents.risk import PortfolioState, risk_gate
from etoro_bot.backtest import run_backtest
from etoro_bot.broker import Ledger, PaperBroker
from etoro_bot.config import BotConfig
from etoro_bot.data import SyntheticData
from etoro_bot.strategies import ALL_STRATEGIES


def small_cfg():
    cfg = BotConfig()
    cfg.watchlist = {"SPY": "etf", "AAPL": "stock", "NVDA": "stock", "BTC": "crypto"}
    cfg.sim.mc_paths = 3000
    cfg.sim.workers = 1
    cfg.sim.seed = 1
    return cfg


def test_exits_stop_target_time():
    lr = np.log(np.array([
        [1.01, 1.01, 1.10],     # objectif touché à la barre 3
        [0.97, 0.99, 1.00],     # stop touché barre 1 (gap -3 % > stop 2 %)
        [1.00, 1.005, 1.005],   # sortie au temps
    ]))
    ret, bars, kind = simulate_exits(lr, +1, 0.02, 0.05)
    assert kind.tolist() == [2, 1, 0]
    assert ret[0] == pytest.approx(0.05)
    assert ret[1] == pytest.approx(-0.03)            # la perte du gap est conservée
    assert bars.tolist() == [3, 1, 3]


def test_short_exits_are_mirrored():
    lr = np.log(np.array([[0.94, 1.0]]))
    ret, _, kind = simulate_exits(lr, -1, 0.02, 0.05)
    assert kind[0] == 2 and ret[0] == pytest.approx(0.05)


def test_monte_carlo_without_edge_is_negative_after_costs():
    rng = np.random.default_rng(0)
    z = rng.standard_normal(2000)
    cond = rng.standard_normal((300, 15))       # setup sans aucun pouvoir prédictif
    c = Candidate("X", "s", "", +1, 100.0, 0.04, 0.06, 0.02, 0.002)
    rep = run_monte_carlo(c, cond, np.empty((0, 15)), z, 40000, 15, 0.4, rng=rng)
    assert rep.paths == 40000
    assert rep.expected_r < 0.05


def test_monte_carlo_detects_real_edge():
    rng = np.random.default_rng(0)
    z = rng.standard_normal(2000)
    cond = rng.standard_normal((300, 15)) + 0.6  # le setup est suivi d'une hausse
    c = Candidate("X", "s", "", +1, 100.0, 0.04, 0.06, 0.02, 0.002)
    rep = run_monte_carlo(c, cond, np.empty((0, 15)), z, 40000, 15, 0.4, rng=rng)
    assert rep.expected_r > 0.2 and rep.batch_agreement == 1.0


def test_no_lookahead_in_history_queries():
    cfg = small_cfg()
    data = SyntheticData().load(cfg.watchlist, 800)
    lib = SetupLibrary(data, ALL_STRATEGIES, cfg.sim.horizon_bars, {})
    asof = list(data["SPY"].index)[400]
    for s in ALL_STRATEGIES:
        for sym in data:
            rec = lib.records[(sym, s.name)]
            own_z, own_r, pool_z, pool_r = lib.query(sym, s.name, asof)
            assert len(own_r) == int((rec.avail_dates <= np.datetime64(asof)).sum())


def test_strategies_signals_have_positive_risk():
    df = SyntheticData().history("AAPL", 800)
    for s in ALL_STRATEGIES:
        sig = s.signals(df)
        e = sig[sig["entry"]]
        assert (e["stop_dist"] > 0).all() and (e["target_dist"] > 0).all()


def test_risk_gate_kill_switch_and_weekly_limit():
    cfg = BotConfig().risk
    st = PortfolioState(equity=79, cash=79, peak_equity=100, week_start_equity=80, open_symbols=set(), exposure=0)
    assert not risk_gate(st, cfg)[0]
    st = PortfolioState(equity=93, cash=93, peak_equity=100, week_start_equity=100, open_symbols=set(), exposure=0)
    assert not risk_gate(st, cfg)[0]
    st = PortfolioState(equity=99, cash=99, peak_equity=100, week_start_equity=100, open_symbols=set(), exposure=0)
    assert risk_gate(st, cfg)[0]


def test_ledger_round_trip(tmp_path):
    cfg = small_cfg()
    data = SyntheticData().load(cfg.watchlist, 800)
    lib = SetupLibrary(data, ALL_STRATEGIES, cfg.sim.horizon_bars, {})
    dates = list(data["SPY"].index)
    cand = None
    for t in dates[300:]:
        cs = find_candidates(lib, cfg, t)
        if cs:
            cand = cs[0]
            break
    assert cand is not None
    dec = evaluate(cand, lib, cfg, seed=0)
    led = Ledger(100.0, str(tmp_path / "l.json"))
    br = PaperBroker(led)
    p = br.open(dec, 20.0, cand.price)
    assert led.cash == pytest.approx(80.0)
    br.close(p, cand.price * 1.10 if cand.direction > 0 else cand.price * 0.90, "test")
    assert led.cash > 100.0
    led.save()
    assert Ledger(100.0, str(tmp_path / "l.json")).cash == pytest.approx(led.cash)


def test_full_backtest_runs_and_respects_risk():
    cfg = small_cfg()
    data = SyntheticData().load(cfg.watchlist, 800)
    res = run_backtest(cfg, data)
    assert res["final_equity"] > 0
    assert res["max_drawdown"] > -cfg.risk.max_drawdown_kill - 0.05
    assert 0 < res["monte_carlo_paths"] <= res["candidates_reviewed"] * cfg.sim.mc_paths


def test_client_refuses_missing_keys_and_real_routes():
    from etoro_bot.etoro_client import EtoroDemoClient

    with pytest.raises(ValueError):
        EtoroDemoClient("", "")
    c = EtoroDemoClient("a", "b")
    with pytest.raises(RuntimeError):
        c._req("GET", "/api/v1/trading/info/real/portfolio")
