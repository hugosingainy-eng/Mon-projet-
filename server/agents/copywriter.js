// Agent 3 — Rédacteur : prépare l'email de prospection + la carte numérique.
import { config } from '../config.js';
import { askJson, aiAvailable, obj } from '../llm.js';

export const name = 'Rédacteur';

const esc = (s = '') => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const SCHEMA = obj({
  objet: { type: 'string', description: "Objet de l'email, court, personnalisé, sans majuscules agressives" },
  message: { type: 'string', description: "Corps de l'email en texte brut, paragraphes séparés par une ligne vide" },
  accroche_carte: { type: 'string', description: 'Titre court de la carte numérique (max 8 mots)' },
  points_carte: { type: 'array', items: { type: 'string' }, description: '3 bénéfices concrets, max 8 mots chacun' },
});

/**
 * Carte numérique compatible email (tableaux + styles inline : Gmail/Outlook).
 * Montre l'aperçu du nouveau site et vos coordonnées.
 */
export function buildCard({ lead, siteUrl, heroUrl, accroche, points }) {
  const s = config.sender;
  const li = points.map((p) => `<tr><td style="padding:4px 0;font:15px/1.4 Arial,sans-serif;color:#2b2722">✓&nbsp; ${esc(p)}</td></tr>`).join('');
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:24px auto;border-collapse:collapse;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #e8e2d8">
<tr><td>${heroUrl ? `<a href="${esc(siteUrl)}"><img src="${esc(heroUrl)}" width="560" alt="Aperçu du site ${esc(lead.name)}" style="display:block;width:100%;height:auto;border:0"></a>` : ''}</td></tr>
<tr><td style="padding:24px 28px 8px">
<div style="font:600 12px Arial,sans-serif;letter-spacing:1.5px;text-transform:uppercase;color:#b4532a">Aperçu offert · ${esc(lead.name)}</div>
<div style="font:700 22px/1.25 Georgia,serif;color:#1d1b18;margin-top:6px">${esc(accroche)}</div></td></tr>
<tr><td style="padding:8px 28px"><table role="presentation" cellpadding="0" cellspacing="0">${li}</table></td></tr>
<tr><td style="padding:16px 28px 24px"><a href="${esc(siteUrl)}" style="display:inline-block;background:#b4532a;color:#ffffff;text-decoration:none;font:600 15px Arial,sans-serif;padding:13px 24px;border-radius:999px">Voir mon futur site →</a></td></tr>
<tr><td style="padding:18px 28px;background:#f6f2ec;font:13px/1.5 Arial,sans-serif;color:#5d564d">
<strong style="color:#1d1b18">${esc(s.name)}</strong> · ${esc(s.company)}<br>
${s.phone ? `${esc(s.phone)} · ` : ''}${s.email ? `<a href="mailto:${esc(s.email)}" style="color:#b4532a">${esc(s.email)}</a>` : ''}${s.website ? ` · <a href="${esc(s.website)}" style="color:#b4532a">${esc(s.website.replace(/^https?:\/\//, ''))}</a>` : ''}
</td></tr></table>`;
}

export function buildEmailHtml({ message, card }) {
  const paras = message.split(/\n{2,}/).map((p) => `<p style="margin:0 0 14px">${esc(p).replace(/\n/g, '<br>')}</p>`).join('');
  return `<!doctype html><html lang="fr"><body style="margin:0;padding:20px;background:#f4f1ec">
<div style="max-width:560px;margin:0 auto;font:15px/1.6 Arial,sans-serif;color:#2b2722">${paras}</div>
${card}
<p style="max-width:560px;margin:12px auto;font:11px/1.5 Arial,sans-serif;color:#8a8279">Vous recevez ce message car votre établissement est référencé publiquement sur Google Maps. Pour ne plus être contacté, répondez simplement « STOP ».</p>
</body></html>`;
}

export async function run(lead, { siteUrl, heroUrl }, feedback = '') {
  const s = config.sender;
  const audit = lead.audit || null;
  const context = lead.segment === 'mauvais_site'
    ? `L'entreprise a déjà un site (${lead.website}) mais il a des faiblesses : ${(audit?.problemes || []).slice(0, 4).join(' ; ')}. Arguments : ${(audit?.arguments_commerciaux || []).join(' ; ')}`
    : "L'entreprise n'a PAS de site internet : ses clients ne la trouvent que via Google Maps.";

  let out;
  if (!aiAvailable()) {
    out = {
      objet: `${lead.name} : j'ai préparé votre site internet`,
      message:
        `Bonjour,\n\nEn cherchant « ${lead.category.toLowerCase()} » sur Google Maps, je suis tombé sur ${lead.name}` +
        `${lead.rating ? ` et vos ${lead.reviews_count} avis (${lead.rating}/5) parlent d'eux-mêmes` : ''}.\n\n` +
        (lead.segment === 'mauvais_site'
          ? "Votre site actuel ne vous rend pas justice, surtout sur mobile, là où vos clients vous cherchent.\n\n"
          : "Vous n'avez pas encore de site internet : beaucoup de clients potentiels passent donc à côté de vous.\n\n") +
        `J'ai pris l'initiative de vous préparer un aperçu, réalisé avec vos photos et vos avis Google. Il est visible ici : ${siteUrl}\n\n` +
        `${s.offer}. Si l'aperçu vous plaît, je peux vous appeler 10 minutes cette semaine pour en parler ?\n\n` +
        `Bien à vous,\n${s.name}\n${s.company}${s.phone ? `\n${s.phone}` : ''}`,
      accroche_carte: 'Votre site est prêt à être mis en ligne',
      points_carte: ['Réalisé avec vos photos Google', 'Parfait sur mobile', 'Vos avis clients mis en avant'],
    };
  } else {
    out = await askJson({
      system:
        "Tu es le Rédacteur d'une agence web française. Tu écris des emails de prospection B2B courts (120-180 mots), " +
        "sincères, personnalisés et non agressifs, au vouvoiement. Pas de promesses chiffrées inventées, pas de jargon, pas de " +
        'mots qui déclenchent les filtres anti-spam (gratuit!!!, urgent, 100%…). Un seul appel à l’action simple. ' +
        "L'email doit contenir le lien vers l'aperçu du site et la signature de l'expéditeur.",
      prompt:
        `Prospect : ${lead.name} (${lead.category}), ${lead.address}. Note Google : ${lead.rating ?? 'n/a'} (${lead.reviews_count} avis).\n` +
        `Situation : ${context}\n` +
        `Lien de l'aperçu du site que nous avons créé pour eux : ${siteUrl}\n` +
        `Expéditeur : ${s.name}, ${s.company}${s.phone ? `, ${s.phone}` : ''}. Offre : ${s.offer}.` +
        (feedback ? `\n\nLe Boss a REFUSÉ ta version précédente. Corrige :\n${feedback}` : ''),
      schema: SCHEMA,
      effort: 'medium',
      maxTokens: 8000,
    });
  }

  const card = buildCard({ lead, siteUrl, heroUrl, accroche: out.accroche_carte, points: out.points_carte });
  return {
    subject: out.objet,
    body: out.message,
    card,
    html: buildEmailHtml({ message: out.message, card }),
  };
}
