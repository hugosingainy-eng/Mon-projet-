import numpy as np
import pandas as pd
import pytest

from quantum_edge.config import Settings
from quantum_edge.quantitative.competition import run_competition
from quantum_edge.quantitative.library import StrategyLibrary
from quantum_edge.quantitative.metrics import trade_metrics
from quantum_edge.quantitative.trades import TradeCosts, simulate_trades
from quantum_edge.quantitative.validation import in_window, lookahead_check, walk_forward_windows
from quantum_edge.simulations.sequences import SCENARIOS, simulate_sequences
from quantum_edge.simulations.trade_paths import run_trade_paths, simulate_exits
from quantum_edge.strategies.base import StrategySpec, frame
from quantum_edge.strategies.catalog import FAMILIES, compute_signals


def _df(prices, hi=None, lo=None):
    idx = pd.bdate_range("2024-01-01", periods=len(prices))
    p = np.array(prices, float)
    return pd.DataFrame({"open": p, "high": hi if hi is not None else p, "low": lo if lo is not None else p,
                         "close": p, "volume": 1e6}, index=idx)


def test_trade_engine_stop_target_time_and_no_stacking():
    df = _df([100, 100, 101, 110, 100, 100, 95, 100, 100, 100, 100])
    entry = pd.Series(False, index=df.index)
    entry.iloc[[0, 1, 4]] = True
    sig = frame(df, entry, pd.Series(3.0, index=df.index), 2.0)
    t = simulate_trades(df, sig, TradeCosts(0.0, 0.0), max_hold=3)
    assert list(t["reason"]) == ["target", "stop"]          # le signal du jour 1 est ignoré (pas d'empilement)
    assert t["r"].iloc[0] == pytest.approx(10 / 3)               # gap au-dessus de l'objectif : sortie à l'ouverture (110)
    assert t["exit"].iloc[1] == pytest.approx(95)            # gap sous le stop : sortie à l'ouverture
    assert t["r"].iloc[1] < -1


def test_same_bar_stop_and_target_assumes_stop():
    df = _df([100, 100, 100], hi=np.array([100, 120, 100.0]), lo=np.array([100, 80, 100.0]))
    entry = pd.Series([True, False, False], index=df.index)
    t = simulate_trades(df, frame(df, entry, pd.Series(5.0, index=df.index), 2.0), TradeCosts(0, 0))
    assert t["reason"].iloc[0] == "stop"


def test_costs_reduce_r():
    df = _df([100, 100, 110, 110])
    entry = pd.Series([True, False, False, False], index=df.index)
    sig = frame(df, entry, pd.Series(3.0, index=df.index), 2.0)
    r0 = simulate_trades(df, sig, TradeCosts(0, 0))["r"].iloc[0]
    r1 = simulate_trades(df, sig, TradeCosts(0.002, 0.001))["r"].iloc[0]
    assert r1 < r0


def test_metrics():
    t = pd.DataFrame({"r": [2, -1, 2, -1, -1, 2], "entry_date": pd.bdate_range("2024-01-01", periods=6),
                      "exit_date": pd.bdate_range("2024-01-02", periods=6)})
    m = trade_metrics(t)
    assert m["n"] == 6 and m["ev_r"] == pytest.approx(0.5) and m["profit_factor"] == pytest.approx(2.0)
    assert m["win_rate"] == pytest.approx(0.5) and m["ci_low"] <= m["ev_r"] <= m["ci_high"]


