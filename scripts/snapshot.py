"""Builds a static status page from the running app's API (default http://127.0.0.1:8000).

Usage: python scripts/snapshot.py OUTPUT.html [BASE_URL]
Every figure comes from the API at generation time; nothing is estimated or filled in."""
from __future__ import annotations

import html
import json
import sys
import urllib.request
from datetime import datetime, timezone

BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def esc(x):
    return html.escape(str(x))


def eur(v, sign=False):
    if v is None:
        return "—"
    s = f"{v:+,.2f}" if sign else f"{v:,.2f}"
    return s.replace(",", " ").replace(".", ",") + " €"


def pct(v, sign=True):
    return "—" if v is None else (f"{v:+.2f}" if sign else f"{v:.2f}").replace(".", ",") + " %"


def num(v, d=2):
    return "—" if v is None else f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def tone(v):
    return "" if not v else ("pos" if v > 0 else "neg")


def when(iso):
    if not iso:
        return "—"
    return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%d/%m %H:%M")


def dur(seconds):
    s = int(seconds)
    return f"{s // 86400} j {s % 86400 // 3600:02d} h {s % 3600 // 60:02d} min"


def table(headers, rows, empty):
    if not rows:
        return f'<p class="empty">{esc(empty)}</p>'
    head = "".join(f'<th class="{c}">{esc(h)}</th>' for h, c in headers)
    body = "".join("<tr>" + "".join(f'<td class="{headers[i][1]} {cls}">{val}</td>' for i, (val, cls) in enumerate(r)) + "</tr>"
                   for r in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def equity_chart(points, initial):
    if len(points) < 2:
        return '<p class="empty">La courbe apparaîtra après les premiers relevés.</p>'
    W, H, L, R, T, B = 900, 260, 64, 16, 14, 30
    ts = [datetime.fromisoformat(p["ts"]).timestamp() for p in points]
    ys = [p["equity"] for p in points]
    lo, hi = min(ys + [initial]), max(ys + [initial])
    pad = max((hi - lo) * 0.15, 0.5)
    lo, hi = lo - pad, hi + pad
    x = lambda t: L + (t - ts[0]) / max(ts[-1] - ts[0], 1) * (W - L - R)
    y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    line = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in zip(ts, ys))
    area = f"{x(ts[0]):.1f},{H - B} {line} {x(ts[-1]):.1f},{H - B}"
    grid = ""
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        grid += (f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                 f'<text x="{L - 8}" y="{y(v) + 4:.1f}" text-anchor="end" class="tick">{num(v)}</text>')
    xt = ""
    for i in range(4):
        t = ts[0] + (ts[-1] - ts[0]) * i / 3
        anchor = "start" if i == 0 else "end" if i == 3 else "middle"
        xt += (f'<text x="{x(t):.1f}" y="{H - 8}" text-anchor="{anchor}" class="tick">'
               f'{datetime.fromtimestamp(t, timezone.utc).strftime("%d/%m %H:%M")}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Courbe de la valeur du portefeuille en euros">'
            f'{grid}<line x1="{L}" x2="{W - R}" y1="{y(initial):.1f}" y2="{y(initial):.1f}" class="base"/>'
            f'<polygon points="{area}" class="area"/><polyline points="{line}" class="line" fill="none"/>'
            f'<circle cx="{x(ts[-1]):.1f}" cy="{y(ys[-1]):.1f}" r="4" class="dot"/>{xt}</svg>'
            f'<p class="note">Ligne pointillée : capital initial de {eur(initial)}. Heures en UTC.</p>')


