// Serveur web : tableau de bord privé + API + hébergement des sites d'aperçu.
import express from 'express';
import cookieParser from 'cookie-parser';
import crypto from 'node:crypto';
import path from 'node:path';
import fs from 'node:fs';
import { config, demoMode } from './config.js';
import { db, getLead, updateLead, getSetting, setSetting, logMessage } from './db.js';
import { runMission, processLead, sendLead, isRunning } from './orchestrator.js';
import * as prospector from './agents/prospector.js';
import * as boss from './agents/supervisor.js';
import { smtpConfigured } from './services/mailer.js';
import { sitesDir } from './agents/webbuilder.js';
import { TEAM, activity } from './team.js';
import { serperAvailable } from './services/webResearch.js';

// ---------- Accès privé : un seul utilisateur (vous) ----------
if (!config.adminPassword) {
  config.adminPassword = crypto.randomBytes(9).toString('base64url');
  console.warn(`\n⚠️  ADMIN_PASSWORD non défini. Mot de passe temporaire : ${config.adminPassword}\n   Définissez-le dans .env.\n`);
}
const SESSION_DAYS = 30;

function sign(value) {
  return crypto.createHmac('sha256', config.sessionSecret).update(value).digest('base64url');
}
function makeToken() {
  const exp = String(Date.now() + SESSION_DAYS * 864e5);
  return `${exp}.${sign(exp)}`;
}
function validToken(token = '') {
  const [exp, sig] = token.split('.');
  if (!exp || !sig) return false;
  const expected = sign(exp);
  return sig.length === expected.length &&
    crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected)) && Number(exp) > Date.now();
}
function safeEqual(a, b) {
  const ha = crypto.createHash('sha256').update(a).digest();
  const hb = crypto.createHash('sha256').update(b).digest();
  return crypto.timingSafeEqual(ha, hb);
}

// Après un redémarrage, les travaux interrompus sont signalés pour être relancés.
db.prepare(`UPDATE leads SET status = 'erreur', boss_notes = 'Traitement interrompu par un redémarrage du serveur : cliquez sur Relancer.'
  WHERE status IN ('audit_en_cours','site_en_cours','email_en_cours','en_file','a_auditer','qualifie','site_valide','verif_site','recherche_email')`).run();
db.prepare("UPDATE missions SET status = 'erreur' WHERE status = 'en_cours'").run();

const loginAttempts = new Map();

const app = express();
app.disable('x-powered-by');
app.set('trust proxy', 1);
app.use(express.json({ limit: '2mb' }));
app.use(cookieParser());

// Sites d'aperçu : publics (le prospect doit pouvoir les ouvrir), mais non indexés.
app.use('/sites', (req, res, next) => {
  res.setHeader('X-Robots-Tag', 'noindex, nofollow');
  next();
}, express.static(sitesDir(), { extensions: ['html'], dotfiles: 'deny', index: 'index.html' }));

app.use(express.static(path.join(config.root, 'public')));

app.post('/api/login', (req, res) => {
  const ip = req.ip;
  const a = loginAttempts.get(ip) || { n: 0, until: 0 };
  if (a.until > Date.now()) return res.status(429).json({ error: 'Trop de tentatives, réessayez dans 15 minutes.' });
  if (!safeEqual(String(req.body?.password || ''), config.adminPassword)) {
    a.n += 1;
    if (a.n >= 5) { a.until = Date.now() + 15 * 60e3; a.n = 0; }
    loginAttempts.set(ip, a);
    return res.status(401).json({ error: 'Mot de passe incorrect.' });
  }
  loginAttempts.delete(ip);
  res.cookie('session', makeToken(), {
    httpOnly: true, sameSite: 'strict', secure: config.publicUrl.startsWith('https'), maxAge: SESSION_DAYS * 864e5,
  });
  res.json({ ok: true });
});

app.post('/api/logout', (req, res) => {
  res.clearCookie('session');
  res.json({ ok: true });
});

// Tout le reste de l'API exige d'être connecté.
app.use('/api', (req, res, next) => {
  if (validToken(req.cookies.session)) return next();
  res.status(401).json({ error: 'Non connecté.' });
});

const wrap = (fn) => (req, res) => Promise.resolve().then(() => fn(req, res)).catch((e) => res.status(400).json({ error: e.message }));