def test_windows_prevent_leakage():
    t = pd.DataFrame({"entry_date": pd.to_datetime(["2024-01-01", "2024-01-08"]),
                      "exit_date": pd.to_datetime(["2024-01-05", "2024-01-20"]), "r": [1, 1]})
    assert len(in_window(t, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-10"))) == 1
    w = walk_forward_windows(pd.bdate_range("2015-01-01", periods=2000), 756, 252)
    assert all(a < b < c for a, b, c in w) and len(w) >= 4


@pytest.mark.parametrize("fam", FAMILIES, ids=lambda f: f.name)
def test_no_lookahead_in_any_strategy(fam, small_data):
    for spec in fam.specs()[:2]:
        ok, msg = lookahead_check(spec, small_data, {"bench": small_data["SPY"]}, n_dates=4)
        assert ok, msg


def test_lookahead_detector_catches_cheating(small_data):
    from quantum_edge.strategies import catalog

    class Cheat(catalog.Family):
        def __init__(self):
            super().__init__("cheat", "triche", "", {"rr": [2.0]})

        def signals(self, df, p, ctx):
            return frame(df, df["close"].shift(-1) > df["close"], df["close"] * 0.02, p["rr"])

    catalog.FAMILY_BY_NAME["cheat"] = Cheat()
    try:
        ok, _ = lookahead_check(StrategySpec("cheat", (("rr", 2.0),)), small_data, {}, n_dates=8)
        assert not ok
    finally:
        catalog.FAMILY_BY_NAME.pop("cheat")


def test_sequence_monte_carlo_scenarios_degrade():
    r = np.array([2.0, -1, -1, 2, -1, 2.5, -1, 1.5] * 10)
    base = simulate_sequences(r, 4000, 100, scenario="base", seed=1)
    worst = simulate_sequences(r, 4000, 100, scenario="pire_cas_combine", seed=1)
    assert base.sims == 4000 and base.n_real_trades == 80
    assert worst.final_return_p50 < base.final_return_p50
    assert worst.risk_of_ruin >= base.risk_of_ruin
    assert set(SCENARIOS) >= {"base", "chocs_brutaux", "retard_execution"}


def test_trade_paths_detects_edge_and_its_absence():
    rng = np.random.default_rng(0)
    unc = rng.standard_normal(3000)
    no_edge = run_trade_paths(0.03, 0.06, 0.015, 0.002, rng.standard_normal((300, 15)), unc, 30000, 15, 0.4, 1)
    edge = run_trade_paths(0.03, 0.06, 0.015, 0.002, rng.standard_normal((300, 15)) + 0.5, unc, 30000, 15, 0.4, 1)
    assert no_edge.expected_r < 0.05 < edge.expected_r and no_edge.paths == 30000


def test_exits_vectorized():
    lr = np.log(np.array([[1.01, 1.08], [0.96, 1.0], [1.0, 1.01]]))
    ret, kind = simulate_exits(lr, 0.03, 0.06)
    assert kind.tolist() == [2, 1, 0] and ret[1] == pytest.approx(-0.04)


def test_competition_and_promotion_rules(small_data, isolated_env):
    s = Settings()
    s.research.mc_sequences = 1000
    s.universe = {k: "stock" for k in small_data}
    res = run_competition(small_data, s, workers=1, log=lambda *_: None, simulated=True)
    assert {r["family"] for r in res["leaderboard"]} == {f.name for f in FAMILIES}
    assert all(not r.get("eligible") for r in res["leaderboard"])          # jamais éligible sur données simulées
    real = StrategyLibrary(isolated_env / "research", simulated=False)
    real.save_run(res)
    assert real.promote(res) == ["type de données incompatible avec cette bibliothèque : aucune promotion"]
    assert real.production()["strategies"] == {}
    # une stratégie en production qui échoue à la re-validation est retirée
    fake = {"created": "2026-01-01T00:00:00+00:00", "simulated_data": False, "leaderboard": [
        {"family": "momentum", "eligible": True, "chosen_spec": {"id": "m:1", "family": "momentum", "params": {"rr": 2.0},
         "label": "m"}, "allowed_regimes": ["bull"], "metrics": {"walk_forward": {}}, "score": 1}]}
    real.promote(fake)
    assert "momentum" in real.production()["strategies"]
    fake["leaderboard"][0].update({"eligible": False, "failed": ["x"]})
    assert any("RETIRÉE" in c for c in real.promote(fake))
    assert real.production()["strategies"] == {}


def test_signals_are_long_only_with_rr_at_least_2(small_data):
    for fam in FAMILIES:
        for spec in fam.specs():
            assert spec.direction == 1 and spec.p["rr"] >= 2.0
            sig = compute_signals(spec, small_data["AAPL"], {"bench": small_data["SPY"]})
            e = sig[sig["entry"]]
            assert ((e["target_dist"] / e["stop_dist"]) >= 2.0 - 1e-9).all()
