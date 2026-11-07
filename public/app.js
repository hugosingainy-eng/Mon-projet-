// Tableau de bord du QG des Agents (vanilla JS, aucune étape de build).
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s = '') => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const STATUS = {
  nouveau: ['Nouveau', ''],
  rejete: ['Écarté par le Boss', 'bad'],
  verif_site: ['Vérification du site sur Google', 'info'],
  recherche_email: ['Recherche de l’email', 'info'],
  a_auditer: ['Site à auditer', 'info'],
  audit_en_cours: ['Audit en cours', 'info'],
  qualifie: ['Qualifié', 'accent'],
  ecarte: ['Bon site (écarté)', ''],
  site_en_cours: ['Site en création', 'info'],
  site_valide: ['Site validé', 'ok'],
  email_en_cours: ['Email en rédaction', 'info'],
  email_manquant: ['Email à renseigner', 'warn'],
  pret_a_envoyer: ['Prêt à envoyer', 'ok'],
  envoye: ['Envoyé', 'ok'],
  en_file: ['En file', 'info'],
  bloque: ['Bloqué par le Boss', 'bad'],
  erreur: ['Erreur', 'bad'],
};
const SEGMENT = { sans_site: ['Sans site', 'accent'], mauvais_site: ['Mauvais site', 'warn'], bon_site: ['Bon site', ''] };
const pill = (map, key) => {
  const [label, cls] = map[key] || [key || '—', ''];
  return `<span class="pill ${cls}">${esc(label)}</span>`;
};

