"""Indicators, strategies, backtester and the experiment lab."""
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select

from quantum_edge import backtest, indicators as ti
from quantum_edge.db import LabExperiment
from quantum_edge.lab import GRID_DEFAULTS, Lab
from quantum_edge.strategies import FAMILIES, Data, signals, space_for
from tests.conftest import synthetic_candles


@pytest.fixture(scope="module")
def df():
    return synthetic_candles(7, 1500)


def test_sma_and_rsi_basics(df):
    c = df["close"].to_numpy()
    assert np.isclose(ti.sma(c, 10)[-1], c[-10:].mean())
    r = ti.rsi(c, 14)
    assert np.nanmin(r) >= 0 and np.nanmax(r) <= 100
    assert np.all(ti.rsi(np.arange(1.0, 100.0), 14)[20:] == 100)          # only gains -> RSI 100
    lo, mid, up = ti.bollinger(c)
    assert np.all(lo[30:] <= mid[30:]) and np.all(mid[30:] <= up[30:])
    assert np.all(ti.atr(df["high"], df["low"], c)[20:] > 0)


def test_indicators_are_causal(df):
    """Changing FUTURE bars must not change any past indicator value."""
    o, h, l, c, v = (df[k].to_numpy().copy() for k in ("open", "high", "low", "close", "volume"))
    cut = 1000
    h2, l2, c2 = h.copy(), l.copy(), c.copy()
    c2[cut:] *= 3; h2[cut:] *= 3; l2[cut:] *= 3
    pairs = [(ti.ema(c, 20), ti.ema(c2, 20)), (ti.rsi(c), ti.rsi(c2)), (ti.macd(c)[2], ti.macd(c2)[2]),
             (ti.atr(h, l, c), ti.atr(h2, l2, c2)), (ti.adx(h, l, c), ti.adx(h2, l2, c2)),
             (ti.stoch_rsi(c), ti.stoch_rsi(c2)), (ti.donchian(h, l, 20)[1], ti.donchian(h2, l2, 20)[1]),
             (ti.support_resistance(h, l, 10)[0], ti.support_resistance(h2, l2, 10)[0]),
             (ti.rolling_vwap(h, l, c, v, 50), ti.rolling_vwap(h2, l2, c2, v, 50))]
    for a, b in pairs:
        assert np.allclose(a[:cut], b[:cut], equal_nan=True)


@pytest.mark.parametrize("family", list(FAMILIES))
def test_every_family_has_no_lookahead(family, df):
    """Signals on a truncated history equal the same bars of the full history."""
    bench = synthetic_candles(99, 1500)["close"]
    rng = np.random.default_rng(1)
    params = {k: v[int(rng.integers(len(v)))] for k, v in space_for(family).items()}
    full = signals(family, Data(df, bench), params)
    cut = 1100
    part = signals(family, Data(df.iloc[:cut], bench.iloc[:cut]), params)
    for a, b in zip(full, part):
        assert a.dtype == bool and len(a) == len(df)
        assert np.array_equal(a[:cut], b)


def _flat(n=50, price=100.0):
    idx = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame({"open": price, "high": price + 0.5, "low": price - 0.5, "close": price, "volume": 1.0}, index=idx)


def test_backtest_enters_next_open_and_charges_costs():
    d0 = _flat()
    d0.iloc[21, d0.columns.get_loc("open")] = 101.0           # bar after the signal opens at 101
    d0.iloc[30:, :4] += 10                                     # later rally
    d = Data(d0)
    z = np.zeros(d.n, bool)
    le = z.copy(); le[20] = True
    lx = z.copy(); lx[35] = True
    tr = backtest.simulate(d, le, z, lx, z, stop_atr=50, rr=0, trail=False, max_hold=40, cost_per_side=0.001)
    assert list(tr.entry) == [21] and list(tr.exit) == [36]   # signal at close 20 -> open 21; exit signal 35 -> open 36
    assert np.isclose(tr.gross[0], 110 / 101 - 1)
    assert np.isclose(tr.ret[0], tr.gross[0] - 0.002)


def test_backtest_stop_wins_when_stop_and_target_hit_in_same_bar():
    d0 = _flat()
    d0.iloc[25, d0.columns.get_loc("high")] = 130.0
    d0.iloc[25, d0.columns.get_loc("low")] = 70.0
    d = Data(d0)
    z = np.zeros(d.n, bool)
    le = z.copy(); le[20] = True
    tr = backtest.simulate(d, le, z, z, z, stop_atr=2, rr=2, trail=False, max_hold=20, cost_per_side=0.0)
    assert tr.exit[0] == 25 and tr.ret[0] < 0


def test_backtest_gap_through_stop_fills_at_open():
    d0 = _flat()
    d0.iloc[25:, :4] = [80.0, 80.5, 79.5, 80.0]
    d = Data(d0)
    z = np.zeros(d.n, bool)
    le = z.copy(); le[20] = True
    tr = backtest.simulate(d, le, z, z, z, stop_atr=2, rr=0, trail=False, max_hold=20, cost_per_side=0.0)
    assert np.isclose(tr.ret[0], 80 / 100 - 1)                # worse than the stop level


def test_evaluation_segments_are_chronological(df):
    d = Data(df)
    p = {"fast": 5, "slow": 30, "kind": "ema", **GRID_DEFAULTS}
    tr = backtest.run("ma_cross", d, p, 0.001)
    ev = backtest.evaluate(tr, d, 0.25, 365, 0.6, 0.2, 5, 2, 0.001)
    seg = ev["segments"]
    assert seg["train"]["trades"] + seg["val"]["trades"] + seg["test"]["trades"] == len(tr)
    assert ev["evaluation"] in {"PASS", "FAIL_TRAIN", "FAIL_VALIDATION", "FAIL_TEST", "INSUFFICIENT_TRADES"}
    costly = backtest.run("ma_cross", d, p, 0.01)
    assert costly.ret.sum() < tr.ret.sum()                    # higher costs -> lower net result


