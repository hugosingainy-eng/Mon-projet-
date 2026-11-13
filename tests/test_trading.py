"""Paper broker accounting, risk limits, engine lifecycle, restart recovery."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from sqlalchemy import select

from quantum_edge.broker import BrokerError, PaperBroker
from quantum_edge.db import Decision, Incident, Position, Strategy, utcnow
from quantum_edge.engine import Engine
from quantum_edge.instruments import BY_SYMBOL, is_market_open
from quantum_edge.lab import GRID_DEFAULTS
from quantum_edge.risk import Proposal, RiskManager

BTC, NVDA = BY_SYMBOL["BTC/EUR"], BY_SYMBOL["NVDA"]
OPEN_US = datetime(2026, 3, 4, 15, 0, tzinfo=timezone.utc)      # a Wednesday, US session open


def setp(providers, hub, sym, px, now=None):
    for p in providers.values():
        p.prices[sym] = px
        p.now = now
    hub.quotes.pop(sym, None)       # tests move time backwards; the hub (rightly) ignores older quotes
    hub.refresh_quotes(now, force=True)


@pytest.fixture
def broker(settings, db, hub):
    return PaperBroker(settings, db, hub)


def test_initial_account(broker):
    a = broker.account()
    assert a["equity"] == a["cash"] == 1000.0 and a["invested"] == 0 and a["realized_pnl"] == 0


def test_long_round_trip_accounting_is_exact(broker, providers, hub, settings):
    setp(providers, hub, "BTC/EUR", 100.0)
    pos = broker.open(BTC, 1, 200.0)
    # crypto quote has bid/ask 99.98/100.02; buy at ask + 5 bps slippage
    assert np.isclose(pos.entry_price, 100.02 * 1.0005)
    fee_in = 200.0 * 0.001
    a = broker.account()
    assert np.isclose(a["cash"], 1000 - 200 - fee_in)
    assert np.isclose(a["equity"], a["initial_capital"] + a["realized_pnl"] + a["unrealized_pnl"])
    setp(providers, hub, "BTC/EUR", 110.0)
    broker.mark_and_check()
    closed = broker.close(pos.id, "test")
    exit_px = 110 * 0.9998 * 0.9995
    proceeds = pos.qty * exit_px
    expected = proceeds - proceeds * 0.001 - 200 - fee_in
    assert np.isclose(closed.realized_pnl_eur, expected)
    a = broker.account()
    assert np.isclose(a["equity"], 1000 + expected) and np.isclose(a["cash"], a["equity"])
    assert a["fees"] > 0 and a["slippage"] > 0 and a["fx_costs"] == 0      # EUR pair: no conversion
    assert broker.audit()["ok"]


def test_short_profits_when_price_falls_and_pays_borrow(broker, providers, hub):
    setp(providers, hub, "BTC/EUR", 100.0)
    t0 = utcnow()
    pos = broker.open(BTC, -1, 200.0, now=t0)
    setp(providers, hub, "BTC/EUR", 90.0, t0 + timedelta(days=1))
    closed = broker.close(pos.id, "test", now=t0 + timedelta(days=1))
    assert 15 < closed.realized_pnl_eur < 20                    # ~ +10% of 200 minus costs
    assert broker.audit()["ok"]
    with broker.db.session() as s:
        from quantum_edge.db import Fill
        assert s.scalars(select(Fill).where(Fill.action == "close")).one().borrow_eur > 0


def test_usd_instrument_uses_fx_and_charges_conversion(broker, providers, hub, settings):
    setp(providers, hub, "EURUSD", 1.25, OPEN_US)               # 1 USD = 0.8 EUR
    setp(providers, hub, "NVDA", 100.0, OPEN_US)
    pos = broker.open(NVDA, 1, 100.0, now=OPEN_US)
    assert np.isclose(pos.entry_fx, 0.8)
    assert np.isclose(pos.qty * pos.entry_price * 0.8, 100.0)
    a = broker.account()
    assert np.isclose(a["fx_costs"], 100.0 * settings.fx_cost_bps / 1e4)
    assert np.isclose(a["equity"], a["initial_capital"] + a["realized_pnl"] + a["unrealized_pnl"])
    setp(providers, hub, "EURUSD", 1.0, OPEN_US)                # dollar strengthens: EUR value rises
    broker.mark_and_check(OPEN_US)
    assert broker.account()["positions_value"] > 120


def test_no_fill_without_fresh_real_price(broker, providers, hub):
    setp(providers, hub, "BTC/EUR", 100.0, utcnow() - timedelta(hours=1))
    with pytest.raises(BrokerError, match="stale"):
        broker.open(BTC, 1, 100.0)
    saturday = datetime(2026, 3, 7, 15, 0, tzinfo=timezone.utc)
    setp(providers, hub, "NVDA", 100.0, saturday)
    setp(providers, hub, "EURUSD", 1.1, saturday)
    assert not is_market_open(NVDA, saturday)
    with pytest.raises(BrokerError, match="closed"):
        broker.open(NVDA, 1, 100.0, now=saturday)
    with pytest.raises(BrokerError, match="not tradable"):
        broker.open(BY_SYMBOL["GC=F"], 1, 100.0)
    assert broker.account()["cash"] == 1000.0


def test_cannot_spend_more_than_cash(broker, providers, hub):
    setp(providers, hub, "BTC/EUR", 100.0)
    with pytest.raises(BrokerError, match="insufficient"):
        broker.open(BTC, 1, 1000.0)                             # 1000 + fee > 1000


def test_stop_take_profit_trailing_and_time_limit(broker, providers, hub):
    setp(providers, hub, "BTC/EUR", 100.0)
    p1 = broker.open(BTC, 1, 100.0, stop_price=95.0, take_profit=120.0)
    setp(providers, hub, "BTC/EUR", 94.0)
    assert [(p.id, r) for p, r in broker.mark_and_check()] == [(p1.id, "stop")]
    setp(providers, hub, "BTC/EUR", 100.0)
    p2 = broker.open(BTC, 1, 100.0, stop_price=95.0, trail_dist=5.0)
    setp(providers, hub, "BTC/EUR", 110.0)
    assert broker.mark_and_check() == []
    assert np.isclose(broker.open_positions()[0].stop_price, 105.0)     # stop trailed up
    setp(providers, hub, "BTC/EUR", 104.0)
    assert broker.mark_and_check()[0][1] == "stop"
    p3 = broker.open(BTC, -1, 100.0, take_profit=100.0, expires_at=utcnow() + timedelta(hours=1))
    setp(providers, hub, "BTC/EUR", 99.0)
    assert broker.mark_and_check()[0][1] == "take_profit"
    p4 = broker.open(BTC, 1, 100.0, expires_at=utcnow() - timedelta(seconds=1))
    assert broker.mark_and_check()[0][1] == "time_limit"
    assert broker.audit()["ok"]


def test_shadow_book_never_touches_cash(broker, providers, hub):
    setp(providers, hub, "BTC/EUR", 100.0)
    pos = broker.open(BTC, 1, 100.0, book="shadow")
    assert broker.account()["cash"] == 1000.0 and broker.account()["equity"] == 1000.0
    broker.close(pos.id, "test")
    assert broker.account()["cash"] == 1000.0


# --- risk manager -----------------------------------------------------------------------
def prop(inst=BTC, side=1, **kw):
    base = dict(inst=inst, side=side, strategy_id=1, strategy_name="t", book="live", stop_dist_pct=0.02,
                expected_trade_pct=0.01, bar_turnover=1e7)
    base.update(kw)
    return Proposal(**base)


@pytest.fixture
def risk(settings, db, hub, broker, providers):
    setp(providers, hub, "BTC/EUR", 100.0)
    return RiskManager(settings, db, hub, broker)


RUN = {"status": "running"}


def test_risk_sizes_within_limits(risk, settings):
    v = risk.evaluate(prop(), RUN)
    assert v.approved and v.notional_eur == pytest.approx(250.0)       # capped at 25% of equity
    v = risk.evaluate(prop(stop_dist_pct=0.2), RUN)
    assert v.notional_eur == pytest.approx(100.0)                      # 2% risk / 20% stop
    assert risk.evaluate(prop(weight=0.5), RUN).notional_eur == pytest.approx(125.0)


@pytest.mark.parametrize("kw,state,why", [
    ({}, {"status": "paused"}, "paused"),
    ({}, {"status": "running", "flatten": True}, "flattened"),
    ({"expected_trade_pct": 0.0}, RUN, "expectancy"),
    ({"stop_dist_pct": 0.001}, RUN, "round-trip cost"),
    ({"bar_turnover": 10.0}, RUN, "liquidity"),
    ({"consensus": -3.0}, RUN, "consensus"),
    ({"inst": BY_SYMBOL["^GSPC"]}, RUN, "not tradable"),
    ({}, {"status": "running", "peak_equity": 2000.0}, "drawdown"),
    ({}, {"status": "running", "day_start_equity": 1200.0}, "daily loss"),
])
def test_risk_rejections(risk, kw, state, why):
    v = risk.evaluate(prop(**kw), state)
    assert not v.approved and why in v.reason


def test_risk_rejects_stale_data_wide_spread_and_duplicates(risk, providers, hub, broker, settings):
    broker.open(BTC, 1, 100.0)
    assert "already holding" in risk.evaluate(prop(), RUN).reason
    settings.max_positions = 1
    setp(providers, hub, "ETH/EUR", 100.0)
    assert "simultaneous" in risk.evaluate(prop(inst=BY_SYMBOL["ETH/EUR"]), RUN).reason
    settings.max_positions = 8
    q = hub.quote("ETH/EUR"); q.bid, q.ask = 99.0, 101.0
    assert "spread" in risk.evaluate(prop(inst=BY_SYMBOL["ETH/EUR"]), RUN).reason
    setp(providers, hub, "ETH/EUR", 100.0, utcnow() - timedelta(hours=2))
    assert "stale" in risk.evaluate(prop(inst=BY_SYMBOL["ETH/EUR"]), RUN).reason
    with risk.db.session() as s:
        assert len(s.scalars(select(Decision)).all()) == 4          # every decision is recorded


def test_exposure_and_correlation_caps(risk, broker, providers, hub, settings):
    for sym in ("BTC/EUR", "ETH/EUR"):
        setp(providers, hub, sym, 100.0)
        broker.open(BY_SYMBOL[sym], 1, 250.0)
    setp(providers, hub, "SOL/EUR", 100.0)
    v = risk.evaluate(prop(inst=BY_SYMBOL["SOL/EUR"]), RUN)
    assert v.approved and v.notional_eur < 110                      # 60% crypto-long cap leaves ~100
    assert risk.evaluate(prop(inst=BY_SYMBOL["SOL/EUR"], side=-1), RUN).notional_eur > 200


# --- engine -----------------------------------------------------------------------------
@pytest.fixture
def eng(settings, providers):
    e = Engine(settings, providers)
    e.hub.refresh_quotes(force=True)
    return e


def test_controls_lifecycle(eng):
    assert eng.control("pause") == (False, "not running")
    ok, _ = eng.control("start")
    assert ok and eng.state["status"] == "running"
    ends = datetime.fromisoformat(eng.state["ends_at"]) - datetime.fromisoformat(eng.state["started_at"])
    assert ends == timedelta(days=5)
    assert eng.control("pause")[0] and eng.state["status"] == "paused"
    assert eng.control("resume")[0] and eng.state["status"] == "running"
    assert not eng.control("reset", confirm=True)[0]                 # must stop first
    assert eng.control("stop")[0] and eng.state["status"] == "stopped"
    assert not eng.control("reset")[0]                               # needs confirmation
    assert eng.control("reset", confirm=True)[0] and eng.state["status"] == "idle"


def test_emergency_stop_closes_positions_and_blocks_trading(eng, providers):
    eng.control("start")
    setp(providers, eng.hub, "BTC/EUR", 100.0)
    eng.broker.open(BTC, 1, 200.0)
    assert not eng.control("emergency_stop")[0]
    ok, msg = eng.control("emergency_stop", confirm=True)
    assert ok and eng.state["status"] == "halted" and eng.broker.open_positions() == []
    v = eng.risk.evaluate(prop(), eng.state)
    assert not v.approved


def test_restart_recovers_experiment_and_portfolio(settings, providers):
    e1 = Engine(settings, providers)
    e1.control("start")
    setp(providers, e1.hub, "BTC/EUR", 100.0)
    e1.broker.open(BTC, 1, 200.0)
    e1.cycle()
    started, equity = e1.state["started_at"], e1.broker.account()["equity"]
    e1.shutdown()
    e2 = Engine(settings, providers)                                 # "computer restarted"
    assert e2.state["status"] == "running" and e2.state["started_at"] == started
    assert len(e2.broker.open_positions()) == 1
    e2.hub.refresh_quotes(force=True)
    assert e2.broker.account()["equity"] == pytest.approx(equity)
    with e2.db.session() as s:
        assert any("restarted" in i.message for i in s.scalars(select(Incident)))


def test_clock_completion_flattens_and_writes_report(settings, providers, tmp_path):
    t = [utcnow()]
    e = Engine(settings, providers, clock=lambda: t[0])
    e.control("start")
    setp(providers, e.hub, "BTC/EUR", 100.0, t[0])
    e.broker.open(BTC, 1, 200.0, now=t[0])
    t[0] += timedelta(days=5, seconds=1)
    for p in providers.values():
        p.now = t[0]
    e.cycle()
    assert e.state["status"] == "completed" and e.broker.open_positions() == []
    assert (tmp_path / "reports" / "final_report.html").exists()
    assert not e.control("start")[0]


def test_strategy_pipeline_forward_then_live(eng, providers, monkeypatch, settings):
    import quantum_edge.engine as engine_mod
    now = utcnow()
    with eng.db.session() as s:
        st = Strategy(experiment_id="x", family="ma_cross", params={"fast": 5, "slow": 30, "kind": "ema", **GRID_DEFAULTS},
                      instrument="BTC/EUR", timeframe="15m", stage="forward", weight=1.0, expected_trade_pct=0.01,
                      created_at=now - timedelta(hours=10), updated_at=now)
        s.add(st)
    df = providers["ccxt"].history(BTC, "15m", 600)
    setp(providers, eng.hub, "BTC/EUR", float(df["close"].iloc[-1]))
    eng.control("start")

    def fake(direction):
        def f(family, d, p):
            z = np.zeros(d.n, bool); one = z.copy(); one[-1] = True
            return {"long": (one, z, z, z), "exit": (z, z, one, z), "none": (z, z, z, z)}[direction]
        return f

    def step(direction):
        monkeypatch.setattr(engine_mod, "strategy_signals", fake(direction))
        with eng.db.session() as s:
            s.get(Strategy, st.id).last_bar_ts = None
        eng.evaluate_strategies(utcnow())

    step("long")
    shadow = eng.broker.open_positions("shadow")
    assert len(shadow) == 1 and shadow[0].stop_price < shadow[0].entry_price
    assert eng.broker.account()["cash"] == 1000.0                    # forward test risks no capital
    eng.evaluate_strategies(utcnow())                                # same bar again: no duplicate action
    assert len(eng.broker.open_positions("shadow")) == 1
    # two profitable forward trades -> promotion to live
    for _ in range(2):
        pos = eng.broker.open_positions("shadow")
        if not pos:
            step("long"); pos = eng.broker.open_positions("shadow")
        setp(providers, eng.hub, "BTC/EUR", eng.hub.quote("BTC/EUR").price * 1.03)
        step("exit")
    perf = next(a for a in eng.agents if a.id == "performance")
    eng.run_agent(perf)
    with eng.db.session() as s:
        assert s.get(Strategy, st.id).stage == "live"
    step("long")
    live = eng.broker.open_positions("live")
    assert len(live) == 1 and live[0].entry_notional_eur <= 250.0 + 1e-6
    with eng.db.session() as s:
        d = s.scalars(select(Decision)).all()
    assert d and d[-1].approved


def test_failing_agent_is_isolated_and_recovers(eng, providers):
    scanner = eng.agents[0]
    providers["yahoo"].fail = providers["ccxt"].fail = True
    orig = scanner.run
    scanner.run = lambda e: (_ for _ in ()).throw(RuntimeError("boom"))
    eng.run_agent(scanner)
    assert scanner.status == "error" and scanner.errors == 1 and "boom" in scanner.last_error
    scanner.run = orig
    providers["yahoo"].fail = providers["ccxt"].fail = False
    eng.run_agent(scanner)
    assert scanner.status == "ok"
    with eng.db.session() as s:
        msgs = [i.message for i in s.scalars(select(Incident))]
    assert any("boom" in m for m in msgs) and any("recovered" in m for m in msgs)


def test_provider_outage_never_fabricates_prices(eng, providers):
    eng.control("start")
    before = {k: (q.price, q.ts) for k, q in eng.hub.quotes.items()}
    for p in providers.values():
        p.fail = True
    eng.cycle()
    assert {k: (q.price, q.ts) for k, q in eng.hub.quotes.items()} == before     # untouched, will go stale
    assert eng.hub.health["ccxt"]["errors"] >= 1


def test_all_fourteen_agents_run(eng):
    eng.cycle()
    assert len(eng.agents) == 14
    bad = {a.id: a.last_error for a in eng.agents if a.status == "error"}
    assert not bad, bad
    assert all(a.last_run for a in eng.agents)


def test_backup_and_restore_into_a_fresh_database(settings, providers, tmp_path):
    from quantum_edge.backup import restore, save
    from quantum_edge.db import Database
    e1 = Engine(settings, providers)
    e1.control("start")
    setp(providers, e1.hub, "BTC/EUR", 100.0)
    e1.broker.open(BTC, 1, 200.0, stop_price=90.0)
    e1.cycle()
    acct, started = e1.broker.account(), e1.state["started_at"]
    path = save(e1.db, tmp_path / "state.json")
    assert "already holds" in restore(e1.db, path)                   # never overwrites
    settings.db_path = str(tmp_path / "fresh.db")
    assert "restored" in restore(Database(settings.db_path), path)
    e2 = Engine(settings, providers)
    assert e2.state["status"] == "running" and e2.state["started_at"] == started
    pos = e2.broker.open_positions()
    assert len(pos) == 1 and pos[0].stop_price == 90.0
    assert e2.broker.account()["cash"] == pytest.approx(acct["cash"]) and e2.broker.audit()["ok"]


def test_forward_test_can_be_disabled_by_configuration(eng, settings):
    now = utcnow()
    with eng.db.session() as s:
        st = Strategy(experiment_id="x", family="ma_cross", params={"fast": 5, "slow": 30, "kind": "ema", **GRID_DEFAULTS},
                      instrument="BTC/EUR", timeframe="15m", stage="forward", weight=1.0, expected_trade_pct=0.01,
                      created_at=now, updated_at=now)
        s.add(st)
    perf = next(a for a in eng.agents if a.id == "performance")
    eng.run_agent(perf)
    with eng.db.session() as s:
        assert s.get(Strategy, st.id).stage == "forward"            # default: must pass the forward test
    settings.forward_min_trades = 0
    eng.run_agent(perf)
    with eng.db.session() as s:
        assert s.get(Strategy, st.id).stage == "live"


def test_exploration_trades_small_and_stops_at_loss_budget(eng, providers, monkeypatch, settings):
    import quantum_edge.engine as engine_mod
    settings.explore_count, settings.explore_loss_budget_eur = 2, 5.0
    now = utcnow()
    with eng.db.session() as s:
        st = Strategy(experiment_id="x", family="ma_cross", params={"fast": 5, "slow": 30, "kind": "ema", **GRID_DEFAULTS},
                      instrument="BTC/EUR", timeframe="15m", stage="explore", weight=settings.explore_weight,
                      expected_trade_pct=-0.001, created_at=now, updated_at=now)      # negative expectancy
        s.add(st)
    df = providers["ccxt"].history(BTC, "15m", 600)
    setp(providers, eng.hub, "BTC/EUR", float(df["close"].iloc[-1]))
    eng.control("start")

    def fire():
        def f(family, d, p):
            z = np.zeros(d.n, bool); one = z.copy(); one[-1] = True
            return one, z, z, z
        monkeypatch.setattr(engine_mod, "strategy_signals", f)
        with eng.db.session() as s:
            s.get(Strategy, st.id).last_bar_ts = None
        eng.evaluate_strategies(utcnow())

    fire()
    pos = eng.broker.open_positions("live")
    assert len(pos) == 1 and pos[0].strategy_name.startswith("explore:")
    assert pos[0].entry_notional_eur <= 1000 * settings.max_position_pct * settings.explore_weight + 1e-6   # <= 5%
    # a validated ("live") strategy with the same negative expectancy is still refused
    v = eng.risk.evaluate(prop(inst=BY_SYMBOL["ETH/EUR"], expected_trade_pct=-0.001), eng.state)
    assert not v.approved and "expectancy" in v.reason
    # lose more than the budget -> exploration is halted and the strategy retired
    setp(providers, eng.hub, "BTC/EUR", eng.hub.quote("BTC/EUR").price * 0.8)
    eng.broker.close(pos[0].id, "test")
    eng.run_agent(next(a for a in eng.agents if a.id == "performance"))
    assert eng.state["explore_halted"]
    with eng.db.session() as s:
        assert s.get(Strategy, st.id).stage == "retired"
    assert not eng.risk.evaluate(prop(exploratory=True), eng.state).approved


def test_focused_research_run_only_uses_requested_markets(settings, db, hub):
    from quantum_edge.lab import Lab
    lab = Lab(settings, db, hub)
    lab._focus = (["crypto"], ["15m"])
    lab.run(120)
    with db.session() as s:
        from quantum_edge.db import LabExperiment
        rows = s.execute(select(LabExperiment.instrument, LabExperiment.timeframe).distinct()).all()
    assert rows and all(i.endswith("/EUR") and tf == "15m" for i, tf in rows)
    settings.explore_count = 3
    picks = lab.exploration_picks(1)
    assert len({p.instrument for p in picks}) == len(picks) <= 3


def test_order_size_is_capped_by_market_liquidity(risk):
    v = risk.evaluate(prop(bar_turnover=1000.0), RUN)          # 10% of a 1,000 EUR bar
    assert v.approved and v.notional_eur == pytest.approx(100.0)
    v = risk.evaluate(prop(bar_turnover=150.0), RUN)           # below the floor
    assert not v.approved and "liquidity" in v.reason
    v = risk.evaluate(prop(bar_turnover=600.0), RUN)           # would allow 60, fine; 10% of 190 would be < 20
    assert v.approved and v.notional_eur == pytest.approx(60.0)


def test_kickstart_opens_small_stopped_positions_in_consensus_direction(eng, providers, settings):
    from quantum_edge.db import Signal
    assert not eng.control("kickstart", confirm=True)[0]            # experiment not running
    eng.control("start")
    assert not eng.control("kickstart")[0]                          # needs confirmation
    for sym, direction in (("BTC/EUR", "short"), ("ETH/EUR", "long")):
        df = providers["ccxt"].history(BY_SYMBOL[sym], "15m", 300)
        setp(providers, eng.hub, sym, float(df["close"].iloc[-1]))
        with eng.db.session() as s:
            s.add(Signal(ts=utcnow(), agent="technical", instrument=sym, direction=direction, confidence=0.6, summary="t"))
    ok, msg = eng.control("kickstart", confirm=True)
    assert ok and "short BTC/EUR" in msg and "long ETH/EUR" in msg
    pos = {p.instrument: p for p in eng.broker.open_positions("live")}
    assert set(pos) == {"BTC/EUR", "ETH/EUR"}                       # only where agents have a view
    b = pos["BTC/EUR"]
    assert b.side == -1 and b.stop_price > b.entry_price > b.take_profit and b.expires_at is not None
    assert all(p.entry_notional_eur <= 50.0 + 1e-6 and p.strategy_name.startswith("explore:") for p in pos.values())
    assert eng.broker.audit()["ok"]


def test_leverage_is_off_by_default_and_capped(settings):
    from quantum_edge.config import SecurityError, validate_paper_only
    settings.max_exposure_pct = 3.0
    with pytest.raises(SecurityError, match="leverage"):
        validate_paper_only(settings)                               # needs explicit allow_leverage
    settings.allow_leverage = True
    validate_paper_only(settings)
    settings.max_exposure_pct = 5.0
    with pytest.raises(SecurityError, match="capped"):
        validate_paper_only(settings)


def test_leverage_borrowing_interest_and_margin_call(settings, providers):
    settings.allow_leverage, settings.max_exposure_pct = True, 3.0
    settings.max_position_pct, settings.max_class_exposure_pct = 1.0, 3.0
    e = Engine(settings, providers)
    e.hub.refresh_quotes(force=True)
    e.control("start")
    for sym in ("BTC/EUR", "ETH/EUR", "SOL/EUR"):
        setp(providers, e.hub, sym, 100.0)
        e.broker.open(BY_SYMBOL[sym], 1, 950.0)
    a = e.broker.account()
    assert a["cash"] < 0 and 2.8 < a["leverage"] <= 3.0                # borrowed about 1,850
    assert np.isclose(a["equity"], a["initial_capital"] + a["realized_pnl"] + a["unrealized_pnl"])
    with pytest.raises(BrokerError, match="insufficient"):
        e.broker.open(BY_SYMBOL["XRP/EUR"], 1, 500.0)                  # beyond 3x
    paid = e.broker.accrue_financing(86400)                            # one day of interest
    assert paid == pytest.approx(-a["cash"] * settings.financing_bps_per_day / 1e4)
    b = e.broker.account()
    assert b["financing"] == pytest.approx(paid) and b["equity"] == pytest.approx(a["equity"] - paid)
    assert np.isclose(b["equity"], b["initial_capital"] + b["realized_pnl"] + b["unrealized_pnl"])
    assert e.broker.audit()["cash_replayed"] == pytest.approx(b["cash"])
    # a 27% fall on a 3x book wipes most of the equity -> margin call
    for sym in ("BTC/EUR", "ETH/EUR", "SOL/EUR"):
        setp(providers, e.hub, sym, 73.0)
    e.cycle()
    assert e.state["status"] == "halted" and "MARGIN CALL" in e.state["halt_reason"]
    assert e.broker.open_positions() == []
    assert 0 < e.broker.account()["equity"] < 300                      # most of the capital is gone


def test_order_book_depth_takes_precedence_over_bar_turnover(risk):
    v = risk.evaluate(prop(bar_turnover=50.0, book_depth=4000.0), RUN)     # quiet bar, deep book
    assert v.approved and v.notional_eur == pytest.approx(250.0)
    v = risk.evaluate(prop(bar_turnover=1e7, book_depth=600.0), RUN)       # busy bar, thin book
    assert v.approved and v.notional_eur == pytest.approx(150.0)           # 25% of the resting orders
    v = risk.evaluate(prop(bar_turnover=1e7, book_depth=100.0), RUN)
    assert not v.approved and "order book depth" in v.reason


def test_consensus_trading_continues_while_it_works_and_stops_after_giveback(eng, providers, settings):
    from quantum_edge.db import Signal
    settings.consensus_trading, settings.consensus_stop_drawdown_eur = True, 5.0
    settings.consensus_max_positions = 1
    eng.control("start")

    def agree(sym, direction):
        df = providers["ccxt"].history(BY_SYMBOL[sym], "1h", 300)
        setp(providers, eng.hub, sym, float(df["close"].iloc[-1]))
        with eng.db.session() as s:
            for agent in ("technical", "scanner", "momentum"):
                s.add(Signal(ts=utcnow(), agent=agent, instrument=sym, direction=direction, confidence=0.6, summary="t"))

    agree("BTC/EUR", "long")
    eng.consensus_trader(utcnow())
    assert eng.broker.open_positions("live") == []                    # no agent has a proven record yet
    eng.agent_scores = {a: {"proven": True} for a in ("technical", "scanner", "momentum")}
    eng.state["consensus_ts"] = None
    eng.consensus_trader(utcnow())
    pos = eng.broker.open_positions("live")
    assert len(pos) == 1 and pos[0].instrument == "BTC/EUR" and pos[0].stop_price is not None
    eng.consensus_trader(utcnow() + timedelta(minutes=20))            # slot is full: nothing more
    assert len(eng.broker.open_positions("live")) == 1
    # weak agreement is ignored
    with eng.db.session() as s:
        s.add(Signal(ts=utcnow(), agent="technical", instrument="ETH/EUR", direction="long", confidence=0.3, summary="t"))
    settings.consensus_max_positions = 2
    eng.consensus_trader(utcnow() + timedelta(minutes=40))
    assert len(eng.broker.open_positions("live")) == 1
    # the method loses more than its allowed give-back -> it switches itself off
    setp(providers, eng.hub, "BTC/EUR", eng.hub.quote("BTC/EUR").price * 0.97)
    eng.broker.close(pos[0].id, "stop")
    rec = eng.consensus_record()
    assert rec["trades"] == 1 and rec["giveback_eur"] >= 5.0
    agree("SOL/EUR", "long")
    eng.consensus_trader(utcnow() + timedelta(hours=1))
    assert eng.state["consensus_halted"] and eng.broker.open_positions("live") == []


def test_agent_memory_scores_past_signals_against_what_happened(eng, providers, settings):
    from quantum_edge.db import Signal
    inst = BY_SYMBOL["BTC/EUR"]
    eng.hub.prefetch([inst], "15m", 0)
    df = eng.hub.cached_candles(inst, "15m")
    c = df["close"].to_numpy()
    with eng.db.session() as s:
        for k in range(40):                                           # 40 hourly signals, outcome known
            i = len(df) - 400 + k * 4
            went_up = c[i + 8] > c[i]
            ts = df.index[i].to_pydatetime()
            s.add(Signal(ts=ts, agent="oracle", instrument="BTC/EUR", direction="long" if went_up else "short", confidence=0.5, summary="t"))
            s.add(Signal(ts=ts, agent="antioracle", instrument="BTC/EUR", direction="short" if went_up else "long", confidence=0.5, summary="t"))
        s.add(Signal(ts=utcnow(), agent="newbie", instrument="BTC/EUR", direction="long", confidence=0.5, summary="t"))
    mem = eng.agent_memory(lookback_hours=24 * 30)
    assert mem["oracle"]["signals"] == 40 and mem["oracle"]["hit_rate"] == 1.0 and mem["oracle"]["proven"]
    assert mem["antioracle"]["hit_rate"] == 0.0 and not mem["antioracle"]["proven"]
    assert "newbie" not in mem                                        # outcome not known yet: not scored
    import json
    json.dumps(eng.state_view())                                      # the memory must be serialisable for the API
    with eng.db.session() as s:
        for a in ("oracle", "antioracle"):
            s.add(Signal(ts=utcnow(), agent=a, instrument="BTC/EUR", direction="long", confidence=0.8, summary="t"))
    assert eng.consensus("BTC/EUR") == pytest.approx(0.5 + 0.8 + 0.8)
    assert eng.consensus("BTC/EUR", proven_only=True) == pytest.approx(0.8)      # only the proven agent counts