let state = { auto: { status: {}, programs: [] }, status: null, leads: [], lastMsgId: 0, messages: [], missions: [], team: [], active: {}, showHelpers: true };

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401 && path !== '/api/login') { showLogin(); throw new Error('Non connecté'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Erreur ${res.status}`);
  return data;
}

function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 3500);
}

const timeAgo = (iso) => {
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T') + 'Z');
  const s = (Date.now() - d) / 1000;
  if (s < 60) return 'à l’instant';
  if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
  return d.toLocaleDateString('fr-FR');
};

// ---------- Connexion ----------
function showLogin() { $('#app').hidden = true; $('#login').hidden = false; }
$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('#login-error').textContent = '';
  try {
    await api('/api/login', { method: 'POST', body: { password: e.target.password.value } });
    e.target.reset();
    start();
  } catch (err) { $('#login-error').textContent = err.message; }
});
$('#logout').addEventListener('click', async () => { await api('/api/logout', { method: 'POST' }); showLogin(); });

// ---------- Navigation ----------
function route() {
  const [path, qs] = location.hash.slice(2).split('?');
  const view = path || 'dashboard';
  const page = ['dashboard', 'autopilot', 'leads', 'missions', 'feed', 'settings'].includes(view) ? view : 'dashboard';
  $$('[data-page]').forEach((s) => (s.hidden = s.dataset.page !== page));
  $$('.side nav a').forEach((a) => a.classList.toggle('active', a.dataset.view === page));
  const params = new URLSearchParams(qs || '');
  if (page === 'leads' && params.has('status')) $('#lead-status').value = params.get('status');
  refresh();
}
window.addEventListener('hashchange', route);

// ---------- Rendu ----------
function renderOrg() {
  if (!state.team.length) return;
  const on = (n) => state.active[n] > 0;
  const chip = (h) => `<li class="helper ${on(h.name) ? 'busy' : ''}" title="${esc(h.role)}">
    <span class="helper-ico">${h.ico}</span><span><b>${esc(h.name)}</b><small>${esc(h.role)}</small></span></li>`;
  const card = (a, cls = '') => {
    const teamBusy = a.helpers.filter((h) => on(h.name)).length;
    const busy = on(a.name) || teamBusy > 0;
    const stateTxt = busy
      ? (teamBusy ? `${teamBusy} sous-agent(s) au travail` : a.name === 'Boss' ? 'en train de vérifier' : 'au travail')
      : a.name === 'Boss' ? 'en attente de livrables' : 'disponible';
    return `<div class="agent ${cls} ${busy ? 'busy' : ''}">
      <div class="agent-top"><div class="agent-ico">${a.ico}</div><div><h3>${esc(a.name)}</h3><div class="state">${stateTxt}</div></div></div>
      <p>${esc(a.role)}</p>
      <div class="team-label">${a.name === 'Boss' ? 'Ses assistants' : 'Son équipe'}</div>
      <ul class="helpers">${a.helpers.map(chip).join('')}</ul></div>`;
  };
  const [bossA, ...chefs] = state.team;
  $('#org').innerHTML = `<div class="org-boss">${card(bossA, 'boss')}</div><div class="org-line"></div>
    <div class="org-team">${chefs.map((a) => card(a)).join('')}</div>`;
}

async function renderStats() {
  const s = await api('/api/stats');
  const b = s.byStatus;
  const items = [
    [s.total, 'prospects trouvés'],
    [s.bySegment.sans_site || 0, 'sans site internet'],
    [s.bySegment.mauvais_site || 0, 'avec un mauvais site'],
    [(b.pret_a_envoyer || 0) + (b.email_manquant || 0), 'dossiers validés'],
    [b.envoye || 0, 'emails envoyés'],
    [s.rejets, 'renvois du Boss'],
    [s.corrections, 'corrections en équipe'],
  ];
  $('#stats').innerHTML = items.map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join('');
}

function renderReady() {
  const ready = state.leads.filter((l) => ['pret_a_envoyer', 'email_manquant'].includes(l.status)).slice(0, 8);
  $('#ready-list').innerHTML = ready.length
    ? ready.map((l) => `<div class="list-item" data-lead="${l.id}"><div><h4>${esc(l.name)}</h4>
        <small>${esc(l.category)} · ${esc(l.email || 'email à renseigner')}</small></div>${pill(STATUS, l.status)}</div>`).join('')
    : '<div class="empty">Aucun dossier validé pour l’instant. Lancez une mission ci-dessus.</div>';
}

function msgHtml(m) {
  const ico = { validation: '✅', rejet: '↩️', livraison: '📦', erreur: '⚠️', info: '💬', consigne: '📋', 'sous-livraison': '📎', correction: '✏️' }[m.kind] || '💬';
  return `<div class="msg ${m.kind} ${m.level ? 'sub' : ''}" ${m.lead_id ? `data-lead="${m.lead_id}" style="cursor:pointer"` : ''}>
    <div class="msg-ico">${ico}</div><div>
    <div class="msg-meta"><b>${esc(m.from_agent)} → ${esc(m.to_agent)}</b>${m.lead_name ? `<span>· ${esc(m.lead_name)}</span>` : ''}<span>· ${timeAgo(m.created_at)}</span></div>
    <div class="msg-body">${esc(m.content)}</div></div></div>`;
}

function renderFeeds() {
  const recent = state.messages.filter((m) => !m.level).slice(-8).reverse();
  $('#mini-feed').innerHTML = recent.length ? recent.map(msgHtml).join('') : '<div class="empty">Les échanges entre agents apparaîtront ici.</div>';
  const all = state.messages.filter((m) => state.showHelpers || !m.level);
  $('#feed').innerHTML = all.length ? [...all].reverse().map(msgHtml).join('') : '<div class="empty">Aucun échange pour le moment.</div>';
}

function renderLeads() {
  const q = $('#lead-search').value.toLowerCase();
  const st = $('#lead-status').value;
  const rows = state.leads.filter((l) => (!st || l.status === st) && (!q || `${l.name} ${l.address} ${l.category}`.toLowerCase().includes(q)));
  $('#leads-table').innerHTML = `<thead><tr><th>Entreprise</th><th>Priorité</th><th>Situation</th><th>Note Google</th><th>Email</th><th>Statut</th></tr></thead>
    <tbody>${rows.map((l) => `<tr data-lead="${l.id}">
      <td><strong>${esc(l.name)}</strong><small>${esc(l.category)} · ${esc(l.address)}</small></td>
      <td class="num">${l.priority != null ? `<span class="prio" style="--p:${l.priority}">${l.priority}</span>` : '—'}</td>
      <td>${l.segment ? pill(SEGMENT, l.segment) : '<span class="muted">—</span>'}${l.audit_score != null ? `<small>audit ${l.audit_score}/100</small>` : ''}</td>
      <td class="num">${l.rating ? `★ ${l.rating} <small>${l.reviews_count} avis</small>` : '—'}</td>
      <td>${esc(l.email || '—')}</td>
      <td>${pill(STATUS, l.status)}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">Aucun prospect.</td></tr>'}</tbody>`;
}

function renderMissions() {
  const label = { en_attente: ['En attente', ''], en_cours: ['En cours', 'info'], terminee: ['Terminée', 'ok'], erreur: ['Erreur', 'bad'], interrompue: ['Interrompue', 'warn'] };
  $('#missions-table').innerHTML = `<thead><tr><th>Mission</th><th>Lancée</th><th>Prospects</th><th>Validés</th><th>Statut</th><th></th></tr></thead>
    <tbody>${state.missions.map((m) => `<tr data-mission="${m.id}">
      <td><strong>${esc(m.query)}</strong><small>${esc(m.city)}${m.autopilot_id ? ' · pilote auto' : ''}</small></td><td>${timeAgo(m.created_at)}</td>
      <td class="num">${m.leads}</td><td class="num">${m.ready}</td><td>${pill(label, m.running ? 'en_cours' : m.status)}</td>
      <td><button class="btn small danger" data-del-mission="${m.id}">Supprimer</button></td></tr>`).join('')
      || '<tr><td colspan="6" class="empty">Aucune mission. Lancez-en une depuis le tableau de bord.</td></tr>'}</tbody>`;
}

function renderSettings() {
  const s = state.status;
  const line = (ok, title, desc) => `<div class="setting-row"><div><strong>${title}</strong><p class="muted">${desc}</p></div>${pill({ y: ['Actif', 'ok'], n: ['À configurer', 'warn'] }, ok ? 'y' : 'n')}</div>`;
  $('#settings').innerHTML = `
    <div class="setting-row"><div><strong>Envoi automatique</strong><p class="muted">Dès que le Boss valide un dossier avec une adresse email, l’email part tout seul. Désactivé : vous cliquez sur « Envoyer » vous-même.</p></div>
      <label class="switch"><input type="checkbox" id="auto-send" ${s.autoSend ? 'checked' : ''} ${s.smtp ? '' : 'disabled'}><span></span></label></div>
    <div class="setting-row"><div><strong>Règles d’envoi</strong><p class="muted">Pour ne pas finir en spam, les envois automatiques sont étalés (1 à 3 min entre deux emails) et plafonnés. Les dossiers en attente partent au prochain créneau.</p>
      <div class="inline"><input type="number" id="send-limit" min="1" max="500" value="${s.sendLimit}"> emails max / jour, de
      <input type="number" id="send-start" min="0" max="23" value="${s.sendStart}"> h à <input type="number" id="send-end" min="1" max="24" value="${s.sendEnd}"> h
      <label class="toggle"><input type="checkbox" id="send-weekdays" ${s.sendWeekdaysOnly ? 'checked' : ''}> en semaine seulement</label></div></div></div>
    <div class="setting-row"><div><strong>Rapport quotidien</strong><p class="muted">Chaque jour, le Boss vous résume les dernières 24 h : nouveaux prospects, sites créés, emails envoyés, dossiers à regarder.</p>
      <div class="inline">à <input type="number" id="report-hour" min="0" max="23" value="${s.reportHour}"> h, envoyé à <input type="email" id="owner-email" placeholder="vous@exemple.fr" value="${esc(s.ownerEmail)}"></div></div>
      <label class="switch"><input type="checkbox" id="daily-report" ${s.dailyReport ? 'checked' : ''}><span></span></label></div>
    ${line(!s.demoGoogle, 'Google Maps (Places API)', s.demoGoogle ? 'Mode démo : données fictives. Ajoutez <code>GOOGLE_MAPS_API_KEY</code> dans <code>.env</code>.' : 'Recherche réelle sur Google Maps.')}
    ${line(s.googleSearch || !s.demoAi, 'Recherche Google (sites cachés et emails)', s.googleSearch ? 'Recherche Google réelle via Serper.' : !s.demoAi ? 'Recherche web assurée par Claude. Pour des résultats Google directs, ajoutez <code>SERPER_API_KEY</code>.' : 'Ajoutez <code>SERPER_API_KEY</code> (serper.dev) ou <code>ANTHROPIC_API_KEY</code>.')}
    ${line(!s.demoAi, 'Intelligence artificielle (Claude)', s.demoAi ? 'Sans IA : gabarits et contrôles automatiques uniquement. Ajoutez <code>ANTHROPIC_API_KEY</code>.' : `Modèle : <code>${esc(s.model)}</code>`)}
    ${line(s.smtp, 'Envoi d’emails (SMTP)', s.smtp ? 'Prêt à envoyer.' : 'Renseignez <code>SMTP_HOST</code>, <code>SMTP_USER</code>, <code>SMTP_PASS</code>.')}
    <div class="setting-row"><div><strong>Votre signature</strong><p class="muted">${esc(s.sender.name)} · ${esc(s.sender.company)} · ${esc(s.sender.email || 'email non défini')}<br>Offre : ${esc(s.sender.offer)}<br>À modifier dans <code>.env</code> (SENDER_*).</p></div></div>
    <div class="setting-row"><div><strong>Exigence du Boss</strong><p class="muted">Jusqu’à ${s.maxRevisions} allers-retours par livrable avant de bloquer un dossier (<code>MAX_REVISIONS</code>).</p></div></div>`;
  const save = async (body, msg) => {
    try { await api('/api/settings', { method: 'POST', body }); Object.assign(state.status, await api('/api/status')); toast(msg); }
    catch (err) { toast(err.message); }
  };
  $('#send-limit').addEventListener('change', (e) => save({ sendLimit: e.target.value }, 'Plafond d’envoi enregistré'));
  $('#send-start').addEventListener('change', (e) => save({ sendStart: e.target.value }, 'Horaires enregistrés'));
  $('#send-end').addEventListener('change', (e) => save({ sendEnd: e.target.value }, 'Horaires enregistrés'));
  $('#send-weekdays').addEventListener('change', (e) => save({ sendWeekdaysOnly: e.target.checked }, 'Enregistré'));
  $('#report-hour').addEventListener('change', (e) => save({ reportHour: e.target.value }, 'Heure du rapport enregistrée'));
  $('#owner-email').addEventListener('change', (e) => save({ ownerEmail: e.target.value }, 'Adresse du rapport enregistrée'));
  $('#daily-report').addEventListener('change', (e) => save({ dailyReport: e.target.checked }, e.target.checked ? 'Rapport quotidien activé' : 'Rapport quotidien désactivé'));
  $('#auto-send')?.addEventListener('change', async (e) => {
    await api('/api/settings', { method: 'POST', body: { autoSend: e.target.checked } });
    state.status.autoSend = e.target.checked;
    toast(e.target.checked ? 'Envoi automatique activé' : 'Envoi automatique désactivé');
  });
}

function renderBadges() {
  const s = state.status;
  $('#mode-badges').innerHTML = [
    [!s.demoGoogle, s.demoGoogle ? 'Google Maps : démo' : 'Google Maps : réel'],
    [!s.demoAi, s.demoAi ? 'IA : désactivée' : 'IA : Claude'],
    [s.googleSearch || !s.demoAi, s.googleSearch ? 'Recherche web : Google' : !s.demoAi ? 'Recherche web : Claude' : 'Recherche web : à configurer'],
    [s.smtp, s.smtp ? 'Emails : prêts' : 'Emails : à configurer'],
  ].map(([ok, t]) => `<span><i class="${ok ? '' : 'off'}"></i>${t}</span>`).join('');
}

// ---------- Pilote automatique ----------
const inMinutes = (iso) => {
  if (!iso) return '—';
  const m = Math.round((new Date(iso) - Date.now()) / 60000);
  if (m <= 0) return 'imminente';
  if (m < 60) return `dans ${m} min`;
  return `à ${new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`;
};

function renderAuto() {
  const st = state.auto.status || {};
  const progs = state.auto.programs || [];
  $('#nav-auto-dot').hidden = !st.active;
  $('#auto-strip').innerHTML = progs.length
    ? `<span class="led ${st.active ? 'on' : ''}"></span><b>Pilote auto ${st.active ? 'en marche' : 'à l’arrêt'}</b>
       <span class="sep">|</span><span>${st.active} programme(s) actif(s)</span>
       <span class="sep">|</span><span>${st.searching ? 'recherche en cours…' : `prochaine recherche ${inMinutes(st.nextRunAt)}`}</span>
       <span class="sep">|</span><span>${st.sendsToday}/${st.sendLimit} emails envoyés aujourd’hui${st.sendOk ? '' : ` · envoi en pause : ${esc(st.sendReason)}`}</span>`
    : `<span class="led"></span><b>Pilote auto</b><span>Faites travailler vos agents 24h/24 : créez un programme →</span>`;

  if ($('[data-page="autopilot"]').hidden) return;
  const tile = (n, l) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`;
  $('#auto-status').innerHTML =
    tile(st.active || 0, 'programmes actifs') +
    tile(st.searching ? '●' : inMinutes(st.nextRunAt), st.searching ? 'recherche en cours' : 'prochaine recherche') +
    tile(`${st.sendsToday ?? 0}/${st.sendLimit ?? 0}`, st.sendOk ? 'emails envoyés aujourd’hui' : `envoi en pause : ${esc(st.sendReason || '')}`) +
    tile(progs.reduce((s, p) => s + p.total_leads, 0), 'prospects trouvés par le pilote');

  $('#auto-list').innerHTML = progs.length ? progs.map((p) => {
    const pct = p.combos ? Math.round(((p.position - 1) / p.combos) * 100) : 0;
    const tags = (arr, max) => arr.slice(0, max).map((t) => `<span class="pill">${esc(t)}</span>`).join('') + (arr.length > max ? `<span class="pill">+${arr.length - max}</span>` : '');
    return `<div class="program ${p.active ? 'on' : ''}">
      <div class="program-head"><div><h3>${esc(p.name)}</h3>
        <span class="muted">${p.running ? '● recherche en cours' : !p.active ? 'en pause' : p.leads_today >= p.daily_limit ? 'limite du jour atteinte : reprise à minuit' : `prochaine recherche ${inMinutes(p.next_run_at)}`} · toutes les ${p.interval_minutes} min</span></div>
        <div class="program-actions">
          <button class="btn small" data-auto-run="${p.id}">Lancer maintenant</button>
          <button class="btn small danger" data-auto-del="${p.id}">Supprimer</button>
          <label class="switch" title="Activer / mettre en pause"><input type="checkbox" data-auto-toggle="${p.id}" ${p.active ? 'checked' : ''}><span></span></label>
        </div></div>
      <div class="tags">${tags(p.queries, 8)}</div>
      <div class="tags">${tags(p.cities, 10)}</div>
      <div class="progress" title="Avancement du cycle"><i style="width:${pct}%"></i></div>
      <div class="program-meta">
        <span>Cycle <b>${p.cycle}</b> · recherche <b>${p.position}/${p.combos}</b></span>
        <span>Aujourd’hui <b>${p.leads_today}/${p.daily_limit}</b> nouveaux prospects</span>
        <span>Total <b>${p.total_leads}</b> prospects en <b>${p.runs}</b> recherches</span>
      </div>
      ${p.last_result ? `<div class="muted" style="font-size:13px">Dernière recherche : ${esc(p.last_result)}</div>` : ''}
    </div>`;
  }).join('') : '<div class="empty">Aucun programme. Créez-en un ci-dessus : vos agents chercheront en continu, même quand vous dormez.</div>';
}

$('#auto-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  const btn = f.querySelector('button[type=submit]');
  btn.disabled = true;
  btn.textContent = f.expand.checked ? 'Préparation de la zone…' : 'Démarrage…';
  try {
    const r = await api('/api/autopilot', { method: 'POST', body: {
      name: f.name.value, queries: f.queries.value, cities: f.cities.value, expand: f.expand.checked,
      intervalMinutes: f.intervalMinutes.value, resultsPerRun: f.resultsPerRun.value, dailyLimit: f.dailyLimit.value,
    } });
    toast(`Programme démarré sur ${r.cities.length} zone(s) 🚀`);
    f.reset();
    refresh();
  } catch (err) { toast(err.message); }
  btn.disabled = false;
  btn.textContent = 'Démarrer le programme';
});

$('#auto-list').addEventListener('click', async (e) => {
  const run = e.target.closest('[data-auto-run]');
  const del = e.target.closest('[data-auto-del]');
  try {
    if (run) { await api(`/api/autopilot/${run.dataset.autoRun}`, { method: 'PATCH', body: { runNow: true } }); toast('Recherche lancée dans la minute'); }
    if (del && confirm('Supprimer ce programme ? Les prospects déjà trouvés sont conservés.')) {
      await api(`/api/autopilot/${del.dataset.autoDel}`, { method: 'DELETE' }); toast('Programme supprimé');
    }
    if (run || del) refresh();
  } catch (err) { toast(err.message); }
});
$('#auto-list').addEventListener('change', async (e) => {
  const t = e.target.closest('[data-auto-toggle]');
  if (!t) return;
  await api(`/api/autopilot/${t.dataset.autoToggle}`, { method: 'PATCH', body: { active: t.checked } });
  toast(t.checked ? 'Programme relancé' : 'Programme en pause');
  refresh();
});

// ---------- Fiche prospect ----------
function webCheckHtml(l) {
  const w = l.web_check;
  if (!w) return '';
  const social = (w.social || []).map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\/(www\.)?/, '').slice(0, 40))}</a>`).join(', ');
  const txt = !w.searched
    ? 'Non vérifié sur Google (aucun moteur de recherche configuré).'
    : w.website
      ? `🌐 Site absent de Google Maps mais trouvé sur le web (${esc(w.engine)}, confiance ${w.score}/100).`
      : `🌐 Vérifié sur le web (${esc(w.engine)}) : aucun site officiel.`;
  return `<small class="hint">${txt}${social ? `<br>Réseaux sociaux : ${social}` : ''}</small>`;
}

function emailInfoHtml(l) {
  const e = l.email_info;
  if (!e) return '';
  if (!e.found) return '<small class="hint">📧 Recherché sur le web : aucune adresse publiée trouvée.</small>';
  const src = e.source && /^https?:/.test(e.source)
    ? `<a href="${esc(e.source)}" target="_blank" rel="noopener">${esc(e.source.replace(/^https?:\/\/(www\.)?/, '').slice(0, 50))}</a>`
    : esc(e.source || '');
  const alts = (e.alternatives || []).map((a) => `${esc(a.email)} (${a.score})`).join(', ');
  return `<small class="hint">📧 Trouvé via ${esc(e.engine)} sur ${src} · confiance ${e.score}/100${alts ? `<br>Autres pistes : ${alts}` : ''}</small>`;
}

let current = null;
let currentTab = 'fiche';

async function openLead(id, tab = 'fiche') {
  current = await api(`/api/leads/${id}`);
  currentTab = tab;
  $('#drawer').hidden = false;
  $('#drawer-backdrop').hidden = false;
  renderDrawer();
}
function closeDrawer() { $('#drawer').hidden = true; $('#drawer-backdrop').hidden = true; current = null; }
$('#drawer-close').addEventListener('click', closeDrawer);
$('#drawer-backdrop').addEventListener('click', closeDrawer);
document.addEventListener('keydown', (e) => e.key === 'Escape' && closeDrawer());
$('#d-tabs').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-tab]');
  if (b) { currentTab = b.dataset.tab; renderDrawer(); }
});

