// Agent 1 — Prospecteur (chef d'équipe) : cherche les entreprises sur Google Maps.
// Sous-agents : 🔭 Éclaireur (variantes de recherche), 🎯 Qualificateur (priorité commerciale).
import { searchPlaces } from '../services/googlePlaces.js';
import { askJson, aiAvailable, obj } from '../llm.js';
import { demoMode } from '../config.js';
import { delegate } from '../team.js';

export const name = 'Prospecteur';

/** Score de priorité 0-100 : plus il est haut, plus le prospect est intéressant. */
export function priorityScore(p) {
  let s = 0;
  if (!p.website) s += 40;
  if ((p.rating ?? 0) >= 4.3) s += 20;
  else if ((p.rating ?? 0) >= 4) s += 10;
  if ((p.reviews_count ?? 0) >= 20) s += 15;
  if ((p.reviews_count ?? 0) >= 100) s += 10;
  if (p.phone) s += 10;
  if ((p.photos || []).length >= 3) s += 5;
  return Math.min(100, s);
}

async function queryVariants(query, city) {
  if (!aiAvailable() || demoMode.google) return [query];
  const r = await askJson({
    system: "Tu es l'Éclaireur d'une agence web : tu proposes des recherches Google Maps qui trouvent des petites entreprises locales indépendantes.",
    prompt: `Métier recherché : « ${query} » à ${city}. Donne 2 variantes de recherche courtes (synonymes ou métiers très proches, en français), sans la ville.`,
    schema: obj({ variantes: { type: 'array', items: { type: 'string' } } }),
    effort: 'low',
    maxTokens: 2000,
  });
  return [query, ...r.variantes.filter((v) => v && v.toLowerCase() !== query.toLowerCase()).slice(0, 2)];
}

export async function run({ query, city, maxResults }, ctx = null) {
  const places = await delegate({
    ctx, chef: name, helper: 'Éclaireur',
    task: `Ratisse Google Maps : « ${query} » à ${city}, ${maxResults} résultats maximum.`,
    run: async () => {
      const variants = await queryVariants(query, city);
      const seen = new Map();
      for (const v of variants) {
        if (seen.size >= maxResults) break;
        for (const p of await searchPlaces(v, city, maxResults)) {
          if (!seen.has(p.place_id)) seen.set(p.place_id, { ...p, found_with: v });
        }
      }
      return { variants, places: [...seen.values()].slice(0, maxResults) };
    },
    summary: (r) => `${r.places.length} établissements trouvés (recherches : ${r.variants.join(' · ')}).`,
  });

  return delegate({
    ctx, chef: name, helper: 'Qualificateur',
    task: 'Classe ces établissements par priorité commerciale.',
    run: async () => places.places
      .map((p) => ({ ...p, priority: priorityScore(p) }))
      .sort((a, b) => b.priority - a.priority),
    summary: (list) => {
      const hot = list.filter((p) => p.priority >= 60).length;
      return `${hot} prospect(s) très prioritaire(s) sur ${list.length}. En tête : ${list.slice(0, 3).map((p) => `${p.name} (${p.priority})`).join(', ') || '—'}.`;
    },
  });
}