// ---------- État & réglages ----------
app.get('/api/status', (req, res) => {
  res.json({
    demoGoogle: demoMode.google,
    demoAi: demoMode.ai,
    smtp: smtpConfigured(),
    googleSearch: serperAvailable(),
    autoSend: getSetting('auto_send') === 'true',
    model: config.model,
    sender: config.sender,
    maxRevisions: config.maxRevisions,
  });
});

app.post('/api/settings', (req, res) => {
  if ('autoSend' in req.body) setSetting('auto_send', req.body.autoSend ? 'true' : 'false');
  res.json({ ok: true });
});

// Organigramme + qui travaille en ce moment.
app.get('/api/team', (req, res) => {
  res.json({ team: TEAM, active: activity() });
});

app.get('/api/stats', (req, res) => {
  const rows = db.prepare('SELECT status, COUNT(*) AS n FROM leads GROUP BY status').all();
  const by = Object.fromEntries(rows.map((r) => [r.status, r.n]));
  const seg = Object.fromEntries(
    db.prepare("SELECT segment, COUNT(*) AS n FROM leads WHERE status != 'rejete' GROUP BY segment").all().map((r) => [r.segment, r.n])
  );
  const rejets = db.prepare("SELECT COUNT(*) AS n FROM agent_messages WHERE kind = 'rejet'").get().n;
  const corrections = db.prepare("SELECT COUNT(*) AS n FROM agent_messages WHERE kind = 'correction'").get().n;
  const validations = db.prepare("SELECT COUNT(*) AS n FROM agent_messages WHERE kind = 'validation'").get().n;
  res.json({ byStatus: by, bySegment: seg, total: rows.reduce((s, r) => s + r.n, 0), rejets, corrections, validations });
});

// ---------- Missions ----------
app.get('/api/missions', (req, res) => {
  const missions = db.prepare(`
    SELECT m.*, (SELECT COUNT(*) FROM leads l WHERE l.mission_id = m.id) AS leads,
      (SELECT COUNT(*) FROM leads l WHERE l.mission_id = m.id AND l.status IN ('pret_a_envoyer','email_manquant','envoye')) AS ready
    FROM missions m ORDER BY m.id DESC`).all();
  res.json(missions.map((m) => ({ ...m, running: isRunning(m.id) })));
});

app.post('/api/missions', wrap((req, res) => {
  const query = String(req.body.query || '').trim();
  const city = String(req.body.city || '').trim();
  const max = Math.min(60, Math.max(1, Number(req.body.maxResults) || 20));
  if (!query || !city) throw new Error('Indiquez une activité et une ville.');
  const info = db.prepare('INSERT INTO missions (query, city, max_results) VALUES (?, ?, ?)').run(query, city, max);
  const id = Number(info.lastInsertRowid);
  runMission(id); // en arrière-plan
  res.json({ id });
}));