function renderDrawer() {
  const l = current;
  $('#d-name').textContent = l.name;
  $('#d-sub').innerHTML = `${esc(l.category)} · ${pill(STATUS, l.status)} ${l.segment ? pill(SEGMENT, l.segment) : ''}`;
  $$('#d-tabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === currentTab));
  const body = $('#d-body');

  if (currentTab === 'fiche') {
    const raw = l.raw || {};
    body.innerHTML = `<dl class="kv">
      <dt>Adresse</dt><dd>${esc(l.address)}</dd>
      <dt>Téléphone</dt><dd>${esc(l.phone || '—')}</dd>
      <dt>Email</dt><dd>${esc(l.email || 'non trouvé')}${emailInfoHtml(l)}
        <form class="inline-form" id="email-form"><input name="email" type="email" placeholder="contact@entreprise.fr" value="${esc(l.email || '')}"><button class="btn small">Enregistrer</button></form></dd>
      <dt>Site actuel</dt><dd>${l.website ? `<a href="${esc(l.website)}" target="_blank" rel="noopener">${esc(l.website)}</a>` : 'Aucun'}${webCheckHtml(l)}</dd>
      <dt>Google Maps</dt><dd>${l.maps_url ? `<a href="${esc(l.maps_url)}" target="_blank" rel="noopener">Voir la fiche</a>` : '—'}</dd>
      <dt>Note</dt><dd>${l.rating ? `★ ${l.rating} (${l.reviews_count} avis)` : '—'}</dd>
      <dt>Horaires</dt><dd>${(raw.hours || []).map(esc).join('<br>') || '—'}</dd>
    </dl>
    ${l.boss_notes ? `<div class="section-title">Note du Boss</div><div class="note">${esc(l.boss_notes)}</div>` : ''}
    ${(raw.reviews || []).length ? `<div class="section-title">Avis Google</div>${raw.reviews.map((r) => `<div class="note" style="margin-bottom:8px">“${esc(r.text)}” — <em>${esc(r.author)}</em></div>`).join('')}` : ''}`;
    $('#email-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        await api(`/api/leads/${l.id}`, { method: 'PATCH', body: { email: e.target.email.value } });
        toast('Email enregistré');
        openLead(l.id, 'fiche'); refresh();
      } catch (err) { toast(err.message); }
    });
  }

  if (currentTab === 'audit') {
    const a = l.audit;
    body.innerHTML = !a ? `<div class="empty">${l.website ? 'Audit pas encore réalisé.' : 'Pas de site à auditer : cette entreprise n’a pas de site internet.'}</div>` : `
      <div style="display:flex;gap:24px;align-items:center;flex-wrap:wrap">
        <div><div class="score">${a.note_globale}<small style="font-size:18px">/100</small></div><span class="muted">note de l’Auditeur</span></div>
        <div>${pill(SEGMENT, a.verdict)}<p class="muted">${esc(a.justification)}</p></div></div>
      <div class="section-title">Mesures techniques (${a.tech?.score ?? '—'}/100)</div>
      <div class="checks">${(a.tech?.checks || []).map((c) => `<div class="check"><span>${c.ok ? '✅' : '❌'}</span><div>${esc(c.label)} ${c.detail ? `<small>${esc(c.detail)}</small>` : ''}</div></div>`).join('')}</div>
      ${a.problemes?.length ? `<div class="section-title">Problèmes</div><ul>${a.problemes.map((p) => `<li>${esc(p)}</li>`).join('')}</ul>` : ''}
      ${a.arguments_commerciaux?.length ? `<div class="section-title">Arguments commerciaux</div><ul>${a.arguments_commerciaux.map((p) => `<li>${esc(p)}</li>`).join('')}</ul>` : ''}`;
  }

  if (currentTab === 'site') {
    body.innerHTML = l.siteUrl
      ? `<p><a href="${l.siteUrl}" target="_blank" rel="noopener">Ouvrir le site dans un nouvel onglet ↗</a></p><iframe class="preview" src="${l.siteUrl}" title="Aperçu du site"></iframe>`
      : '<div class="empty">Le site n’a pas encore été créé (ou validé par le Boss).</div>';
  }

  if (currentTab === 'email') {
    body.innerHTML = l.email_subject
      ? `<dl class="kv"><dt>À</dt><dd>${esc(l.email || '⚠️ adresse à renseigner dans l’onglet Fiche')}</dd><dt>Objet</dt><dd><strong>${esc(l.email_subject)}</strong></dd></dl>
         <div class="section-title">Aperçu tel que reçu par le prospect</div><iframe class="preview" src="/api/leads/${l.id}/email" title="Aperçu de l’email"></iframe>`
      : '<div class="empty">L’email n’a pas encore été rédigé et validé.</div>';
  }

  if (currentTab === 'boss') {
    body.innerHTML = `<div class="feed">${l.messages.length ? l.messages.map((m) => msgHtml({ ...m, lead_name: null })).join('') : '<div class="empty">Aucun échange.</div>'}</div>`;
  }

  // Actions
  const canSend = l.status === 'pret_a_envoyer' && state.status.smtp;
  const canRetry = ['bloque', 'erreur', 'rejete', 'ecarte'].includes(l.status);
  $('#d-foot').innerHTML = `
    <button class="btn danger" data-act="delete">Supprimer</button>
    ${l.site_slug && !['site_en_cours', 'email_en_cours'].includes(l.status) && l.status !== 'envoye' ? '<button class="btn" data-act="redo-site">Refaire le site</button>' : ''}
    ${!['envoye', 'recherche_email', 'verif_site', 'site_en_cours', 'email_en_cours', 'audit_en_cours'].includes(l.status) ? `<button class="btn" data-act="find-email">${l.email ? 'Chercher un autre email' : 'Rechercher l’email sur le web'}</button>` : ''}
    ${canRetry ? `<button class="btn" data-act="retry">${['rejete', 'ecarte'].includes(l.status) ? 'Traiter quand même' : 'Relancer'}</button>` : ''}
    ${l.status === 'pret_a_envoyer' ? `<button class="btn primary" data-act="send" ${canSend ? '' : 'disabled title="Configurez le SMTP"'}>Envoyer l’email</button>` : ''}
    ${l.status === 'envoye' ? `<span class="pill ok">Envoyé ${timeAgo(l.sent_at)}</span>` : ''}`;
}

