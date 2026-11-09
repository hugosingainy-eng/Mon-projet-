// Tableau de bord Quantum Edge — aucune donnée inventée : tout vient de l'API locale.
const $ = (s) => document.querySelector(s);
const usd = (v) => (v == null || isNaN(v)) ? "—" : `${v >= 0 ? "" : "−"}${Math.abs(v).toFixed(2)} $`;
const sgn = (v) => (v == null || isNaN(v)) ? "—" : `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)} $`;
const pct = (v, d = 2) => (v == null || isNaN(v)) ? "—" : `${(v * 100).toFixed(d)} %`;
const cls = (v) => v > 0 ? "pos" : v < 0 ? "neg" : "";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const token = () => localStorage.getItem("qe_token") || "";

async function get(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}
async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Dashboard-Token": token() }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || r.status);
  return j;
}

function table(cols, rows, empty = "Aucune donnée") {
  if (!rows || !rows.length) return `<div class="empty">${empty}</div>`;
  const th = cols.map((c) => `<th>${c[0]}</th>`).join("");
  const tr = rows.map((r) => `<tr>${cols.map((c) => `<td class="${c[2] || ""}">${c[1](r)}</td>`).join("")}</tr>`).join("");
  return `<div class="tablewrap"><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
}
const kpi = (l, v, c = "") => `<div class="kpi"><div class="l">${l}</div><div class="v ${c}">${v}</div></div>`;

function lineChart(el, pts, label) {
  if (!pts || pts.length < 2) { el.innerHTML = `<div class="empty">Pas encore d'historique de capital.</div>`; return; }
  const W = 1000, H = 220, P = 30;
  const ys = pts.map((p) => p[1]); const lo = Math.min(...ys), hi = Math.max(...ys); const span = hi - lo || 1;
  const x = (i) => P + (i / (pts.length - 1)) * (W - 2 * P);
  const y = (v) => H - P - ((v - lo) / span) * (H - 2 * P);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">
    <line x1="${P}" y1="${y(lo)}" x2="${W - P}" y2="${y(lo)}" stroke="var(--border)"/>
    <line x1="${P}" y1="${y(hi)}" x2="${W - P}" y2="${y(hi)}" stroke="var(--border)"/>
    <text x="${P}" y="${y(hi) - 6}" fill="var(--muted)" font-size="12">${hi.toFixed(2)} $</text>
    <text x="${P}" y="${y(lo) + 16}" fill="var(--muted)" font-size="12">${lo.toFixed(2)} $</text>
    <path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2"/></svg>`;
}

// ---------------------------------------------------------------- sections
function renderOverview(o) {
  const b = $("#mode-badge");
  b.textContent = o.label; b.className = `badge ${o.simulated ? "sim" : "demo"}`;
  const banner = $("#alert-banner");
  if (o.emergency && o.emergency.active) { banner.textContent = `ARRÊT D'URGENCE : ${o.emergency.reason}`; banner.className = "banner"; }
  else if (o.breaker && o.breaker.tripped) { banner.textContent = `COUPE-CIRCUIT : ${o.breaker.reason} — reprise sur autorisation (onglet Risque)`; banner.className = "banner"; }
  else if (o.recovery && o.recovery.active) { banner.textContent = "Mode récupération : rapprochement des positions en cours"; banner.className = "banner warn"; }
  else banner.className = "banner hidden";
  const tag = o.simulated ? " (simulé)" : "";
  $("#kpis").innerHTML = [
    kpi("Capital virtuel initial", usd(o.starting_capital)),
    kpi("Capital actuel" + tag, usd(o.equity)),
    kpi("Solde disponible", usd(o.balance)),
    kpi("P&L du jour" + tag, sgn(o.daily_pnl), cls(o.daily_pnl)),
    kpi("P&L de la semaine" + tag, sgn(o.weekly_pnl), cls(o.weekly_pnl)),
    kpi("Rendement total" + tag, pct(o.total_return), cls(o.total_return)),
    kpi("Drawdown", pct(o.drawdown), o.drawdown > 0.03 ? "neg" : ""),
    kpi("Positions ouvertes", `${o.open_positions} / 3`),
    kpi("P&L réalisé", sgn(o.realized), cls(o.realized)),
    kpi("Frais payés", usd(o.fees)),
  ].join("");
  $("#equity-note").textContent = o.last_update ? `mis à jour ${new Date(o.last_update).toLocaleString("fr-FR")}` : "aucune donnée";
}

async function loadEquity() {
  const e = await get("/api/equity");
  lineChart($("#equity-chart"), e.points.map((p) => [p.ts, p.equity]), "Évolution du capital");
}

