// Agent 0 — Le BOSS : vérifie chaque livrable des sous-agents.
// Il combine des contrôles automatiques stricts (non négociables) et une relecture
// critique par l'IA. S'il refuse, il renvoie un retour précis à l'agent concerné,
// qui doit corriger et relivrer.
import { askJson, aiAvailable, obj } from '../llm.js';
import { config } from '../config.js';

export const name = 'Boss';

const VERDICT = obj({
  approuve: { type: 'boolean' },
  note: { type: 'integer', description: 'Note de qualité sur 10' },
  retour: {
    type: 'string',
    description: "Si refusé : instructions précises et actionnables pour l'agent. Si approuvé : courte remarque.",
  },
});

const BOSS_SYSTEM =
  "Tu es le Boss d'une agence web française qui prospecte des petites entreprises locales. Tu supervises des agents " +
  "IA et tu es exigeant : rien ne part chez un client sans ta validation. Tu approuves uniquement un travail que tu serais " +
  'fier de montrer (note ≥ 8/10). Quand tu refuses, ton retour est concret, listé, actionnable. Tu ne refuses pas pour ' +
  'des détails de goût. Tu réponds en français.';

function verdict(approved, score, feedback) {
  return { approved, score, feedback };
}

async function aiReview(task, deliverable, hardIssues) {
  if (hardIssues.length) {
    return verdict(false, 3, 'Contrôles automatiques échoués :\n- ' + hardIssues.join('\n- '));
  }
  if (!aiAvailable()) return verdict(true, 8, 'Contrôles automatiques validés (mode sans IA).');
  const r = await askJson({
    system: BOSS_SYSTEM,
    prompt: `${task}\n\nLivrable à vérifier :\n${deliverable}`,
    schema: VERDICT,
    effort: 'high',
    maxTokens: 16000,
  });
  const ok = r.approuve && r.note >= 8;
  return verdict(ok, r.note, ok ? r.retour : r.retour || 'Qualité insuffisante, améliore le livrable.');
}

// --- 1. Validation d'un prospect trouvé sur Google Maps -----------------------
export function reviewProspect(p) {
  const issues = [];
  if (p.business_status && p.business_status !== 'OPERATIONAL') issues.push(`établissement non actif (${p.business_status})`);
  if (!p.phone && !p.address) issues.push('ni téléphone ni adresse : impossible à contacter');
  if ((p.reviews_count ?? 0) < 3) issues.push('moins de 3 avis Google : activité trop peu visible');
  if (/(mcdonald|carrefour|leclerc|auchan|intermarch|lidl|franchise|burger king|kfc)/i.test(p.name)) {
    issues.push('grande enseigne / franchise : pas notre cible');
  }
  return issues.length
    ? verdict(false, 2, issues.join(' ; '))
    : verdict(true, 8, p.website ? 'Prospect valide, site à auditer.' : 'Prospect valide, sans site : cible prioritaire.');
}

// --- 2. Validation d'un audit de site ------------------------------------------
export async function reviewAudit(lead, audit) {
  const hard = [];
  if (!audit.problemes?.length && audit.verdict === 'mauvais_site') hard.push('verdict "mauvais site" sans aucun problème listé');
  if (audit.verdict === 'mauvais_site' && audit.tech.score >= 85) {
    hard.push(`verdict "mauvais site" incohérent avec la note technique élevée (${audit.tech.score}/100) : justifie mieux ou change de verdict`);
  }
  if (audit.verdict === 'bon_site' && audit.tech.reachable === false) hard.push('site inaccessible jugé "bon" : incohérent');
  const { excerpt, ...tech } = audit.tech;
  return aiReview(
    `Vérifie l'audit du site de "${lead.name}" (${lead.website}). Le verdict est-il juste et étayé par les mesures ? ` +
      `Les arguments commerciaux sont-ils exacts et respectueux ? Seuil mauvais site : ${config.badSiteThreshold}/100.`,
    JSON.stringify({ ...audit, tech }, null, 2),
    hard
  );
}

// --- 3. Validation d'un site web généré ----------------------------------------
export async function reviewSite(lead, site) {
  const html = site.html || '';
  const hard = [];
  if (html.length < 2500) hard.push('site trop court / incomplet');
  if (!/<meta[^>]+name=["']viewport/i.test(html)) hard.push('meta viewport manquante : le site ne sera pas adapté au mobile');
  if (!/<title>[^<]{5,}<\/title>/i.test(html)) hard.push('balise <title> absente ou vide');
  if (!html.toLowerCase().includes(lead.name.toLowerCase().slice(0, 12))) hard.push("le nom de l'entreprise n'apparaît pas");
  const digits = (lead.phone || '').replace(/\D/g, '');
  if (digits && !html.replace(/\D/g, '').includes(digits.slice(-8))) hard.push('le numéro de téléphone est absent');
  if (site.photos.length && !site.photos.some((p) => html.includes(p.file))) hard.push("aucune photo Google Maps n'est utilisée");
  if (/lorem ipsum|\{\{|\[TODO|XX XX|example\.com/i.test(html)) hard.push('texte de remplissage ou placeholder détecté');
  if (/<script[^>]+src=["']https?:/i.test(html)) hard.push('script externe interdit');

  return aiReview(
    `Vérifie ce site vitrine créé pour "${lead.name}" (${lead.category}). Critères : design professionnel et adapté au ` +
      `métier, responsive, hiérarchie claire, appel à l'action téléphone visible, aucune information inventée (prix, ` +
      `services, faux avis), français impeccable, SEO local (title/description), accessibilité (alt, contrastes). ` +
      `Vraies données : ${JSON.stringify({ phone: lead.phone, address: lead.address, rating: lead.rating, reviews: lead.raw?.reviews })}`,
    html.slice(0, 60000),
    hard
  );
}

// --- 4. Validation de l'email + carte numérique --------------------------------
export async function reviewEmail(lead, email, siteUrl) {
  const hard = [];
  const words = email.body.split(/\s+/).length;
  if (!email.subject || email.subject.length > 90) hard.push('objet absent ou trop long (> 90 caractères)');
  if (words > 260) hard.push(`email trop long (${words} mots, max 260)`);
  if (words < 50) hard.push(`email trop court (${words} mots)`);
  if (!email.body.includes(siteUrl)) hard.push("le lien vers l'aperçu du site est absent du message");
  if (!email.body.toLowerCase().includes(lead.name.toLowerCase().slice(0, 10))) hard.push("le nom de l'entreprise n'est pas cité (pas personnalisé)");
  if (/(gratuit\s*!|urgent|100\s*%|cliquez ici|offre limitée|!!)/i.test(email.subject + email.body)) hard.push('formulation spam détectée');
  if (/\btu\b|\bton\b|\btes\b/i.test(email.body)) hard.push('tutoiement : utiliser le vouvoiement');

  return aiReview(
    `Vérifie cet email de prospection pour "${lead.name}" (${lead.segment === 'sans_site' ? "n'a pas de site" : 'a un site de mauvaise qualité'}). ` +
      `Critères : personnalisé, honnête, respectueux, court, une seule demande claire, aucune affirmation inventée, ` +
      `orthographe parfaite, donne envie de cliquer sur l'aperçu.`,
    `OBJET : ${email.subject}\n\n${email.body}`,
    hard
  );
}
