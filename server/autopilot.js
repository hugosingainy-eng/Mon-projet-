// Pilote automatique : les agents travaillent 24h/24, 7j/7, sans intervention.
//
// Toutes les minutes, le planificateur :
//  1. lance la prochaine recherche des programmes actifs (métier × ville, à tour de rôle) ;
//  2. envoie les dossiers prêts, dans les horaires et le plafond d'envoi ;
//  3. vous envoie le rapport du jour (une fois par jour).
//
// Au redémarrage du serveur, les dossiers interrompus reprennent automatiquement.
import { db, getLead, logMessage, updateLead, getSetting, setSetting } from './db.js';
import { config } from './config.js';
import { runMission, processLead, sendLead } from './orchestrator.js';
import { canAutoSend, parisNow, setting, sendsToday } from './sendPolicy.js';
import { sendMail, smtpConfigured } from './services/mailer.js';
import { askJson, aiAvailable, obj } from './llm.js';

const TRANSIENT = ['audit_en_cours', 'site_en_cours', 'email_en_cours', 'en_file', 'a_auditer', 'qualifie',
  'site_valide', 'verif_site', 'recherche_email'];

let missionBusy = false;   // une seule recherche automatique à la fois (maîtrise des coûts)
let flushing = false;
let ticking = false;
let timer = null;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- Programmes ----------
export function parseList(text) {
  return [...new Set(String(text || '').split(/[,;\n]+/).map((s) => s.trim()).filter(Boolean))];
}

export function getAutopilot(id) {
  const a = db.prepare('SELECT * FROM autopilots WHERE id = ?').get(id);
  if (!a) return null;
  return { ...a, queries: JSON.parse(a.queries), cities: JSON.parse(a.cities) };
}

export function listAutopilots() {
  return db.prepare('SELECT id FROM autopilots ORDER BY id DESC').all().map((r) => {
    const a = getAutopilot(r.id);
    const combos = a.queries.length * a.cities.length;
    return {
      ...a,
      combos,
      position: combos ? (a.cursor % combos) + 1 : 0,
      leads_today: a.day === parisNow().ymd ? a.leads_today : 0,
      running: missionBusy === a.id,
    };
  });
}

/** Élargit une ville à ses arrondissements / communes voisines (avec l'IA). */
export async function expandCities(cities) {
  if (!aiAvailable()) return cities;
  try {
    const r = await askJson({
      system: "Tu aides une agence web à quadriller une zone pour trouver des commerces locaux sur Google Maps.",
      prompt: `Zones : ${cities.join(', ')}.\nPour chaque zone, liste ses arrondissements ou quartiers (grandes villes) et les communes voisines ` +
        "de plus de 3 000 habitants, dans un rayon d'environ 15 km. Noms tels qu'on les tape dans Google Maps (ex. « Lyon 3e », « Villeurbanne »). 40 noms maximum, en incluant les zones d'origine.",
      schema: obj({ zones: { type: 'array', items: { type: 'string' } } }),
      effort: 'low',
      maxTokens: 4000,
    });
    return [...new Set([...cities, ...r.zones.map((z) => z.trim()).filter(Boolean)])].slice(0, 60);
  } catch {
    return cities;
  }
}