async function loadTrades() {
  const t = await get("/api/trades");
  const open = t.positions.filter((p) => p.state === "open");
  const cols = [["Actif", (p) => `<b>${esc(p.symbol)}</b>`], ["Stratégie", (p) => esc(p.strategy)],
    ["Montant", (p) => usd(p.amount)], ["Entrée", (p) => p.entry?.toFixed(4)], ["Stop", (p) => p.stop?.toFixed(4)],
    ["Objectif", (p) => p.target?.toFixed(4)], ["Risque", (p) => usd(p.risk_usd)],
    ["Source", (p) => p.simulated ? `<span class="chip unavailable">simulé</span>` : `<span class="chip support">eToro démo</span>`]];
  $("#open-positions").innerHTML = table(cols, open, "Aucune position ouverte — refuser de trader est normal.");
  $("#trades").innerHTML = table([...cols.slice(0, 4), ["Sortie", (p) => p.exit?.toFixed(4) ?? "—"],
    ["État", (p) => esc(p.state)], ["Raison", (p) => esc(p.reason ?? ""), "wrap"], ["P&L", (p) => p.pnl == null ? "—" : `<span class="${cls(p.pnl)}">${sgn(p.pnl)}</span>`],
    ["R", (p) => p.r == null ? "—" : p.r.toFixed(2)], ["Frais", (p) => usd(p.fees)],
    ["Hypothèse", (p) => esc(p.hypothesis?.text ?? ""), "wrap"], cols[7]], t.positions, "Aucun trade.");
  $("#orders").innerHTML = table([["Clé", (o) => esc(o.client_key)], ["Date", (o) => esc(o.ts)], ["Actif", (o) => esc(o.symbol)],
    ["Montant", (o) => usd(o.amount)], ["État", (o) => `<span class="chip ${o.state === "confirmed" ? "support" : o.state === "uncertain" ? "veto" : ""}">${esc(o.state)}</span>`],
    ["ID courtier", (o) => esc(o.broker_order_id ?? "")]], t.orders, "Aucun ordre.");
}

async function loadMarket() {
  const m = await get("/api/market");
  $("#scan-info").textContent = m.last_scan ? `scan du ${new Date(m.last_scan.ts).toLocaleString("fr-FR")} · ${m.last_scan.n_candidates} signaux · ${(m.last_scan.mc_paths || 0).toLocaleString("fr-FR")} simulations` : "aucun scan";
  $("#opps").innerHTML = table([["Actif", (r) => `<b>${esc(r.symbol)}</b>`], ["Stratégie", (r) => esc(r.strategy)],
    ["Décision", (r) => `<span class="chip ${r.decision === "BUY" ? "support" : "oppose"}">${esc(r.decision)}</span>`],
    ["Régime", (r) => esc(r.regime ?? "—")], ["Volatilité", (r) => esc(r.volatility ?? "—")],
    ["Technique", (r) => esc(r.technical ?? "—"), "wrap"]], m.opportunities, "Aucun signal au dernier scan.");
  const prices = Object.entries(m.prices || {}).map(([s, v]) => ({ s, ...v }));
  $("#prices").innerHTML = table([["Actif", (r) => esc(r.s)], ["Dernier prix", (r) => r.price?.toFixed(4)],
    ["Plus haut", (r) => r.high?.toFixed(4)], ["Plus bas", (r) => r.low?.toFixed(4)], ["Barre du", (r) => esc(r.bar_date)]],
    prices, "Aucun prix (le bot n'a pas encore tourné).") + (m.simulated ? `<p class="muted">Prix issus de la source configurée ; en mode synthétique ils sont FICTIFS.</p>` : "");
}

async function loadAgents() {
  const a = await get("/api/agents");
  if (!a.decisions.length) { $("#agents").innerHTML = `<div class="empty">Aucune décision enregistrée.</div>`; return; }
  $("#agents").innerHTML = a.decisions.map((d) => `
    <div class="decision">
      <h3>${esc(d.symbol)} · ${esc(d.strategy)} → <span class="chip ${d.authorized ? "support" : "oppose"}">${esc(d.decision)}</span>
        <span class="muted">confiance ${d.confidence?.toFixed(2)}</span></h3>
      ${table([["Agent", (r) => esc(r.agent)], ["Vote", (r) => `<span class="chip ${esc(r.vote)}">${esc(r.vote)}</span>`],
        ["Conclusion", (r) => esc(r.conclusion), "wrap"], ["Confiance", (r) => r.confidence == null ? "—" : r.confidence.toFixed(2)]], d.agents)}
      ${d.reasons.length ? `<p class="muted"><b>Raisons :</b> ${d.reasons.map(esc).join(" · ")}</p>` : ""}
    </div>`).join("");
}