def build() -> str:
    st, positions, trades = get("/api/state"), get("/api/positions"), get("/api/trades?limit=40")
    equity, strategies, agents = get("/api/equity"), get("/api/strategies"), get("/api/agents")
    incidents, summary, market = get("/api/incidents?limit=12"), get("/api/lab/summary"), get("/api/market")
    decisions = get("/api/decisions?limit=12")
    ex, pf, tr, lab = st["experiment"], st["portfolio"], st["trading"], st["lab"]
    status_fr = {"idle": "en attente", "running": "en cours", "paused": "en pause", "stopped": "arrêtée",
                 "halted": "arrêt d'urgence", "completed": "terminée"}.get(ex["status"], ex["status"])
    progress = 100 * ex["elapsed_seconds"] / (ex["duration_days"] * 86400)
    fresh = sum(1 for m in market if not m["stale"])
    live = [s for s in strategies if s["stage"] == "live"]
    fwd = [s for s in strategies if s["stage"] == "forward"]
    exp = [s for s in strategies if s["stage"] == "explore"]
    tiles = [("Valeur du portefeuille", eur(pf["equity"]), ""),
             ("Résultat total", pct(pf["total_return_pct"]), tone(pf["total_return_pct"])),
             ("Liquidités", eur(pf["cash"]), ""),
             ("Gain/perte réalisé", eur(pf["realized_pnl"], True), tone(pf["realized_pnl"])),
             ("Gain/perte latent", eur(pf["unrealized_pnl"], True), tone(pf["unrealized_pnl"])),
             ("Perte maximale depuis un sommet", pct(-pf["max_drawdown_pct"] if pf["max_drawdown_pct"] else 0.0, False), tone(-pf["max_drawdown_pct"])),
             ("Trades clôturés", str(tr["closed_trades"]), ""),
             ("Taux de réussite", pct(tr["win_rate"] * 100, False) if tr["win_rate"] is not None else "—", ""),
             ("Frais + glissement + change", eur(pf["fees"] + pf["slippage"] + pf["fx_costs"]), ""),
             ("Capital engagé", eur(pf["invested"]), ""),
             ("Levier utilisé", "×" + num(pf.get("leverage") or 0.0), "warn" if (pf.get("leverage") or 0) > 1 else "")]
    ob = st.get("objectives") or {}
    objective_html = ""
    if ob.get("return_pct"):
        target = pf["initial_capital"] * (1 + ob["return_pct"] / 100)
        objective_html = (
            '<section><h2>Objectifs fixés</h2><div class="panel facts">'
            f'<span>Objectif de résultat <b>{pct(ob["return_pct"])}</b> soit <b>{eur(target)}</b></span>'
            f'<span>Résultat actuel <b class="{tone(pf["total_return_pct"])}">{pct(pf["total_return_pct"])}</b></span>'
            f'<span>Reste à gagner <b>{eur(ob["remaining_eur"])}</b></span>'
            f'<span>Objectif par trade gagnant <b>{num(ob["trade_eur_min"], 0)} à {num(ob["trade_eur_max"], 0)} €</b></span>'
            f'<span>Gain moyen des trades gagnants <b>{eur(ob.get("avg_win_eur"))}</b></span>'
            f'<span>Perte moyenne des trades perdants <b>{eur(ob.get("avg_loss_eur"))}</b></span>'
            f'<span>Trades gagnants dans la cible <b>{ob.get("wins_in_range", 0)} sur {tr["wins"]}</b></span>'
            '</div></section>')
    tiles_html = "".join(f'<div class="tile"><span>{esc(l)}</span><b class="{c}">{v}</b></div>' for l, v, c in tiles)

    pos_rows = [[(esc(p["instrument"]), ""), ("achat" if p["side"] == "long" else "vente", ""), (num(p["entry_price"], 4), ""),
                 (num(p["current_price"], 4), ""), (eur(p["value_eur"]), ""),
                 (eur(p["unrealized_pnl_eur"], True), tone(p["unrealized_pnl_eur"])), (esc(p["strategy"]), "dim"),
                 (when(p["opened_at"]), "dim")] for p in positions]
    trade_rows = [[(when(t["closed_at"]), "dim"), (esc(t["instrument"]), ""), ("achat" if t["side"] == "long" else "vente", ""),
                   (eur(t["pnl_eur"], True), tone(t["pnl_eur"])), (pct(t["pnl_pct"]), tone(t["pnl_pct"])),
                   (eur(t["fees_eur"] + t["slippage_eur"] + t["fx_cost_eur"]), "dim"), (esc(t["exit_reason"]), "dim"),
                   (esc(t["strategy"]), "dim")] for t in trades]
    stage_fr = {"forward": "test sans capital", "live": "avec capital", "explore": "exploration (non validée)", "retired": "retirée"}
    strat_rows = [[(esc(s["strategy"]), ""), (esc(s["instrument"]), ""), (esc(s["timeframe"]), "dim"),
                   (f'<span class="pill {s["stage"]}">{stage_fr.get(s["stage"], s["stage"])}</span>', ""),
                   (f'{s["shadow_trades"]} / {eur(s["shadow_pnl_eur"], True)}', tone(s["shadow_pnl_eur"])),
                   (f'{s["live_trades"]} / {eur(s["live_pnl_eur"], True)}', tone(s["live_pnl_eur"])),
                   (pct(s["expected_trade_pct"]), "dim"), (esc(s["note"]), "dim")]
                  for s in strategies if s["stage"] != "retired"]
    agent_html = "".join(
        f'<li class="{a["status"]}"><b>{esc(a["name"])}</b><span>{esc((a["last_error"] if a["status"] == "error" else a["activity"]) or "pas encore exécuté")}</span></li>'
        for a in agents)
    dec_rows = [[(when(d["ts"]), "dim"), (esc(d["instrument"]), ""), ("achat" if d["side"] == "long" else "vente", ""),
                 ("accepté" if d["approved"] else "refusé", "pos" if d["approved"] else "neg"), (esc(d["reason"]), "dim")]
                for d in decisions]
    inc_rows = [[(when(i["ts"]), "dim"), (esc(i["severity"]), {"error": "neg", "warning": "warn"}.get(i["severity"], "dim")),
                 (esc(i["component"]), ""), (esc(i["message"]), "dim")] for i in incidents]
    ev = summary.get("by_evaluation", {})
    R, L = ("r", ""), ("", "")
    return f"""<title>Quantum Edge AI Live</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
/* layout: status band, KPI strip, equity curve, then scan-able tables in one column */
:root{{--bg:#0b1016;--panel:#111922;--line:#1f2b38;--fg:#dbe3ec;--dim:#8494a6;--accent:#4aa8ff;--pos:#33c48d;--neg:#f0616d;--warn:#e0a83a;
--display:"Space Grotesk","Inter",system-ui,sans-serif;--body:"Inter",system-ui,sans-serif;--mono:"JetBrains Mono",ui-monospace,monospace;color-scheme:dark}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{--bg:#f4f6f9;--panel:#ffffff;--line:#d9e0e8;--fg:#17202b;--dim:#5b6878;--accent:#1267c4;--pos:#0c8a5b;--neg:#c9323f;--warn:#9a6a00;color-scheme:light}}}}
:root[data-theme="light"]{{--bg:#f4f6f9;--panel:#ffffff;--line:#d9e0e8;--fg:#17202b;--dim:#5b6878;--accent:#1267c4;--pos:#0c8a5b;--neg:#c9323f;--warn:#9a6a00;color-scheme:light}}
body{{background:var(--bg);color:var(--fg);font:14px/1.5 var(--body);padding-block:20px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
.wrap{{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:20px}}
h1{{font:600 22px/1.2 var(--display);margin:0;text-wrap:balance}}
h2{{font:600 12px/1.2 var(--display);letter-spacing:.09em;text-transform:uppercase;color:var(--dim);margin:0 0 10px}}
header{{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center}}
.badge{{border:1px solid var(--warn);color:var(--warn);border-radius:4px;padding:2px 9px;font-weight:600;font-size:12px}}
.state{{border:1px solid var(--pos);color:var(--pos);border-radius:4px;padding:2px 9px;font-weight:600;font-size:12px}}
.meta{{color:var(--dim);font-size:13px}}
.clock{{display:flex;flex-direction:column;gap:6px}}.bar{{height:6px;background:var(--line);border-radius:3px;overflow:hidden}}.bar i{{display:block;height:100%;background:var(--accent);width:{progress:.2f}%}}
.clock div:first-child{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px 12px;font:13px var(--mono);color:var(--dim)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}}
.tile{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px;min-width:0}}
.tile span{{display:block;color:var(--dim);font-size:12px}}.tile b{{font:500 19px var(--mono);font-variant-numeric:tabular-nums}}
section{{min-width:0}}.panel{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;font-variant-numeric:tabular-nums}}
th{{color:var(--dim);font-weight:500;font-size:12px}}td:last-child{{white-space:normal;min-width:180px}}tr:last-child td{{border-bottom:0}}
.pos{{color:var(--pos)}}.neg{{color:var(--neg)}}.warn{{color:var(--warn)}}.dim{{color:var(--dim)}}
.pill{{border:1px solid var(--line);border-radius:10px;padding:1px 8px;font-size:12px}}.pill.live{{border-color:var(--pos);color:var(--pos)}}.pill.forward{{border-color:var(--accent);color:var(--accent)}}.pill.explore{{border-color:var(--warn);color:var(--warn)}}
.empty,.note{{color:var(--dim);margin:0}}.note{{font-size:12px;margin-top:6px}}
svg{{width:100%;height:auto;display:block}}.grid{{stroke:var(--line);stroke-width:1}}.tick{{fill:var(--dim);font:11px var(--mono)}}
.base{{stroke:var(--dim);stroke-width:1;stroke-dasharray:4 4}}.line{{stroke:var(--accent);stroke-width:2}}.area{{fill:var(--accent);opacity:.12}}.dot{{fill:var(--accent)}}
ul.agents{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:8px}}
ul.agents li{{border-left:3px solid var(--pos);padding:2px 0 2px 10px;min-width:0}}ul.agents li.error{{border-color:var(--neg)}}ul.agents li.idle,ul.agents li.disabled{{border-color:var(--line)}}
ul.agents b{{display:block;font-weight:600}}ul.agents span{{color:var(--dim);font-size:12px;overflow-wrap:anywhere}}
.facts{{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:13px}}.facts b{{font-family:var(--mono);font-weight:500}}
</style>
<div class="wrap">
<header><h1>Quantum Edge AI</h1><span class="badge">Trading simulé — aucun argent réel</span><span class="state">Expérience {esc(status_fr)}</span>
<span class="meta">Relevé du {datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M")} UTC, mis à jour environ toutes les heures</span></header>
<div class="clock"><div><span>écoulé {dur(ex["elapsed_seconds"])}</span><span>restant {dur(ex["remaining_seconds"])}</span></div><div class="bar"><i></i></div></div>
<div class="tiles">{tiles_html}</div>
{objective_html}
<section><h2>Valeur du portefeuille</h2><div class="panel">{equity_chart(equity, pf["initial_capital"])}</div></section>
<section><h2>Positions ouvertes ({len(positions)})</h2><div class="panel">{table([("Instrument", ""), ("Sens", ""), ("Entrée", ""), ("Cours", ""), ("Valeur", ""), ("Latent", ""), ("Stratégie", ""), ("Ouverte", "")], pos_rows, "Aucune position ouverte pour le moment.")}</div></section>
<section><h2>Derniers trades clôturés</h2><div class="panel">{table([("Clôture", ""), ("Instrument", ""), ("Sens", ""), ("Résultat net", ""), ("%", ""), ("Coûts", ""), ("Sortie", ""), ("Stratégie", "")], trade_rows, "Aucun trade clôturé pour le moment.")}</div></section>
<section><h2>Stratégies actives — {len(live)} validées avec capital, {len(exp)} en exploration, {len(fwd)} en test</h2><div class="panel">{table([("Famille", ""), ("Instrument", ""), ("Bougies", ""), ("Étape", ""), ("Test : trades / net", ""), ("Capital : trades / net", ""), ("Attendu par trade", ""), ("Note", "")], strat_rows, "Aucune stratégie validée pour le moment.")}</div></section>
<section><h2>Laboratoire de stratégies</h2><div class="panel facts"><span>Expériences stockées <b>{num(lab.get("total_all_runs"), 0)}</b></span><span>Dernière série <b>{num(lab["completed"], 0)} / {num(lab["target"], 0)}</b></span><span>Validées <b>{ev.get("PASS", 0)}</b></span><span>Rejetées à la validation <b>{ev.get("FAIL_VALIDATION", 0)}</b></span><span>Rejetées au test final <b>{ev.get("FAIL_TEST", 0)}</b></span><span>Trop peu de trades <b>{ev.get("INSUFFICIENT_TRADES", 0)}</b></span><span>Phase <b>{esc(lab["phase"])}</b></span></div></section>
<section><h2>Décisions du gestionnaire de risque</h2><div class="panel">{table([("Heure", ""), ("Instrument", ""), ("Sens", ""), ("Décision", ""), ("Motif", "")], dec_rows, "Aucune proposition de trade avec capital pour le moment.")}</div></section>
<section><h2>Les 14 agents</h2><div class="panel"><ul class="agents">{agent_html}</ul></div></section>
<section><h2>Journal — données : {fresh} instruments sur {len(market)} avec un prix frais</h2><div class="panel">{table([("Heure", ""), ("Niveau", ""), ("Composant", ""), ("Message", "")], inc_rows, "Aucun incident.")}</div></section>
<p class="note">Résultats simulés à partir de prix de marché réels (Kraken, Yahoo Finance), frais, écart acheteur/vendeur, glissement et change inclus. Ils ne préjugent pas de résultats en argent réel.</p>
</div>"""


if __name__ == "__main__":
    out = sys.argv[1]
    open(out, "w", encoding="utf-8").write(build())
    print("snapshot written to", out)
