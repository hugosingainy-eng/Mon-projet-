// Agent 2 — Auditeur (chef d'équipe) : analyse les sites existants pour repérer les mauvais sites.
// Sous-agents : 🛠️ Technicien, 📈 Analyste SEO, 🕵️ Enquêteur contact.
import { technicalAudit, seoAudit, findContactEmails, combineScore } from '../services/siteAudit.js';
import { askJson, aiAvailable, obj } from '../llm.js';
import { config } from '../config.js';
import { delegate, track } from '../team.js';

export const name = 'Auditeur';

const SCHEMA = obj({
  verdict: { type: 'string', enum: ['mauvais_site', 'bon_site'] },
  note_globale: { type: 'integer', description: 'Qualité du site sur 100 (100 = excellent)' },
  problemes: { type: 'array', items: { type: 'string' }, description: 'Problèmes concrets constatés' },
  arguments_commerciaux: {
    type: 'array', items: { type: 'string' },
    description: 'Arguments pour convaincre le gérant de refaire son site, formulés avec tact',
  },
  justification: { type: 'string' },
});

/** Les sous-agents collectent les mesures (une seule fois, même si le Boss demande une révision). */
async function collect(lead, ctx) {
  const tech = await delegate({
    ctx, chef: name, helper: 'Technicien',
    task: `Contrôle technique de ${lead.website} : accès, HTTPS, mobile, vitesse.`,
    run: () => technicalAudit(lead.website),
    summary: (t) => t.reachable
      ? `${t.checks.filter((c) => !c.ok).length} point(s) technique(s) en échec, chargement ${t.loadMs} ms.`
      : `Site inaccessible (${t.error || 'HTTP ' + t.status}).`,
  });

  const [seo, contact] = await Promise.all([
    delegate({
      ctx, chef: name, helper: 'Analyste SEO',
      task: 'Analyse le référencement : balises, données structurées, PageSpeed.',
      run: () => seoAudit(tech),
      summary: (s) => `${s.checks.filter((c) => !c.ok).length} point(s) SEO en échec${s.pageSpeed ? `, PageSpeed perf ${s.pageSpeed.performance}/100` : ''}.`,
    }),
    delegate({
      ctx, chef: name, helper: 'Enquêteur contact',
      task: 'Trouve une adresse email de contact sur le site.',
      run: () => findContactEmails(tech),
      summary: (c) => (c.emails.length ? `Email trouvé : ${c.emails[0]}` : `Aucun email trouvé${c.visited.length ? ` (pages fouillées : ${c.visited.join(', ')})` : ''}.`),
    }),
  ]);

  const { checks, score } = combineScore(tech, seo);
  const { html, ...techRest } = tech;
  return {
    ...techRest,
    title: seo.title,
    description: seo.description,
    pageSpeed: seo.pageSpeed,
    checks,
    score,
    emails: contact.emails,
    excerpt: html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, '').slice(0, 6000),
  };
}

export async function run(lead, feedback = '', previous = null, ctx = null) {
  const tech = previous?.tech || (await collect(lead, ctx));

  // Le chef rend son verdict à partir des rapports de son équipe.
  return track(name, async () => {
    if (!aiAvailable()) {
      const failed = tech.checks.filter((c) => !c.ok);
      return {
        tech,
        verdict: tech.score < config.badSiteThreshold ? 'mauvais_site' : 'bon_site',
        note_globale: tech.score,
        problemes: failed.map((c) => `${c.label}${c.detail ? ` (${c.detail})` : ''}`),
        arguments_commerciaux: failed.slice(0, 3).map((c) => `Améliorer : ${c.label.toLowerCase()}`),
        justification: `Note technique ${tech.score}/100 (seuil ${config.badSiteThreshold}).`,
      };
    }

    const { excerpt, ...techSummary } = tech;
    const ai = await askJson({
      system:
        "Tu es l'Auditeur, chef d'équipe d'une agence web française. Ton Technicien, ton Analyste SEO et ton Enquêteur " +
        "contact t'ont remis leurs rapports. Tu tranches : le site de cette petite entreprise mérite-t-il d'être refait " +
        "(design daté, pas mobile, lent, pas sécurisé, peu de contenu, pas d'appel à l'action) ? Sois honnête : si le site est correct, dis-le.",
      prompt:
        `Entreprise : ${lead.name} (${lead.category}) — ${lead.address}\nSite : ${lead.website}\n\n` +
        `Rapports de l'équipe :\n${JSON.stringify(techSummary, null, 2)}\n\nExtrait du HTML :\n${excerpt}\n\n` +
        `Seuil "mauvais site" de l'agence : note < ${config.badSiteThreshold}/100.` +
        (feedback ? `\n\nRetour du Boss sur ta version précédente (corrige ces points) :\n${feedback}` : ''),
      schema: SCHEMA,
      effort: 'medium',
      maxTokens: 16000,
    });
    return { tech, ...ai };
  });
}
