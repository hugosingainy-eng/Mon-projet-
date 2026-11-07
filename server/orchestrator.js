// Chef d'orchestre : fait travailler les agents dans l'ordre, sous le contrôle du Boss.
//
//  Prospecteur ──► Boss ──► (site ?) ──► Auditeur ──► Boss ──► Créateur de site ──► Boss ──► Rédacteur ──► Boss ──► prêt à envoyer
//                                   └─ pas de site ─────────────────┘
//
// Chaque chef d'équipe (Prospecteur, Auditeur, Créateur de site, Rédacteur) délègue à ses
// propres sous-agents et contrôle leur travail avant de livrer au Boss (voir team.js).
//
// À chaque étape, si le Boss refuse, l'agent reçoit son retour et recommence
// (jusqu'à MAX_REVISIONS). Au-delà, le prospect est marqué "bloqué" pour vous.
import fs from 'node:fs';
import path from 'node:path';
import { sitesDir } from './agents/webbuilder.js';
import { db, logMessage, updateLead, getLead, getSetting } from './db.js';
import { config } from './config.js';
import * as prospector from './agents/prospector.js';
import * as auditor from './agents/auditor.js';
import * as webbuilder from './agents/webbuilder.js';
import * as copywriter from './agents/copywriter.js';
import * as boss from './agents/supervisor.js';
import { sendMail, smtpConfigured } from './services/mailer.js';
import { track } from './team.js';

const running = new Set();

class BlockedError extends Error {}

/** Boucle générique : l'agent livre, le Boss juge, l'agent corrige si besoin. */
async function supervised({ missionId, leadId, agent, produce, review, summarize }) {
  let feedback = '';
  let previous = null;
  for (let attempt = 1; attempt <= config.maxRevisions; attempt++) {
    const deliverable = await track(agent, () => produce(feedback, previous));
    logMessage({
      missionId, leadId, from: agent, to: boss.name, kind: 'livraison',
      content: `Version ${attempt} : ${summarize(deliverable)}`,
    });
    const v = await track(boss.name, () => review(deliverable));
    if (v.approved) {
      logMessage({ missionId, leadId, from: boss.name, to: agent, kind: 'validation', content: `✅ Validé (${v.score}/10). ${v.feedback}` });
      return { deliverable, verdict: v };
    }
    logMessage({ missionId, leadId, from: boss.name, to: agent, kind: 'rejet', content: `❌ Refusé (${v.score}/10) — à corriger :\n${v.feedback}` });
    feedback = v.feedback;
    previous = deliverable;
  }
  throw new BlockedError(`${agent} n'a pas obtenu la validation du Boss après ${config.maxRevisions} essais. Dernier retour : ${feedback}`);
}

/** Traite un prospect de bout en bout (audit → site → email). */
export async function processLead(leadId) {
  let lead = getLead(leadId);
  const missionId = lead.mission_id;
  const ctx = { missionId, leadId };

  try {
    // Étape 2 : audit si le prospect a un site
    if (lead.website && !lead.audit) {
      updateLead(leadId, { status: 'audit_en_cours' });
      const { deliverable: audit } = await supervised({
        ...ctx,
        agent: auditor.name,
        produce: (fb, prev) => auditor.run(lead, fb, prev, ctx),
        review: (a) => boss.reviewAudit(lead, a, ctx),
        summarize: (a) => `verdict ${a.verdict}, note ${a.note_globale}/100 — ${a.problemes.slice(0, 3).join(' ; ') || 'aucun problème majeur'}`,
      });
      const { excerpt, ...tech } = audit.tech;
      const bad = audit.verdict === 'mauvais_site';
      updateLead(leadId, {
        audit: { ...audit, tech },
        audit_score: audit.note_globale,
        email: lead.email || tech.emails?.[0] || null,
        segment: bad ? 'mauvais_site' : 'bon_site',
        status: bad ? 'qualifie' : 'ecarte',
        boss_notes: bad ? 'Site de mauvaise qualité : opportunité.' : 'Site correct : pas une priorité.',
      });
      if (!bad) {
        logMessage({ ...ctx, from: boss.name, to: 'Vous', kind: 'info', content: `${lead.name} a déjà un bon site : prospect écarté.` });
        return;
      }
      lead = getLead(leadId);
    }

    // Étape 3 : création du site
    if (!lead.site_slug) {
      updateLead(leadId, { status: 'site_en_cours' });
      const { deliverable: site } = await supervised({
        ...ctx,
        agent: webbuilder.name,
        produce: (fb, prev) => webbuilder.run(lead, fb, prev, ctx),
        review: (s) => boss.reviewSite(lead, s, ctx),
        summarize: (s) => `site généré (${Math.round(s.html.length / 1024)} Ko, ${s.photos.length} photos) — ${s.notes}`,
      });
      updateLead(leadId, { site_slug: site.slug, status: 'site_valide' });
      lead = getLead(leadId);
    }

    // Étape 4 : email + carte numérique
    const siteUrl = `${config.publicUrl}/sites/${lead.site_slug}/`;
    let heroUrl = '';
    try {
      const photos = JSON.parse(fs.readFileSync(path.join(sitesDir(), lead.site_slug, 'photos.json'), 'utf8'));
      if (photos[0]) heroUrl = `${siteUrl}${photos[0].file}`;
    } catch { /* pas de photo */ }
    updateLead(leadId, { status: 'email_en_cours' });
    const { deliverable: email } = await supervised({
      ...ctx,
      agent: copywriter.name,
      produce: (fb, prev) => copywriter.run(lead, { siteUrl, heroUrl }, fb, prev, ctx),
      review: (e) => boss.reviewEmail(lead, e, siteUrl, ctx),
      summarize: (e) => `objet « ${e.subject} » (${e.body.split(/\s+/).length} mots) + carte numérique`,
    });
    updateLead(leadId, {
      email_subject: email.subject,
      email_body: email.body,
      card_html: email.html,
      status: lead.email ? 'pret_a_envoyer' : 'email_manquant',
    });
    logMessage({
      ...ctx, from: boss.name, to: 'Vous', kind: 'info',
      content: lead.email
        ? `Dossier ${lead.name} complet et validé : prêt à envoyer à ${lead.email}.`
        : `Dossier ${lead.name} validé, mais aucune adresse email trouvée : ajoutez-la pour envoyer.`,
    });

    // Envoi automatique si vous l'avez activé
    if (lead.email && getSetting('auto_send') === 'true' && smtpConfigured()) {
      await sendLead(leadId);
    }
  } catch (err) {
    const blocked = err instanceof BlockedError;
    updateLead(leadId, { status: blocked ? 'bloque' : 'erreur', boss_notes: err.message.slice(0, 1000) });
    logMessage({ ...ctx, from: blocked ? boss.name : 'Système', to: 'Vous', kind: 'erreur', content: err.message });
  }
}