async function loadLab() {
  const l = await get("/api/lab");
  const run = l.latest_run;
  $("#lab-info").textContent = run ? `${run.created} · ${run.total_trades_simulated?.toLocaleString("fr-FR")} trades simulés${run.simulated_data ? " · DONNÉES SIMULÉES" : ""}` : "aucune recherche (lance `research`)";
  $("#leaderboard").innerHTML = table([["#", (r) => r.rank], ["Famille", (r) => `<b>${esc(r.family)}</b>`],
    ["Statut", (r) => `<span class="chip ${r.eligible ? "support" : "oppose"}">${esc(r.status)}</span>`],
    ["Score", (r) => r.score?.toFixed(2)], ["n WF", (r) => r.metrics?.walk_forward?.n ?? "—"],
    ["E[R]", (r) => r.metrics?.walk_forward?.ev_r?.toFixed(3) ?? "—"], ["IC90 bas", (r) => r.metrics?.walk_forward?.ci_low?.toFixed(3) ?? "—"],
    ["PF", (r) => r.metrics?.walk_forward?.profit_factor?.toFixed(2) ?? "—"], ["Sharpe", (r) => r.metrics?.walk_forward?.sharpe?.toFixed(2) ?? "—"],
    ["Sortino", (r) => r.metrics?.walk_forward?.sortino?.toFixed(2) ?? "—"],
    ["Risque coupe-circuit", (r) => pct(r.monte_carlo?.base?.risk_of_ruin, 0)],
    ["Échecs", (r) => esc((r.failed || []).join(" · ")), "wrap"]], run?.leaderboard || [], "Aucune recherche disponible.");
  const real = Object.entries(l.production.strategies || {}).map(([f, e]) => ({ f, sim: false, ...e }));
  const sim = Object.entries(l.production_simulated?.strategies || {}).map(([f, e]) => ({ f, sim: true, ...e }));
  const prod = real.length ? real : sim;
  $("#production").innerHTML = table([["Famille", (r) => esc(r.f)], ["Paramètres", (r) => esc(r.spec.label)],
    ["Validée le", (r) => esc(r.validated_at)], ["Régimes", (r) => esc((r.allowed_regimes || []).join(", "))],
    ["Données", (r) => r.sim ? `<span class="chip unavailable">SIMULÉES — test du pipeline</span>` : `<span class="chip support">réelles</span>`]], prod,
    "Aucune stratégie validée sur données réelles : le bot ne trade pas (c'est voulu).");
  const bt = l.last_backtest;
  $("#backtest").innerHTML = bt ? `<div class="kpis">${[
    kpi("Période de test", esc(bt.period)), kpi("Capital", `${usd(bt.start)} → ${usd(bt.final)}`),
    kpi("Rendement", pct(bt.return), cls(bt.return)), kpi("Drawdown max", pct(bt.max_dd)),
    kpi("Trades", bt.trades), kpi("Profit factor", bt.profit_factor?.toFixed(2)),
    kpi("Buy & hold SPY", pct(bt.buy_and_hold_benchmark))].join("")}</div>
    ${bt.simulated_data ? `<p class="warn"><b>DONNÉES SIMULÉES — résultats sans valeur.</b></p>` : ""}<div id="bt-chart" class="chart"></div>`
    : `<div class="empty">Aucun backtest (lance \`backtest\`).</div>`;
  if (bt) lineChart($("#bt-chart"), bt.equity_curve, "Backtest");
}

function renderRisk(r) {
  const L = r.limits, U = r.usage;
  const bar = (u, l) => `<span class="${u >= l ? "neg" : u >= 0.6 * l ? "warn" : ""}">${usd(u)} / ${usd(l)}</span>`;
  $("#risk-kpis").innerHTML = [kpi("Risque max / trade", usd(L.risk_per_trade)), kpi("Perte du jour", bar(U.daily_loss, L.daily_loss)),
    kpi("Perte de la semaine", bar(U.weekly_loss, L.weekly_loss)), kpi("Drawdown", bar(U.drawdown, L.max_drawdown)),
    kpi("Positions max", L.max_positions), kpi("Gain/risque min", `${L.min_reward_risk} : 1`),
    kpi("Levier", "x1 (verrouillé)"), kpi("Vente à découvert", "désactivée")].join("");
  const br = r.breaker || {}, em = r.emergency || {};
  const active = br.tripped || em.active;
  $("#breaker").innerHTML = active
    ? `<p class="neg"><b>${em.active ? "ARRÊT D'URGENCE" : "COUPE-CIRCUIT"} :</b> ${esc(em.reason || br.reason)} (${esc(em.at || br.at)})</p>`
    : `<p class="pos">Normal : les entrées sont autorisées si toutes les règles sont respectées.</p>`;
  $("#resume-form").classList.toggle("hidden", !active);
  $("#phrase").textContent = r.resume_phrase;
  const pf = r.portfolio || {};
  $("#portfolio").innerHTML = `<div class="kpis">${[kpi("Exposition", usd(pf.exposure)), kpi("Exposition / capital", pct(pf.exposure_pct)),
    kpi("Concentration max", pct(pf.concentration)), kpi("Exposition x volatilité", usd(pf.vol_adjusted_exposure)),
    kpi("Risque jusqu'aux stops", usd(pf.risk_to_stops)), kpi("VaR 95 % 1 jour", usd(pf.var95_1d))].join("")}</div>`;
  $("#events").innerHTML = table([["Date", (e) => esc(e.ts)], ["Niveau", (e) => `<span class="chip ${e.level === "critical" ? "veto" : "unavailable"}">${esc(e.level)}</span>`],
    ["Type", (e) => esc(e.kind)], ["Message", (e) => esc(e.message), "wrap"]], r.events, "Aucun incident.");
}

