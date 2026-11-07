// Programmes de recherche : les agents ne cherchent QUE quand vous le demandez.
//
// Un programme = une liste de métiers × une liste de villes, enregistrée une fois.
// Quand vous cliquez « Chercher des clients », les agents passent toutes les
// combinaisons une par une, puis S'ARRÊTENT. Rien ne se lance tout seul.
//
// En tâche de fond, chaque minute, le serveur :
//  1. poursuit les recherches que vous avez lancées (une combinaison à la fois) ;
//  2. envoie les dossiers prêts, seulement si vous avez activé l'envoi automatique ;
//  3. vous envoie le rapport du jour, si vous l'avez activé.
// Au redémarrage, les recherches et dossiers en cours reprennent là où ils en étaient.
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
      done: Math.min(a.cursor, combos),         // combinaisons faites pendant ce lancement
      found: a.leads_today,                      // nouveaux prospects de ce lancement
      max: a.daily_limit,                        // plafond de nouveaux prospects par lancement
      searching: a.active === 1,
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

export function createAutopilot({ name, queries, cities, resultsPerRun = 20, maxProspects = 100, launch = false }) {
  if (!queries.length || !cities.length) throw new Error('Indiquez au moins un métier et une ville.');
  const info = db.prepare(
    `INSERT INTO autopilots (name, queries, cities, results_per_run, daily_limit, active)
     VALUES (?, ?, ?, ?, ?, 0)`
  ).run(name || `${queries[0]} — ${cities[0]}`, JSON.stringify(queries), JSON.stringify(cities),
    clamp(resultsPerRun, 1, 60), clamp(maxProspects, 1, 2000));
  const id = Number(info.lastInsertRowid);
  if (launch) launchProgram(id);
  return id;
}

/** « Chercher des clients » : lance un passage complet sur toutes les combinaisons. */
export function launchProgram(id) {
  const a = getAutopilot(id);
  if (!a) throw new Error('Programme introuvable.');
  if (a.active) return;
  db.prepare('UPDATE autopilots SET active = 1, cursor = 0, leads_today = 0, runs = runs + 1, last_result = ? WHERE id = ?')
    .run('Recherche lancée…', id);
  logMessage({ from: 'Vous', to: 'Boss', kind: 'info', content: `Cherche-moi des clients : programme « ${a.name} » (${a.queries.length * a.cities.length} recherches à faire).` });
  setTimeout(tick, 500);
}

/** Arrête une recherche en cours (la combinaison en cours se termine proprement). */
export function stopProgram(id) {
  const a = getAutopilot(id);
  if (!a?.active) return;
  db.prepare('UPDATE autopilots SET active = 0, last_result = ? WHERE id = ?')
    .run(`Arrêtée par vous après ${a.cursor} recherche(s), ${a.leads_today} nouveaux prospects.`, id);
  logMessage({ from: 'Vous', to: 'Boss', kind: 'info', content: `Stop : arrête la recherche « ${a.name} ».` });
}

function clamp(v, min, max) {
  return Math.min(max, Math.max(min, Math.round(Number(v) || min)));
}

// ---------- 1. Recherches lancées par vous ----------
function finish(a, reason) {
  db.prepare('UPDATE autopilots SET active = 0, last_run_at = ?, last_result = ? WHERE id = ?').run(new Date().toISOString(), reason, a.id);
  logMessage({ from: 'Boss', to: 'Vous', kind: 'info', content: `Programme « ${a.name} » terminé : ${reason} Les agents attendent votre prochaine demande.` });
}