export function createAutopilot({ name, queries, cities, resultsPerRun = 20, intervalMinutes = 30, dailyLimit = 100 }) {
  if (!queries.length || !cities.length) throw new Error('Indiquez au moins un métier et une ville.');
  const info = db.prepare(
    `INSERT INTO autopilots (name, queries, cities, results_per_run, interval_minutes, daily_limit, next_run_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(
    name || `${queries[0]} — ${cities[0]}`, JSON.stringify(queries), JSON.stringify(cities),
    clamp(resultsPerRun, 1, 60), clamp(intervalMinutes, 5, 1440), clamp(dailyLimit, 1, 2000), new Date().toISOString()
  );
  return Number(info.lastInsertRowid);
}

/** Minuit (heure de Paris) + 1 minute, en ISO. */
export function nextParisMidnight(from = new Date()) {
  const { hour, minute } = parisNow(from);
  return new Date(from.getTime() + ((23 - hour) * 60 + (60 - minute) + 1) * 60e3).toISOString();
}

function clamp(v, min, max) {
  return Math.min(max, Math.max(min, Math.round(Number(v) || min)));
}

// ---------- 1. Recherches automatiques ----------
async function runOnce(a) {
  const today = parisNow().ymd;
  const leadsToday = a.day === today ? a.leads_today : 0;
  const remaining = a.daily_limit - leadsToday;
  const next = new Date(Date.now() + a.interval_minutes * 60e3).toISOString();

  if (remaining <= 0) {
    db.prepare('UPDATE autopilots SET day = ?, leads_today = ?, next_run_at = ?, last_result = ? WHERE id = ?')
      .run(today, leadsToday, nextParisMidnight(), `Limite du jour atteinte (${a.daily_limit} prospects) : reprise à minuit.`, a.id);
    return;
  }

  const combos = a.queries.flatMap((q) => a.cities.map((c) => [q, c]));
  const [query, city] = combos[a.cursor % combos.length];
  const mission = db.prepare('INSERT INTO missions (query, city, max_results, autopilot_id) VALUES (?, ?, ?, ?)')
    .run(query, city, Math.min(a.results_per_run, remaining), a.id);
  const missionId = Number(mission.lastInsertRowid);
  logMessage({ missionId, from: 'Pilote auto', to: 'Boss', kind: 'info', content: `Programme « ${a.name} » : recherche ${(a.cursor % combos.length) + 1}/${combos.length} (cycle ${a.cycle}) → « ${query} » à ${city}.` });

  const stats = (await runMission(missionId)) || { found: 0, added: 0, accepted: 0 };
  const newCursor = a.cursor + 1;
  const wrapped = newCursor % combos.length === 0;
  db.prepare(`UPDATE autopilots SET cursor = ?, cycle = ?, day = ?, leads_today = ?, total_leads = total_leads + ?, runs = runs + 1,
      last_run_at = ?, next_run_at = ?, last_result = ? WHERE id = ?`).run(
    newCursor, wrapped ? a.cycle + 1 : a.cycle, today, leadsToday + stats.added, stats.added,
    new Date().toISOString(), next,
    `« ${query} » à ${city} : ${stats.found} trouvés, ${stats.added} nouveaux, ${stats.accepted} retenus.`, a.id
  );
  if (wrapped) {
    logMessage({ from: 'Pilote auto', to: 'Vous', kind: 'info', content: `Programme « ${a.name} » : cycle ${a.cycle} terminé (${combos.length} recherches). On recommence pour repérer les nouveaux commerces.` });
  }
}

async function runDueAutopilots() {
  if (missionBusy) return;
  const now = new Date().toISOString();
  const due = db.prepare('SELECT id FROM autopilots WHERE active = 1 AND (next_run_at IS NULL OR next_run_at <= ?) ORDER BY next_run_at LIMIT 1').get(now);
  if (!due) return;
  const a = getAutopilot(due.id);
  missionBusy = a.id;
  runOnce(a)
    .catch((err) => {
      db.prepare('UPDATE autopilots SET next_run_at = ?, last_result = ? WHERE id = ?')
        .run(new Date(Date.now() + 15 * 60e3).toISOString(), `Erreur : ${err.message}`.slice(0, 500), a.id);
      logMessage({ from: 'Pilote auto', to: 'Vous', kind: 'erreur', content: `Programme « ${a.name} » : ${err.message}` });
    })
    .finally(() => { missionBusy = false; });
}

// ---------- 2. Envois étalés ----------
async function flushSendQueue() {
  if (flushing || !canAutoSend().ok) return;
  flushing = true;
  try {
    const { remaining } = canAutoSend();
    const ready = db.prepare("SELECT id FROM leads WHERE status = 'pret_a_envoyer' AND email IS NOT NULL ORDER BY priority DESC, id LIMIT ?").all(remaining);
    for (const { id } of ready) {
      if (!canAutoSend().ok) break;
      try {
        await sendLead(id);
      } catch (err) {
        const l = getLead(id);
        updateLead(id, { status: 'erreur', boss_notes: `Envoi impossible : ${err.message}` });
        logMessage({ missionId: l?.mission_id, leadId: id, from: 'Système', to: 'Vous', kind: 'erreur', content: `Envoi impossible : ${err.message}` });
      }
      // 1 à 3 minutes entre deux emails : un rythme humain, meilleur pour la délivrabilité.
      await sleep(60e3 + Math.random() * 120e3);
    }
  } finally {
    flushing = false;
  }
}

// ---------- 3. Rapport quotidien ----------
export function buildReport() {
  const since = new Date(Date.now() - 24 * 3600e3).toISOString().replace('T', ' ').slice(0, 19);
  const count = (sql, ...args) => db.prepare(sql).get(...args).n;
  const r = {
    nouveaux: count('SELECT COUNT(*) AS n FROM leads WHERE created_at >= ?', since),
    sansSite: count("SELECT COUNT(*) AS n FROM leads WHERE created_at >= ? AND segment = 'sans_site'", since),
    mauvaisSite: count("SELECT COUNT(*) AS n FROM leads WHERE created_at >= ? AND segment = 'mauvais_site'", since),
    sites: count("SELECT COUNT(*) AS n FROM agent_messages WHERE created_at >= ? AND kind = 'validation' AND to_agent = 'Créateur de site'", since),
    prets: count("SELECT COUNT(*) AS n FROM leads WHERE status = 'pret_a_envoyer'"),
    aCompleter: count("SELECT COUNT(*) AS n FROM leads WHERE status = 'email_manquant'"),
    envoyes: count("SELECT COUNT(*) AS n FROM leads WHERE sent_at >= ?", new Date(Date.now() - 24 * 3600e3).toISOString()),
    bloques: count("SELECT COUNT(*) AS n FROM leads WHERE status IN ('bloque','erreur') AND updated_at >= ?", since),
    renvois: count("SELECT COUNT(*) AS n FROM agent_messages WHERE created_at >= ? AND kind = 'rejet'", since),
    programmes: count('SELECT COUNT(*) AS n FROM autopilots WHERE active = 1'),
  };
  r.texte =
    `Rapport des dernières 24 h :\n` +
    `• ${r.nouveaux} nouveaux prospects (${r.sansSite} sans site, ${r.mauvaisSite} avec un mauvais site)\n` +
    `• ${r.sites} sites créés et validés par le Boss (${r.renvois} renvois pour correction)\n` +
    `• ${r.envoyes} emails envoyés · ${r.prets} dossiers prêts à envoyer · ${r.aCompleter} emails à renseigner\n` +
    `• ${r.bloques} dossiers bloqués ou en erreur à regarder\n` +
    `• ${r.programmes} programme(s) du pilote automatique actif(s)`;
  return r;
}

async function maybeDailyReport() {
  if (setting('daily_report') !== 'true') return;
  const now = parisNow();
  if (now.hour < Number(setting('report_hour')) || getSetting('report_day') === now.ymd) return;
  setSetting('report_day', now.ymd);
  const r = buildReport();
  logMessage({ from: 'Boss', to: 'Vous', kind: 'info', content: r.texte });
  const to = getSetting('owner_email') || config.sender.email;
  if (to && smtpConfigured()) {
    try {
      await sendMail({
        to,
        subject: `QG des Agents : ${r.nouveaux} prospects, ${r.sites} sites, ${r.envoyes} emails (24 h)`,
        text: `${r.texte}\n\nTableau de bord : ${config.publicUrl}`,
        html: `<div style="font:15px/1.6 Arial,sans-serif;color:#1d1b18;max-width:560px">${r.texte.replace(/\n/g, '<br>')}<p><a href="${config.publicUrl}" style="color:#b4532a">Ouvrir le tableau de bord →</a></p></div>`,
      });
    } catch (err) {
      logMessage({ from: 'Système', to: 'Vous', kind: 'erreur', content: `Rapport quotidien non envoyé : ${err.message}` });
    }
  }
}

// ---------- Reprise après redémarrage ----------
async function resumeInterrupted() {
  db.prepare("UPDATE missions SET status = 'interrompue', finished_at = datetime('now') WHERE status = 'en_cours'").run();
  const placeholders = TRANSIENT.map(() => '?').join(',');
  const leads = db.prepare(`SELECT id FROM leads WHERE status IN (${placeholders}) ORDER BY priority DESC, id`).all(...TRANSIENT);
  if (!leads.length) return;
  db.prepare(`UPDATE leads SET status = 'en_file' WHERE status IN (${placeholders})`).run(...TRANSIENT);
  logMessage({ from: 'Pilote auto', to: 'Vous', kind: 'info', content: `Redémarrage : ${leads.length} dossier(s) interrompu(s) reprennent automatiquement.` });
  for (const { id } of leads) await processLead(id);
}

// ---------- Boucle principale ----------
async function tick() {
  if (ticking) return;
  ticking = true;
  try {
    await runDueAutopilots();
    flushSendQueue();       // en arrière-plan (peut durer plusieurs minutes)
    await maybeDailyReport();
  } catch (err) {
    console.error('Pilote auto :', err);
  } finally {
    ticking = false;
  }
}

export function startAutopilot() {
  if (timer) return;
  resumeInterrupted().catch((err) => console.error('Reprise :', err));
  timer = setInterval(tick, 60e3);
  setTimeout(tick, 3000);
}

export function autopilotStatus() {
  const active = db.prepare('SELECT COUNT(*) AS n FROM autopilots WHERE active = 1').get().n;
  const next = db.prepare('SELECT MIN(next_run_at) AS t FROM autopilots WHERE active = 1').get().t;
  const send = canAutoSend();
  return {
    active,
    nextRunAt: next,
    searching: Boolean(missionBusy),
    sendsToday: sendsToday(),
    sendLimit: Number(setting('send_limit')),
    sendOk: send.ok,
    sendReason: send.ok ? null : send.reason,
  };
}