/** Lance une mission complète en arrière-plan. */
export async function runMission(missionId) {
  if (running.has(missionId)) return;
  running.add(missionId);
  const mission = db.prepare('SELECT * FROM missions WHERE id = ?').get(missionId);
  const ctx = { missionId };
  db.prepare("UPDATE missions SET status = 'en_cours' WHERE id = ?").run(missionId);
  logMessage({ ...ctx, from: boss.name, to: prospector.name, kind: 'info', content: `Mission : trouve-moi des « ${mission.query} » à ${mission.city} (max ${mission.max_results}).` });

  try {
    const places = await track(prospector.name, () =>
      prospector.run({ query: mission.query, city: mission.city, maxResults: mission.max_results }, ctx));
    logMessage({ ...ctx, from: prospector.name, to: boss.name, kind: 'livraison', content: `${places.length} établissements trouvés sur Google Maps.` });

    const accepted = [];
    let rejected = 0;
    for (const p of places) {
      if (db.prepare('SELECT 1 FROM leads WHERE place_id = ?').get(p.place_id)) continue; // déjà connu
      const v = boss.reviewProspect(p);
      const info = db.prepare(
        `INSERT INTO leads (mission_id, place_id, name, category, address, phone, website, maps_url, rating, reviews_count, raw, segment, status, boss_notes, priority)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
      ).run(
        missionId, p.place_id, p.name, p.category, p.address, p.phone, p.website, p.maps_url, p.rating, p.reviews_count,
        JSON.stringify(p), p.website ? null : 'sans_site', v.approved ? (p.website ? 'a_auditer' : 'qualifie') : 'rejete', v.feedback, p.priority ?? null
      );
      if (v.approved) accepted.push(Number(info.lastInsertRowid));
      else rejected++;
    }
    logMessage({
      ...ctx, from: boss.name, to: prospector.name, kind: 'validation',
      content: `${accepted.length} prospects retenus, ${rejected} écartés (fermés, injoignables, franchises ou trop peu d'avis).`,
    });

    // 2 prospects traités en parallèle, les plus prioritaires d'abord (classement du Qualificateur)
    const queue = [...accepted];
    await Promise.all(
      Array.from({ length: 2 }, async () => {
        while (queue.length) await processLead(queue.shift());
      })
    );

    db.prepare("UPDATE missions SET status = 'terminee', finished_at = datetime('now') WHERE id = ?").run(missionId);
    logMessage({ ...ctx, from: boss.name, to: 'Vous', kind: 'info', content: `Mission « ${mission.query} — ${mission.city} » terminée.` });
  } catch (err) {
    db.prepare("UPDATE missions SET status = 'erreur', finished_at = datetime('now') WHERE id = ?").run(missionId);
    logMessage({ ...ctx, from: 'Système', to: 'Vous', kind: 'erreur', content: err.message });
  } finally {
    running.delete(missionId);
  }
}

/** Envoie l'email d'un prospect validé par le Boss. */
export async function sendLead(leadId) {
  const lead = getLead(leadId);
  if (!lead.email) throw new Error('Aucune adresse email pour ce prospect.');
  if (!lead.card_html) throw new Error("Ce dossier n'a pas encore été validé par le Boss.");
  await sendMail({ to: lead.email, subject: lead.email_subject, html: lead.card_html, text: lead.email_body });
  updateLead(leadId, { status: 'envoye', sent_at: new Date().toISOString() });
  logMessage({ missionId: lead.mission_id, leadId, from: 'Système', to: 'Vous', kind: 'info', content: `Email envoyé à ${lead.name} (${lead.email}).` });
}

export function isRunning(missionId) {
  return running.has(missionId);
}
