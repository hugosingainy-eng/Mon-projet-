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
