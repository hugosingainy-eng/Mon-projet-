"""Performance report built only from what is stored in the database."""
from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np
from sqlalchemy import func, select

from .db import EquitySnapshot, Incident, LabExperiment, Position, Strategy

CAVEATS = [
    "All trades are simulated (paper trading). No real order was ever sent.",
    "Fills use observed market prices plus the configured cost model (fees, spread, slippage, FX conversion, short borrow).",
    "Yahoo Finance data is unofficial, may be delayed, and has no bid/ask: a modelled spread is used for those instruments.",
    "Short selling, fractional quantities and instant fills are simulation assumptions; a real account may not offer them.",
    "Out of 10,000+ tested configurations some pass validation by chance. A five-day forward run is far too short to prove an edge.",
    "Backtested and simulated results are not indicative of future real-money performance.",
]


def lab_row(r: LabExperiment) -> dict:
    seg = r.segments
    pct = lambda x: None if x is None else x * 100
    return {"id": r.id, "strategy": r.family, "instrument": r.instrument, "timeframe": r.timeframe,
            "method": r.method, "params": r.params, "trades": r.trades, "net_return_pct": pct(r.net_return),
            "max_drawdown_pct": pct(r.max_drawdown), "sharpe": r.sharpe, "sortino": r.sortino,
            "profit_factor": r.profit_factor,
            "train_return_pct": pct(seg["train"]["ret"]), "train_sharpe": seg["train"]["sharpe"],
            "val_return_pct": pct(seg["val"]["ret"]), "val_sharpe": seg["val"]["sharpe"],
            "test_return_pct": pct(seg["test"]["ret"]), "test_sharpe": seg["test"]["sharpe"],
            "stability": r.stability, "cost_pct": r.cost_pct, "evaluation": r.evaluation, "score": r.score,
            "period_start": r.period_start.isoformat(), "period_end": r.period_end.isoformat(), "bars": r.bars}


def lab_top(db, limit: int = 20) -> list[dict]:
    with db.session() as s:
        run = s.scalar(select(func.max(LabExperiment.run_id)))
        if run is None:
            return []
        rows = s.scalars(select(LabExperiment).where(LabExperiment.run_id == run)
                         .order_by((LabExperiment.evaluation == "PASS").desc(), LabExperiment.score.desc())
                         .limit(limit)).all()
        return [lab_row(r) for r in rows]


def lab_summary(db) -> dict:
    out = {}
    with db.session() as s:
        for name, col in (("by_evaluation", LabExperiment.evaluation), ("by_method", LabExperiment.method),
                          ("by_family", LabExperiment.family)):
            out[name] = {k: n for k, n in s.execute(select(col, func.count()).group_by(col)).all()}
    return out


def strategy_rows(db) -> list[dict]:
    with db.session() as s:
        strategies = list(s.scalars(select(Strategy).order_by(Strategy.stage, Strategy.id)))
        closed = list(s.scalars(select(Position).where(Position.status == "closed", Position.strategy_id.is_not(None))))
    out = []
    for st in strategies:
        live = [p.realized_pnl_eur for p in closed if p.strategy_id == st.id and p.book == "live"]
        shadow = [p.realized_pnl_eur for p in closed if p.strategy_id == st.id and p.book == "shadow"]
        out.append({"id": st.id, "experiment_id": st.experiment_id, "strategy": st.family, "instrument": st.instrument,
                    "timeframe": st.timeframe, "stage": st.stage, "weight": st.weight, "live_trades": len(live),
                    "live_pnl_eur": float(sum(live)), "shadow_trades": len(shadow), "shadow_pnl_eur": float(sum(shadow)),
                    "expected_trade_pct": st.expected_trade_pct * 100, "note": st.note, "params": st.params,
                    "updated_at": st.updated_at.isoformat()})
    return out


def trade_row(p: Position) -> dict:
    return {"id": p.id, "instrument": p.instrument, "asset_class": p.asset_class,
            "side": "long" if p.side == 1 else "short", "qty": p.qty, "entry_price": p.entry_price,
            "exit_price": p.exit_price, "currency": p.quote_ccy, "pnl_eur": p.realized_pnl_eur,
            "pnl_pct": p.realized_pnl_eur / p.entry_notional_eur * 100 if p.entry_notional_eur else None,
            "fees_eur": p.fees_eur, "slippage_eur": p.slippage_eur, "fx_cost_eur": p.fx_cost_eur,
            "opened_at": p.opened_at.isoformat(), "closed_at": p.closed_at.isoformat(),
            "duration_minutes": (p.closed_at - p.opened_at).total_seconds() / 60,
            "exit_reason": p.exit_reason, "strategy": p.strategy_name}