app.delete('/api/missions/:id', wrap((req, res) => {
  db.prepare('DELETE FROM agent_messages WHERE mission_id = ?').run(req.params.id);
  db.prepare('DELETE FROM missions WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
}));

// ---------- Prospects ----------
app.get('/api/leads', (req, res) => {
  const where = [];
  const args = [];
  if (req.query.status) { where.push('status = ?'); args.push(req.query.status); }
  if (req.query.mission) { where.push('mission_id = ?'); args.push(req.query.mission); }
  if (req.query.q) { where.push('(name LIKE ? OR address LIKE ?)'); args.push(`%${req.query.q}%`, `%${req.query.q}%`); }
  const sql = `SELECT id, mission_id, name, category, address, phone, email, website, rating, reviews_count, segment,
    audit_score, priority, site_slug, status, boss_notes, sent_at, updated_at FROM leads
    ${where.length ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY updated_at DESC LIMIT 500`;
  res.json(db.prepare(sql).all(...args));
});

app.get('/api/leads/:id', wrap((req, res) => {
  const lead = getLead(req.params.id);
  if (!lead) throw new Error('Prospect introuvable.');
  const messages = db.prepare('SELECT * FROM agent_messages WHERE lead_id = ? ORDER BY id').all(lead.id);
  res.json({ ...lead, messages, siteUrl: lead.site_slug ? `/sites/${lead.site_slug}/` : null });
}));

app.get('/api/leads/:id/email', wrap((req, res) => {
  const lead = getLead(req.params.id);
  if (!lead?.card_html) throw new Error('Email pas encore prêt.');
  res.type('html').send(lead.card_html);
}));

app.patch('/api/leads/:id', wrap((req, res) => {
  const lead = getLead(req.params.id);
  if (!lead) throw new Error('Prospect introuvable.');
  const fields = {};
  if ('email' in req.body) {
    const email = String(req.body.email || '').trim();
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('Adresse email invalide.');
    fields.email = email || null;
    if (lead.status === 'email_manquant' && email) fields.status = 'pret_a_envoyer';
  }
  updateLead(lead.id, fields);
  res.json({ ok: true });
}));

app.post('/api/leads/:id/send', wrap(async (req, res) => {
  await sendLead(Number(req.params.id));
  res.json({ ok: true });
}));

// Relancer le circuit (après un blocage, une erreur, ou pour refaire une étape).
app.post('/api/leads/:id/retry', wrap((req, res) => {
  const lead = getLead(req.params.id);
  if (!lead) throw new Error('Prospect introuvable.');
  const redo = req.body?.redo; // 'site' | 'email' | undefined
  const fields = { status: 'en_file' };
  if (redo === 'site') {
    fields.site_slug = null;
    if (lead.site_slug) fs.rmSync(path.join(sitesDir(), lead.site_slug, 'index.html'), { force: true });
  }
  if (lead.status === 'rejete' || lead.status === 'ecarte') {
    logMessage({ missionId: lead.mission_id, leadId: lead.id, from: 'Vous', to: 'Boss', kind: 'info', content: 'Prospect repêché manuellement : traite-le quand même.' });
    if (lead.status === 'ecarte') fields.segment = 'mauvais_site';
    else if (!lead.website) fields.segment = 'sans_site';
  }
  updateLead(lead.id, fields);
  // Un prospect repêché avec un "bon" site saute l'audit.
  processLead(lead.id);
  res.json({ ok: true });
}));

// Relancer la recherche d'email sur le web pour un prospect.
app.post('/api/leads/:id/find-email', wrap((req, res) => {
  const lead = getLead(req.params.id);
  if (!lead) throw new Error('Prospect introuvable.');
  if (['recherche_email', 'site_en_cours', 'email_en_cours', 'verif_site', 'audit_en_cours'].includes(lead.status)) {
    throw new Error('Les agents travaillent déjà sur ce dossier.');
  }
  const previous = lead.status;
  updateLead(lead.id, { status: 'recherche_email' });
  const ctx = { missionId: lead.mission_id, leadId: lead.id };
  (async () => {
    try {
      const r = await prospector.findContact(lead, '', null, ctx);
      const v = boss.reviewContact(lead, r);
      logMessage({ ...ctx, from: boss.name, to: prospector.name, kind: v.approved ? 'validation' : 'rejet', content: `${v.approved ? '✅' : '❌'} ${v.feedback}` });
      const email = v.approved ? r.email : null;
      updateLead(lead.id, {
        email: email || lead.email,
        email_info: { source: r.source, score: r.score, engine: r.engine, extract: r.extract, alternatives: r.alternatives, found: Boolean(email) },
        status: email && previous === 'email_manquant' ? 'pret_a_envoyer' : previous,
      });
    } catch (err) {
      updateLead(lead.id, { status: previous });
      logMessage({ ...ctx, from: 'Système', to: 'Vous', kind: 'erreur', content: err.message });
    }
  })();
  res.json({ ok: true });
}));

app.delete('/api/leads/:id', wrap((req, res) => {
  db.prepare('DELETE FROM agent_messages WHERE lead_id = ?').run(req.params.id);
  db.prepare('DELETE FROM leads WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
}));

// ---------- Fil des agents ----------
app.get('/api/messages', (req, res) => {
  const since = Number(req.query.since) || 0;
  const rows = db.prepare(`
    SELECT m.*, l.name AS lead_name FROM agent_messages m LEFT JOIN leads l ON l.id = m.lead_id
    WHERE m.id > ? ORDER BY m.id DESC LIMIT 200`).all(since);
  res.json(rows.reverse());
});

// Erreurs inattendues : réponse JSON, sans détails internes.
app.use((err, req, res, next) => {
  console.error(err);
  res.status(err.status || 500).json({ error: err.expose ? err.message : 'Erreur serveur.' });
});

app.listen(config.port, () => {
  console.log(`\n🚀 Agence IA démarrée sur ${config.publicUrl}`);
  console.log(`   Google Maps : ${demoMode.google ? 'MODE DÉMO (pas de clé)' : 'réel'}`);
  console.log(`   IA Claude   : ${demoMode.ai ? 'MODE SANS IA (pas de clé)' : config.model}`);
  console.log(`   SMTP        : ${smtpConfigured() ? 'configuré' : 'non configuré (envoi désactivé)'}\n`);
});