async function runNext(a) {
  const combos = a.queries.flatMap((q) => a.cities.map((c) => [q, c]));
  if (a.cursor >= combos.length) return finish(a, `${combos.length} recherche(s) faite(s), ${a.leads_today} nouveaux prospects.`);
  const remaining = a.daily_limit - a.leads_today;
  if (remaining <= 0) return finish(a, `plafond de ${a.daily_limit} nouveaux prospects atteint.`);

  const [query, city] = combos[a.cursor];
  const mission = db.prepare('INSERT INTO missions (query, city, max_results, autopilot_id) VALUES (?, ?, ?, ?)')
    .run(query, city, Math.min(a.results_per_run, remaining), a.id);
  const missionId = Number(mission.lastInsertRowid);
  logMessage({ missionId, from: 'Boss', to: 'Prospecteur', kind: 'info', content: `Programme « ${a.name} » : recherche ${a.cursor + 1}/${combos.length} → « ${query} » à ${city}.` });

  const stats = (await runMission(missionId)) || { found: 0, added: 0, accepted: 0 };
  db.prepare(`UPDATE autopilots SET cursor = cursor + 1, leads_today = leads_today + ?, total_leads = total_leads + ?,
      last_run_at = ?, last_result = ? WHERE id = ?`).run(
    stats.added, stats.added, new Date().toISOString(),
    `« ${query} » à ${city} : ${stats.found} trouvés, ${stats.added} nouveaux, ${stats.accepted} retenus.`, a.id
  );
  const after = getAutopilot(a.id);
  if (after?.active && (after.cursor >= combos.length || after.leads_today >= after.daily_limit)) {
    finish(after, after.cursor >= combos.length
      ? `${combos.length} recherche(s) faite(s), ${after.leads_today} nouveaux prospects.`
      : `plafond de ${after.daily_limit} nouveaux prospects atteint.`);
  }
}

async function runRequestedSearches() {
  if (missionBusy) return;
  const next = db.prepare('SELECT id FROM autopilots WHERE active = 1 ORDER BY last_run_at IS NOT NULL, last_run_at LIMIT 1').get();
  if (!next) return;   // personne n'a rien demandé : les agents ne cherchent pas
  const a = getAutopilot(next.id);
  missionBusy = a.id;
  runNext(a)
    .catch((err) => {
      db.prepare('UPDATE autopilots SET active = 0, last_result = ? WHERE id = ?').run(`Erreur : ${err.message}`.slice(0, 500), a.id);
      logMessage({ from: 'Système', to: 'Vous', kind: 'erreur', content: `Programme « ${a.name} » arrêté : ${err.message}` });
    })
    .finally(() => {
      missionBusy = false;
      setTimeout(tick, 500); // enchaîne la combinaison suivante sans attendre la minute
    });
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
    `• ${r.programmes} recherche(s) en cours`;
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
  logMessage({ from: 'Système', to: 'Vous', kind: 'info', content: `Redémarrage : ${leads.length} dossier(s) interrompu(s) reprennent automatiquement.` });
  for (const { id } of leads) await processLead(id);
}

// ---------- Boucle principale ----------
async function tick() {
  if (ticking) return;
  ticking = true;
  try {
    await runRequestedSearches();
    flushSendQueue();       // en arrière-plan (peut durer plusieurs minutes)
    await maybeDailyReport();
  } catch (err) {
    console.error('Tâches de fond :', err);
  } finally {
    ticking = false;
  }
}

export function startAutopilot() {
  if (timer) return;
  // Ancienne version « 24h/24 » : plus aucun programme ne tourne sans votre demande.
  if (getSetting('programs_manual') !== 'true') {
    db.prepare('UPDATE autopilots SET active = 0').run();
    setSetting('programs_manual', 'true');
  }
  resumeInterrupted().catch((err) => console.error('Reprise :', err));
  timer = setInterval(tick, 60e3);
  setTimeout(tick, 3000);
}

export function autopilotStatus() {
  const running = db.prepare('SELECT name FROM autopilots WHERE active = 1').all().map((r) => r.name);
  const send = canAutoSend();
  return {
    searching: running,
    sendsToday: sendsToday(),
    sendLimit: Number(setting('send_limit')),
    autoSend: getSetting('auto_send') === 'true',
    sendOk: send.ok,
    sendReason: send.ok ? null : send.reason,
  };
}