$('#d-foot').addEventListener('click', async (e) => {
  const act = e.target.closest('[data-act]')?.dataset.act;
  if (!act || !current) return;
  const id = current.id;
  try {
    if (act === 'send') {
      if (!confirm(`Envoyer l’email à ${current.email} ?`)) return;
      await api(`/api/leads/${id}/send`, { method: 'POST' });
      toast('Email envoyé ✉️');
    }
    if (act === 'retry') { await api(`/api/leads/${id}/retry`, { method: 'POST', body: {} }); toast('Dossier renvoyé aux agents'); }
    if (act === 'find-email') { await api(`/api/leads/${id}/find-email`, { method: 'POST' }); toast('Le Détective email part chercher sur le web 📧'); }
    if (act === 'redo-site') { await api(`/api/leads/${id}/retry`, { method: 'POST', body: { redo: 'site' } }); toast('Le Créateur de site recommence'); }
    if (act === 'delete') {
      if (!confirm('Supprimer ce prospect ?')) return;
      await api(`/api/leads/${id}`, { method: 'DELETE' });
      closeDrawer(); refresh(); return;
    }
    openLead(id, currentTab); refresh();
  } catch (err) { toast(err.message); }
});

// Clics sur les listes
document.addEventListener('click', async (e) => {
  const del = e.target.closest('[data-del-mission]');
  if (del) {
    e.stopPropagation();
    if (confirm('Supprimer cette mission et tous ses prospects ?')) {
      await api(`/api/missions/${del.dataset.delMission}`, { method: 'DELETE' });
      refresh();
    }
    return;
  }
  const lead = e.target.closest('[data-lead]');
  if (lead && !e.target.closest('#drawer')) return openLead(lead.dataset.lead);
  const mission = e.target.closest('[data-mission]');
  if (mission) { location.hash = '#/leads'; }
});