async function loadWeekly() {
  const w = await get("/api/weekly");
  const rep = w.last_report;
  const closed = w.live_week.closed;
  const pnl = closed.reduce((a, c) => a + (c.pnl || 0), 0);
  let html = `<div class="kpis">${[kpi("Trades (7 j)", closed.length), kpi("P&L net (7 j)", sgn(pnl), cls(pnl)),
    kpi("Opportunités rejetées", w.live_week.rejected)].join("")}</div>`;
  if (rep) {
    const s = rep.stats || {};
    html += `<div class="card"><div class="card-h"><h2>Dernier rapport hebdomadaire</h2><span class="muted">${esc(rep.path)}</span></div>
      <div class="kpis">${[kpi("Trades", s.n ?? 0), kpi("Réussite", pct(s.win_rate, 0)), kpi("P&L net", sgn(s.net), cls(s.net)),
        kpi("Profit factor", s.profit_factor?.toFixed?.(2) ?? "—"), kpi("Gain moyen", sgn(s.avg_win)), kpi("Perte moyenne", sgn(s.avg_loss)),
        kpi("Drawdown max", pct(rep.drawdown)), kpi("Meilleure", esc(s.best ?? "—")), kpi("Pire", esc(s.worst ?? "—"))].join("")}</div>
      <h2>Conclusions</h2><ul>${(rep.audit?.findings || []).map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
      <h2>Propositions (jamais appliquées automatiquement)</h2><ul>${(rep.audit?.proposals || ["aucune"]).map((f) => `<li>${esc(f)}</li>`).join("")}</ul></div>`;
  } else html += `<div class="empty">Le premier rapport hebdomadaire sera généré vendredi après la clôture.</div>`;
  html += `<p class="muted">Une semaine ne prouve rien : il faut 8 à 12 semaines d'observation en démo.</p>`;
  $("#weekly").innerHTML = html;
}

// ---------------------------------------------------------------- navigation & temps réel
const loaders = { overview: async () => { renderOverview(await get("/api/overview")); await loadEquity(); await loadTrades(); },
  market: loadMarket, agents: loadAgents, trades: loadTrades, lab: loadLab,
  risk: async () => renderRisk(await get("/api/risk")), weekly: loadWeekly };
let current = "overview";
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${b.dataset.tab}`));
  current = b.dataset.tab; refresh();
}));
async function refresh() { try { await loaders[current](); } catch (e) { console.error(e); } }

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => $("#conn").classList.add("on");
  ws.onclose = () => { $("#conn").classList.remove("on"); setTimeout(connect, 3000); };
  ws.onmessage = (m) => { const d = JSON.parse(m.data); renderOverview(d.overview); if (current === "risk") renderRisk(d.risk); };
}

$("#btn-emergency").addEventListener("click", async () => {
  if (!confirm("Arrêter le bot et fermer toutes ses positions démo ?")) return;
  try { const r = await post("/api/emergency-stop", { reason: "arrêt depuis le tableau de bord", close_all: true }); alert(r.message); refresh(); }
  catch (e) { const t = prompt("Jeton du tableau de bord requis :"); if (t) { localStorage.setItem("qe_token", t); } alert(`Échec : ${e.message}`); }
});
$("#resume-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = new FormData(ev.target);
  try { const r = await post("/api/resume", Object.fromEntries(f)); $("#resume-msg").textContent = r.message; refresh(); }
  catch (e) { $("#resume-msg").textContent = `Refusé : ${e.message}`; }
});

refresh(); connect(); setInterval(refresh, 30000);
