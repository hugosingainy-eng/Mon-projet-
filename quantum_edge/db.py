"""Persistent storage (SQLite by default; plain SQLAlchemy so PostgreSQL also works)."""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine,
                        event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores naive UTC, always returns timezone-aware UTC."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class KV(Base):
    __tablename__ = "kv"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book: Mapped[str] = mapped_column(String(8), index=True)      # live | shadow
    status: Mapped[str] = mapped_column(String(8), index=True)    # open | closed
    instrument: Mapped[str] = mapped_column(String(24), index=True)
    asset_class: Mapped[str] = mapped_column(String(12))
    quote_ccy: Mapped[str] = mapped_column(String(4))
    side: Mapped[int] = mapped_column(Integer)                    # +1 long, -1 short
    qty: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    entry_fx: Mapped[float] = mapped_column(Float)                # EUR per 1 unit of quote ccy
    entry_notional_eur: Mapped[float] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_price: Mapped[float] = mapped_column(Float)
    last_fx: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    trail_dist: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    strategy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    strategy_name: Mapped[str] = mapped_column(String(64), default="")
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    realized_pnl_eur: Mapped[float | None] = mapped_column(Float, nullable=True)  # net of all costs
    fees_eur: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_eur: Mapped[float] = mapped_column(Float, default=0.0)
    fx_cost_eur: Mapped[float] = mapped_column(Float, default=0.0)


class Fill(Base):
    """Append-only transaction log. The live cash balance is always recomputable from it."""
    __tablename__ = "fills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    book: Mapped[str] = mapped_column(String(8), index=True)
    position_id: Mapped[int] = mapped_column(Integer, index=True)
    instrument: Mapped[str] = mapped_column(String(24))
    action: Mapped[str] = mapped_column(String(8))                # open | close
    side: Mapped[str] = mapped_column(String(4))                  # buy | sell
    qty: Mapped[float] = mapped_column(Float)
    ref_price: Mapped[float] = mapped_column(Float)               # observed market price
    price: Mapped[float] = mapped_column(Float)                   # simulated fill price
    fx: Mapped[float] = mapped_column(Float)
    price_source: Mapped[str] = mapped_column(String(48))
    price_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    notional_eur: Mapped[float] = mapped_column(Float)
    fee_eur: Mapped[float] = mapped_column(Float)
    slippage_eur: Mapped[float] = mapped_column(Float)            # spread + slippage, embedded in price
    fx_cost_eur: Mapped[float] = mapped_column(Float)
    borrow_eur: Mapped[float] = mapped_column(Float, default=0.0)
    cash_delta_eur: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(48), default="")


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    instrument: Mapped[str] = mapped_column(String(24))
    side: Mapped[str] = mapped_column(String(6))
    strategy: Mapped[str] = mapped_column(String(64))
    approved: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(200))
    notional_eur: Mapped[float | None] = mapped_column(Float, nullable=True)


class EquitySnapshot(Base):
    __tablename__ = "equity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)


class LabExperiment(Base):
    __tablename__ = "lab_experiments"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)   # hash of the configuration
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    family: Mapped[str] = mapped_column(String(32), index=True)
    params: Mapped[dict] = mapped_column(JSON)
    instrument: Mapped[str] = mapped_column(String(24), index=True)
    timeframe: Mapped[str] = mapped_column(String(6))
    method: Mapped[str] = mapped_column(String(16), index=True)
    period_start: Mapped[datetime] = mapped_column(UTCDateTime)
    period_end: Mapped[datetime] = mapped_column(UTCDateTime)
    bars: Mapped[int] = mapped_column(Integer)
    trades: Mapped[int] = mapped_column(Integer)
    net_return: Mapped[float] = mapped_column(Float)      # whole period, after costs
    max_drawdown: Mapped[float] = mapped_column(Float)
    sharpe: Mapped[float] = mapped_column(Float)
    sortino: Mapped[float] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_trade: Mapped[float | None] = mapped_column(Float, nullable=True)
    segments: Mapped[dict] = mapped_column(JSON)          # train / val / test metrics
    stability: Mapped[float] = mapped_column(Float)
    cost_pct: Mapped[float] = mapped_column(Float)        # total execution cost, % of capital
    evaluation: Mapped[str] = mapped_column(String(24), index=True)
    score: Mapped[float] = mapped_column(Float, index=True)


class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(20), index=True)
    family: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSON)
    instrument: Mapped[str] = mapped_column(String(24))
    timeframe: Mapped[str] = mapped_column(String(6))
    stage: Mapped[str] = mapped_column(String(10), index=True)   # forward | live | retired
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    expected_trade_pct: Mapped[float] = mapped_column(Float, default=0.0)
    last_bar_ts: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    agent: Mapped[str] = mapped_column(String(24))
    instrument: Mapped[str] = mapped_column(String(24), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(String(300))
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    severity: Mapped[str] = mapped_column(String(8))
    component: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(400))
    recovered: Mapped[bool] = mapped_column(Boolean, default=False)


class News(Base):
    __tablename__ = "news"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    instrument: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(400))
    publisher: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(600), unique=True)
    sentiment: Mapped[float] = mapped_column(Float)


class Filing(Base):
    __tablename__ = "filings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution: Mapped[str] = mapped_column(String(80))
    form: Mapped[str] = mapped_column(String(12))
    accession: Mapped[str] = mapped_column(String(32), unique=True)
    report_date: Mapped[str] = mapped_column(String(10))
    filing_date: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(String(300))


class Holding(Base):
    __tablename__ = "holdings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    accession: Mapped[str] = mapped_column(String(32), index=True)
    institution: Mapped[str] = mapped_column(String(80))
    issuer: Mapped[str] = mapped_column(String(120))
    value_usd: Mapped[float] = mapped_column(Float)
    shares: Mapped[float] = mapped_column(Float)
    report_date: Mapped[str] = mapped_column(String(10))
    filing_date: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(300))


class Database:
    def __init__(self, path: str):
        if path != ":memory:" and "://" not in path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        url = path if "://" in path else f"sqlite:///{path}"
        kwargs = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if path == ":memory:":
                from sqlalchemy.pool import StaticPool
                kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _pragma(conn, _):
                cur = conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.close()
        Base.metadata.create_all(self.engine)
        self._Session = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self):
        s = self._Session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # --- key/value state --------------------------------------------------------------
    def get(self, key: str, default=None):
        with self.session() as s:
            row = s.get(KV, key)
            return default if row is None else json.loads(row.value)

    def set(self, key: str, value) -> None:
        with self.session() as s:
            row = s.get(KV, key)
            if row is None:
                s.add(KV(key=key, value=json.dumps(value)))
            else:
                row.value = json.dumps(value)

    def incident(self, severity: str, component: str, message: str, recovered: bool = False) -> None:
        with self.session() as s:
            s.add(Incident(ts=utcnow(), severity=severity, component=component,
                           message=str(message)[:400], recovered=recovered))