$('#mission-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  try {
    await api('/api/missions', { method: 'POST', body: { query: f.query.value, city: f.city.value, maxResults: f.maxResults.value } });
    toast('Mission lancée : le Prospecteur part chercher 🧭');
    f.query.value = '';
    refresh();
  } catch (err) { toast(err.message); }
});

$('#lead-search').addEventListener('input', renderLeads);
$('#show-helpers').addEventListener('change', (e) => { state.showHelpers = e.target.checked; renderFeeds(); });
$('#lead-status').innerHTML = '<option value="">Tous les statuts</option>' + Object.entries(STATUS).map(([k, [l]]) => `<option value="${k}">${l}</option>`).join('');
$('#lead-status').addEventListener('change', renderLeads);

// ---------- Rafraîchissement ----------
async function refresh() {
  try {
    const [leads, missions, msgs, team, auto] = await Promise.all([
      api('/api/leads'), api('/api/missions'), api(`/api/messages?since=${state.lastMsgId}`), api('/api/team'), api('/api/autopilot'),
    ]);
    state.auto = auto;
    state.team = team.team;
    state.active = team.active;
    state.leads = leads;
    state.missions = missions;
    if (msgs.length) {
      state.messages.push(...msgs);
      state.messages = state.messages.slice(-300);
      state.lastMsgId = msgs[msgs.length - 1].id;
    }
    renderOrg(); renderReady(); renderFeeds(); renderLeads(); renderMissions(); renderAuto();
    if (!$('[data-page="dashboard"]').hidden) renderStats();
  } catch { /* hors ligne ou déconnecté */ }
}

async function start() {
  try {
    state.status = await api('/api/status');
  } catch { return; }
  $('#login').hidden = true;
  $('#app').hidden = false;
  renderBadges();
  renderSettings();
  route();
  clearInterval(start.timer);
  start.timer = setInterval(refresh, 3000);
}

start();