def build(eng) -> dict:
    db = eng.db
    with db.session() as s:
        closed = list(s.scalars(select(Position).where(Position.book == "live", Position.status == "closed")
                                .order_by(Position.closed_at)))
        eq = [(e.ts, e.equity) for e in s.scalars(select(EquitySnapshot).order_by(EquitySnapshot.ts))]
        n_inc = {k: n for k, n in s.execute(select(Incident.severity, func.count()).group_by(Incident.severity)).all()}
    state = eng.state_view()
    risk = {"sharpe_daily_annualized": None, "sortino_daily_annualized": None,
            "avg_win_eur": None, "avg_loss_eur": None}
    if eq:
        daily = {}
        for ts, v in eq:
            daily[ts.date()] = v
        vals = np.array([eng.s.initial_capital] + list(daily.values()))
        r = np.diff(vals) / vals[:-1]
        if len(r) >= 2 and r.std(ddof=1) > 0:
            risk["sharpe_daily_annualized"] = float(r.mean() / r.std(ddof=1) * np.sqrt(365))
            down = np.sqrt(np.mean(np.minimum(r, 0) ** 2))
            if down > 0:
                risk["sortino_daily_annualized"] = float(r.mean() / down * np.sqrt(365))
    pnl = [p.realized_pnl_eur for p in closed]
    if any(x > 0 for x in pnl):
        risk["avg_win_eur"] = float(np.mean([x for x in pnl if x > 0]))
    if any(x <= 0 for x in pnl):
        risk["avg_loss_eur"] = float(np.mean([x for x in pnl if x <= 0]))
    return {"title": "Quantum Edge AI — paper-trading experiment report", "generated_at": eng.now().isoformat(),
            "state": state, "risk_metrics": risk, "ledger_audit": eng.broker.audit(),
            "strategies": strategy_rows(db), "lab_summary": lab_summary(db), "lab_top": lab_top(db, 20),
            "trades": [trade_row(p) for p in closed], "incidents": n_inc,
            "data_providers": {k: {"last_ok": v["last_ok"].isoformat() if v["last_ok"] else None,
                                   "errors": v["errors"], "last_error": v["last_error"]}
                               for k, v in eng.hub.health.items()},
            "caveats": CAVEATS}


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.4g}" if abs(v) < 1 else f"{v:,.2f}"
    if isinstance(v, dict):
        return html.escape(", ".join(f"{k}={x}" for k, x in v.items()))
    return html.escape(str(v))


def _table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "<p class='empty'>None.</p>"
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{_fmt(r.get(c))}</td>" for c in cols) + "</tr>" for r in rows)
    return f"<div class='scroll'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _kv(d: dict) -> str:
    return "<div class='grid'>" + "".join(
        f"<div class='kv'><span>{html.escape(str(k).replace('_', ' '))}</span><b>{_fmt(v)}</b></div>"
        for k, v in d.items() if not isinstance(v, (dict, list))) + "</div>"


def to_html(rep: dict) -> str:
    st = rep["state"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(rep['title'])}</title>
<style>body{{background:#0b0f14;color:#d7dee7;font:14px/1.5 system-ui,sans-serif;margin:0;padding:16px;max-width:1200px;margin:auto}}
h1{{font-size:22px}}h2{{font-size:16px;margin-top:28px;border-bottom:1px solid #243040;padding-bottom:4px}}
.badge{{display:inline-block;background:#3a2a00;color:#ffc857;padding:2px 10px;border-radius:4px;font-weight:600}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px}}
.kv{{background:#121922;border:1px solid #1e2a38;border-radius:6px;padding:8px}}.kv span{{display:block;color:#8494a7;font-size:12px}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{padding:4px 8px;border-bottom:1px solid #1e2a38;text-align:left;white-space:nowrap}}
th{{color:#8494a7}}.empty{{color:#8494a7}}li{{margin:4px 0}}</style></head><body>
<h1>{html.escape(rep['title'])}</h1><p><span class="badge">PAPER TRADING — no real money</span> &nbsp; generated {html.escape(rep['generated_at'])}</p>
<h2>Experiment</h2>{_kv(st['experiment'])}
<h2>Portfolio (EUR)</h2>{_kv(st['portfolio'])}
<h2>Trading</h2>{_kv(st['trading'])}{_kv(rep['risk_metrics'])}
<h2>Ledger audit (cash and realized P&amp;L replayed from the fill log)</h2>{_kv(rep['ledger_audit'])}
<h2>Strategy laboratory</h2>{_kv(st['lab'])}
<p>By verdict: {_fmt(rep['lab_summary'].get('by_evaluation', {}))}<br>By method: {_fmt(rep['lab_summary'].get('by_method', {}))}</p>
<h2>Top strategies of the latest research run</h2>{_table(rep['lab_top'], ['strategy', 'instrument', 'timeframe', 'method', 'trades', 'net_return_pct', 'max_drawdown_pct', 'train_sharpe', 'val_sharpe', 'test_sharpe', 'val_return_pct', 'test_return_pct', 'stability', 'evaluation', 'score', 'params'])}
<h2>Deployed strategies</h2>{_table(rep['strategies'], ['id', 'strategy', 'instrument', 'timeframe', 'stage', 'weight', 'live_trades', 'live_pnl_eur', 'shadow_trades', 'shadow_pnl_eur', 'expected_trade_pct', 'note'])}
<h2>Closed trades</h2>{_table(rep['trades'], ['closed_at', 'instrument', 'side', 'qty', 'entry_price', 'exit_price', 'currency', 'pnl_eur', 'pnl_pct', 'fees_eur', 'slippage_eur', 'fx_cost_eur', 'duration_minutes', 'exit_reason', 'strategy'])}
<h2>Incidents</h2><p>{_fmt(rep['incidents'])}</p>
<h2>Limits of this experiment</h2><ul>{''.join(f'<li>{html.escape(c)}</li>' for c in rep['caveats'])}</ul>
</body></html>"""


def save_final(eng) -> Path:
    rep = build(eng)
    out = Path(eng.s.db_path).parent / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "final_report.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    path = out / "final_report.html"
    path.write_text(to_html(rep), encoding="utf-8")
    return path