def test_lab_runs_distinct_stored_experiments(settings, db, hub):
    lab = Lab(settings, db, hub)
    lab.run(300)
    st = lab.status()
    assert st["completed"] == 300 and st["phase"] == "complete"
    with db.session() as s:
        rows = s.scalars(select(LabExperiment)).all()
        methods = {m for (m,) in s.execute(select(LabExperiment.method).distinct())}
    assert len(rows) == 300 and len({r.id for r in rows}) == 300
    assert methods == {"grid", "random", "bayesian", "evolutionary"}
    # a second run re-tests the configurations that are currently deployed, before anything else
    cfg = (rows[0].family, rows[0].params, rows[0].instrument, rows[0].timeframe)
    lab.revalidate = lambda: [cfg]
    run2 = lab.run(50)
    assert lab.verdict(run2, *cfg) == rows[0].evaluation          # same data -> same verdict
    assert lab.verdict(run2, "ma_cross", {"x": 1}, "BTC/EUR", "15m") is None
    keys = {(r.family, str(sorted(r.params.items())), r.instrument, r.timeframe) for r in rows}
    assert len(keys) == 300                                    # 300 genuinely different configurations
    r = rows[0]
    assert set(r.segments) == {"train", "val", "test"} and r.period_start < r.period_end and r.bars > 0


def test_lab_rejects_most_strategies_on_pure_noise(settings, db):
    """On a driftless random walk there is nothing to find: the pass rate must stay small."""
    class Noise:
        name = "ccxt"
        def history(self, inst, tf, bars):
            rng = np.random.default_rng(sum(map(ord, inst.symbol + tf)))
            n = 3000
            c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
            o = np.concatenate(([100], c[:-1]))
            idx = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
            return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.001, "low": np.minimum(o, c) * 0.999,
                                 "close": c, "volume": 1000.0}, index=idx)
        def quotes(self, insts):
            return {}
    from quantum_edge.data.hub import DataHub
    lab = Lab(settings, db, DataHub(settings, {"ccxt": Noise()}))
    lab.run(1500)
    with db.session() as s:
        passed = s.scalar(select(func.count()).select_from(LabExperiment).where(LabExperiment.evaluation == "PASS"))
    assert passed / 1500 < 0.03


def test_lab_without_data_runs_nothing(settings, db, providers):
    from quantum_edge.data.hub import DataHub
    for p in providers.values():
        p.fail = True
    lab = Lab(settings, db, DataHub(settings, providers))
    lab.run(100)
    assert lab.status()["completed"] == 0 and lab.status()["phase"] == "no data"
    assert lab.total() == 0                                    # nothing fabricated


def test_only_frequently_trading_strategies_are_deployed(settings, db, hub):
    from quantum_edge.lab import trades_per_day
    lab = Lab(settings, db, hub)
    run = lab.run(600)
    settings.lab_min_trades_per_day = 0.0
    everything = lab.candidates(run)
    settings.lab_min_trades_per_day = 1.0
    frequent = lab.candidates(run)
    assert all(trades_per_day(r) >= 1.0 for r in frequent)
    assert len(frequent) <= len(everything)
    settings.lab_min_trades_per_day = 1e9
    assert lab.candidates(run) == []


def test_illiquid_venue_history_is_rejected():
    """A venue whose candles are mostly empty must not be used; the next venue is tried."""
    import pandas as pd
    from quantum_edge.data.ccxt_provider import CcxtProvider
    from quantum_edge.instruments import BY_SYMBOL

    class Ex:
        rateLimit = 0
        def __init__(self, volume):
            self.markets, self.volume = {"BNB/EUR": {}}, volume
        def milliseconds(self):
            return 1_800_000_000_000
        def fetch_ohlcv(self, symbol, tf, since=None, limit=None):
            return [[since + i * 900_000, 1.0, 1.0, 1.0, 1.0, self.volume] for i in range(50)]

    prov = CcxtProvider(["dead", "alive"], ["dead", "alive"])
    prov._ex = {"dead": Ex(0.0), "alive": Ex(5.0)}
    df = prov.history(BY_SYMBOL["BNB/EUR"], "15m", 40)
    assert df.attrs["source"] == "ccxt:alive" and (df["volume"] > 0).all()
    prov._ex = {"dead": Ex(0.0), "alive": Ex(0.0)}
    assert prov.history(BY_SYMBOL["BNB/EUR"], "15m", 40).empty        # nothing usable -> no data, not fake data


def test_minimum_reward_to_risk_filter_on_deployment(settings, db, hub):
    lab = Lab(settings, db, hub)
    run = lab.run(800)
    settings.lab_min_trades_per_day = 0.0
    settings.lab_min_rr = 4.0
    picks = lab.candidates(run)
    assert all(p.params["rr"] >= 4.0 for p in picks)
    settings.lab_min_rr = 0.0
    assert len(lab.candidates(run)) >= len(picks)


def test_minimum_win_rate_filter_on_deployment(settings, db, hub):
    lab = Lab(settings, db, hub)
    run = lab.run(800)
    settings.lab_min_trades_per_day = 0.0
    settings.lab_min_win_rate = 0.55
    picks = lab.candidates(run)
    assert all(p.win_rate >= 0.55 and min(p.segments[k]["win"] for k in ("val", "test")) >= 0.50 for p in picks)
