"""Rapports quotidiens, hebdomadaires et de recherche (Markdown, dans reports/)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np


def _label(engine) -> str:
    return "SIMULÉ" if engine.account.simulated else "DÉMO eToro"


def _week_stats(closed: list[dict]) -> dict:
    if not closed:
        return {"n": 0}
    pnl = np.array([c["pnl"] or 0 for c in closed])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    by = {}
    for c in closed:
        by.setdefault(c["strategy"], []).append(c["pnl"] or 0)
    ranked = sorted(by.items(), key=lambda kv: sum(kv[1]))
    return {"n": len(closed), "win_rate": float((pnl > 0).mean()), "net": float(pnl.sum()),
            "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
            "avg_win": float(wins.mean()) if len(wins) else 0.0, "avg_loss": float(losses.mean()) if len(losses) else 0.0,
            "best": ranked[-1][0], "worst": ranked[0][0]}


def daily_report(engine) -> str:
    db = engine.db
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    acc = engine.account.d
    eq = db.query("SELECT * FROM equity ORDER BY id DESC LIMIT 1")
    eqv = eq[0]["equity"] if eq else acc["cash"]
    dec = db.query("SELECT * FROM decisions WHERE ts LIKE ?", (day + "%",))
    closed = db.query("SELECT * FROM positions WHERE state='closed' AND exit_ts LIKE ?", (day + "%",))
    ev = db.query("SELECT * FROM events WHERE ts LIKE ? AND level IN ('critical','error')", (day + "%",))
    md = [f"# Rapport quotidien {day} — {_label(engine)}", "",
          f"- Capital du bot : **{eqv:.2f} $** (départ {acc['starting_capital']:.2f} $)",
          f"- P&L du jour : {eqv - acc['day_start_equity']:+.2f} $ | réalisé total : {acc['realized']:+.2f} $ "
          f"| frais : {acc['fees']:.2f} $",
          f"- Décisions : {len(dec)} (achats autorisés : {sum(d['authorized'] for d in dec)})",
          f"- Trades clôturés aujourd'hui : {len(closed)}",
          f"- Coupe-circuit : {'DÉCLENCHÉ — ' + engine.breaker.state['reason'] if engine.breaker.state['tripped'] else 'normal'}",
          f"- Incidents : {len(ev)}", ""]
    for d in dec:
        p = json.loads(d["payload"])
        md.append(f"  - {d['decision']} {d['symbol']} ({d['strategy']}) — " + "; ".join(p.get("reasons", [])[:2]))
    path = engine.paths["reports"] / "daily" / f"{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(md), encoding="utf-8")
    return str(path)


def weekly_report(engine) -> str:
    db = engine.db
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).isoformat()
    closed = db.query("SELECT * FROM positions WHERE state='closed' AND exit_ts >= ?", (since,))
    dec = db.query("SELECT * FROM decisions WHERE ts >= ?", (since,))
    eqs = db.query("SELECT equity FROM equity WHERE ts >= ? ORDER BY id", (since,))
    dd = 0.0
    if eqs:
        e = np.array([x["equity"] for x in eqs])
        dd = float((1 - e / np.maximum.accumulate(e)).max())
    st = _week_stats(closed)
    audit = engine.agents["auditor"].analyze_history(engine.account.closed_positions(),
                                                     db.query("SELECT authorized FROM decisions"))
    iso = now.isocalendar()
    md = [f"# Rapport hebdomadaire {iso[0]}-S{iso[1]:02d} — {_label(engine)}", "",
          f"- Trades : {st['n']}"]
    if st["n"]:
        md += [f"- Taux de réussite : {st['win_rate']:.0%}", f"- P&L net : {st['net']:+.2f} $",
               f"- Profit factor : {st['profit_factor']:.2f}",
               f"- Gain moyen : {st['avg_win']:+.2f} $ | perte moyenne : {st['avg_loss']:+.2f} $",
               f"- Meilleure stratégie : {st['best']} | pire : {st['worst']}"]
    md += [f"- Drawdown max de la semaine : {dd:.2%}",
           f"- Opportunités rejetées : {sum(1 for d in dec if not d['authorized'])} sur {len(dec)}", "",
           "## Conclusions de l'auditeur"] + [f"- {f}" for f in audit["findings"]] + \
          ["", "## Propositions (aucune appliquée automatiquement)"] + [f"- {p}" for p in audit["proposals"] or ["aucune"]] + \
          ["", "> Une semaine de résultats ne prouve rien. Observer 8 à 12 semaines minimum en démo."]
    path = engine.paths["reports"] / "weekly" / f"{iso[0]}-W{iso[1]:02d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(md), encoding="utf-8")
    engine.db.set("last_weekly", {"path": str(path), "stats": st, "audit": audit, "drawdown": dd})
    return str(path)


def research_report(result: dict, path) -> str:
    L = [f"# Rapport de recherche — {result['created']}", ""]
    if result.get("simulated_data"):
        L += ["> ⚠️ **DONNÉES SIMULÉES** : ces résultats ne disent RIEN du marché réel.", ""]
    p = result["period"]
    L += [f"- Univers : {', '.join(result['universe'])}",
          f"- Période : {p['start']} → {p['end']} (train < {p['train_end']} ≤ validation < {p['valid_end']} ≤ test)",
          f"- Plis walk-forward : {result['walk_forward_folds']} | trades simulés : {result['total_trades_simulated']:,}",
          f"- Durée : {result['seconds']} s", "", "## Classement des stratégies", "",
          "| Rang | Famille | Statut | Score | n WF | E[R] WF | IC90 bas | PF | Sharpe | Sortino | DD max (R) | E coûts x2 | E retard |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in result["leaderboard"]:
        m = r.get("metrics", {}).get("walk_forward", {})
        L.append(f"| {r['rank']} | {r['family']} | {r['status']} | {r.get('score', 0):.2f} | {m.get('n', 0)} | "
                 f"{m.get('ev_r', 0):+.3f} | {m.get('ci_low', 0):+.3f} | {m.get('profit_factor', 0):.2f} | "
                 f"{m.get('sharpe', 0):+.2f} | {m.get('sortino', 0):+.2f} | {m.get('max_dd_r', 0):.1f} | "
                 f"{r.get('ev_cost_x2', 0):+.3f} | {r.get('ev_delay_1bar', 0):+.3f} |")
    for r in result["leaderboard"]:
        L += ["", f"### {r['family']}", f"*Hypothèse :* {r['hypothesis']}", f"*Inspiration :* {r['inspired_by']}"]
        if "chosen_spec" in r:
            L.append(f"*Paramètres retenus :* `{r['chosen_spec']['label']}` ({r['configs_tested']} testés)")
            for k, ok in r["checks"].items():
                L.append(f"- {'✅' if ok else '❌'} {k}")
            base = r.get("monte_carlo", {}).get("base")
            worst = r.get("monte_carlo", {}).get("pire_cas_combine")
            if base:
                L.append(f"- Monte-Carlo (100 trades, {base['sims']:,} séquences, {base['n_real_trades']} trades réels) : "
                         f"médiane {base['final_return_p50']:+.1%}, 5e centile {base['final_return_p05']:+.1%}, "
                         f"P(coupe-circuit -5 %) {base['risk_of_ruin']:.0%}")
            if worst:
                L.append(f"- Pire cas combiné : médiane {worst['final_return_p50']:+.1%}, "
                         f"P(coupe-circuit) {worst['risk_of_ruin']:.0%}")
            L.append(f"- Régimes autorisés : {r['allowed_regimes'] or 'aucun'}")
        else:
            L.append(f"- Rejetée : {r.get('failed')}")
    L += ["", "## Avertissements"] + [f"- {w}" for w in result["warnings"]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")
    return str(path)
