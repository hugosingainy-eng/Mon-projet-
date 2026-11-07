// Agent 2 — Auditeur : analyse les sites existants pour repérer les mauvais sites.
import { auditWebsite } from '../services/siteAudit.js';
import { askJson, aiAvailable, obj } from '../llm.js';
import { config } from '../config.js';

export const name = 'Auditeur';

const SCHEMA = obj({
  verdict: { type: 'string', enum: ['mauvais_site', 'bon_site'] },
  note_globale: { type: 'integer', description: 'Qualité du site sur 100 (100 = excellent)' },
  problemes: { type: 'array', items: { type: 'string' }, description: 'Problèmes concrets constatés' },
  arguments_commerciaux: {
    type: 'array', items: { type: 'string' },
    description: "Arguments pour convaincre le gérant de refaire son site, formulés avec tact",
  },
  justification: { type: 'string' },
});

export async function run(lead, feedback = '') {
  const tech = await auditWebsite(lead.website);

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
      "Tu es l'Auditeur d'une agence web française. Tu évalues objectivement le site d'une petite entreprise " +
      "pour savoir s'il mérite d'être refait (design daté, pas mobile, lent, pas sécurisé, peu de contenu, pas d'appel à l'action). " +
      'Sois honnête : si le site est correct, dis-le.',
    prompt:
      `Entreprise : ${lead.name} (${lead.category}) — ${lead.address}\n` +
      `Site : ${lead.website}\n\nMesures techniques :\n${JSON.stringify(techSummary, null, 2)}\n\n` +
      `Extrait du HTML :\n${excerpt}\n\n` +
      `Seuil "mauvais site" de l'agence : note < ${config.badSiteThreshold}/100.` +
      (feedback ? `\n\nRetour du Boss sur ta version précédente (corrige ces points) :\n${feedback}` : ''),
    schema: SCHEMA,
    effort: 'medium',
    maxTokens: 16000,
  });
  return { tech, ...ai };
}
