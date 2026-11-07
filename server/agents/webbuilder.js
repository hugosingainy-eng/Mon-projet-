// Agent 4 — Créateur de site (chef d'équipe) : fabrique un site vitrine à partir de la fiche Google Maps.
// Sous-agents : 📷 Photographe, 🖋️ Rédacteur web, 💻 Intégrateur.
import fs from 'node:fs';
import path from 'node:path';
import { config } from '../config.js';
import { downloadPhotos } from '../services/googlePlaces.js';
import { askJson, aiAvailable, obj } from '../llm.js';
import { delegate } from '../team.js';
import { siteIssues } from './supervisor.js';

export const name = 'Créateur de site';

export function slugify(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
}

export function sitesDir() {
  return path.join(config.dataDir, 'sites');
}

const esc = (s = '') => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---------- 📷 Photographe ----------
async function photographer(raw, dir) {
  const manifest = path.join(dir, 'photos.json');
  if (fs.existsSync(manifest)) return JSON.parse(fs.readFileSync(manifest, 'utf8'));
  const saved = await downloadPhotos(raw.photos || [], dir);
  // La meilleure photo d'accueil : format paysage, la plus grande.
  const dims = (f) => {
    const i = Number(f.file.match(/\d+/)?.[0]) - 1;
    const ph = (raw.photos || [])[i] || {};
    return { w: ph.width || 1200, h: ph.height || 800 };
  };
  const ranked = saved
    .map((p) => ({ ...p, ...dims(p) }))
    .sort((a, b) => (b.w >= b.h) - (a.w >= a.h) || b.w * b.h - a.w * a.h);
  fs.writeFileSync(manifest, JSON.stringify(ranked));
  return ranked;
}

// ---------- 🖋️ Rédacteur web ----------
const CONTENT_SCHEMA = obj({
  slogan: { type: 'string', description: 'Accroche courte (max 10 mots)' },
  introduction: { type: 'string', description: '2 phrases de présentation, sans rien inventer' },
  points_forts: {
    type: 'array',
    items: obj({ titre: { type: 'string' }, texte: { type: 'string' } }),
    description: '3 points forts tirés UNIQUEMENT des avis clients réels',
  },
  appel_action: { type: 'string', description: "Texte du bouton d'appel, ex. « Appeler maintenant »" },
});

function templateContent(lead, raw) {
  const cat = (lead.category || 'commerce').toLowerCase();
  const city = lead.address.split(',').pop()?.trim().replace(/^\d{5}\s*/, '') || '';
  const points = (raw.reviews || []).filter((r) => r.text).slice(0, 3).map((r, i) => ({
    titre: ['Accueil', 'Savoir-faire', 'Confiance'][i],
    texte: r.text.split(/(?<=[.!?])\s/)[0],
  }));
  return {
    slogan: raw.summary || `Votre ${cat} de confiance${city ? ` à ${city}` : ''}`,
    introduction: `${lead.name} vous accueille ${city ? `à ${city}` : 'près de chez vous'}. ` +
      (lead.rating ? `Noté ${lead.rating}/5 par ${lead.reviews_count} clients sur Google.` : 'Passez nous voir ou appelez-nous.'),
    points_forts: points,
    appel_action: 'Appeler maintenant',
  };
}

async function webWriter(lead, raw, feedback) {
  if (!aiAvailable()) return templateContent(lead, raw);
  return askJson({
    system:
      "Tu es le Rédacteur web d'une agence. Tu écris les textes d'un site vitrine pour une petite entreprise locale, " +
      'en français, chaleureux et concret. Interdit : inventer des prix, des chiffres, des services précis ou des années ' +
      "d'expérience. Les points forts viennent uniquement des avis clients fournis.",
    prompt: `Fiche : ${JSON.stringify({ nom: lead.name, metier: lead.category, adresse: lead.address, note: lead.rating, avis: raw.reviews, description: raw.summary })}` +
      (feedback ? `\n\nCorrections demandées : ${feedback}` : ''),
    schema: CONTENT_SCHEMA,
    effort: 'low',
    maxTokens: 4000,
  });
}

function contentIssues(c) {
  if (!c.slogan?.trim()) return 'slogan manquant';
  if (c.slogan.split(/\s+/).length > 14) return 'slogan trop long (max 10 mots)';
  if (/\d+\s?(€|euros?)|\b(depuis|plus de) \d+ ans\b/i.test(JSON.stringify(c))) return 'prix ou ancienneté inventés : retire-les';
  return null;
}

// ---------- 💻 Intégrateur ----------
function templateSite(lead, raw, photos, content) {
  const hero = photos[0]?.file || '';
  const tel = (lead.phone || '').replace(/\s/g, '');
  const gallery = photos.slice(1).map((p) => `<img src="${p.file}" alt="${esc(lead.name)}" loading="lazy">`).join('');
  const strengths = content.points_forts.map((p) => `<div class="card"><h3>${esc(p.titre)}</h3><p>${esc(p.texte)}</p></div>`).join('');
  const reviews = (raw.reviews || []).filter((r) => r.text).slice(0, 3)
    .map((r) => `<blockquote><p>“${esc(r.text)}”</p><cite>${esc(r.author)} · ${'★'.repeat(Math.round(r.rating || 5))}</cite></blockquote>`).join('');
  const hours = (raw.hours || []).map((h) => `<li>${esc(h)}</li>`).join('');
  const credits = [...new Set(photos.flatMap((p) => p.attributions))].join(', ');
  return `<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(lead.name)} — ${esc(lead.category)} à ${esc(lead.address.split(',').pop()?.trim())}</title>
<meta name="description" content="${esc(lead.name)}, ${esc(lead.category)}. ${esc(lead.address)}. Appelez le ${esc(lead.phone)}.">
<style>
:root{--ink:#1d1b18;--paper:#faf7f2;--accent:#b4532a;--muted:#6b645b}
*{box-sizing:border-box}body{margin:0;font:17px/1.6 Georgia,serif;color:var(--ink);background:var(--paper)}
header{position:relative;min-height:78vh;display:flex;align-items:flex-end;color:#fff;background:#222 url('${hero}') center/cover}
header::after{content:"";position:absolute;inset:0;background:linear-gradient(transparent 30%,rgba(0,0,0,.75))}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
header .wrap{position:relative;z-index:1;padding-bottom:56px}
h1{font-size:clamp(2.2rem,6vw,4rem);line-height:1.05;margin:.2em 0}
.tag{font:600 13px/1 system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;opacity:.9}
.btn{display:inline-block;background:var(--accent);color:#fff;padding:14px 26px;border-radius:999px;text-decoration:none;font:600 16px system-ui,sans-serif;margin-top:16px}
section{padding:72px 0}h2{font-size:2rem;margin:0 0 24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.card{background:#fff;border-radius:12px;padding:22px}.card h3{margin:0 0 6px;color:var(--accent)}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.gallery img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:10px}
blockquote{margin:0 0 20px;padding:24px;background:#fff;border-radius:12px;border-left:4px solid var(--accent)}
cite{font:14px system-ui,sans-serif;color:var(--muted)}
.infos{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:32px}
ul{padding-left:18px}footer{padding:32px 0;font:13px system-ui,sans-serif;color:var(--muted);border-top:1px solid #e6dfd4}
</style></head><body>
<header><div class="wrap"><div class="tag">${esc(lead.category)}${lead.rating ? ` · ★ ${lead.rating}/5 (${lead.reviews_count} avis Google)` : ''}</div>
<h1>${esc(lead.name)}</h1><p>${esc(content.slogan)}</p>
${tel ? `<a class="btn" href="tel:${tel}">${esc(content.appel_action)} · ${esc(lead.phone)}</a>` : ''}</div></header>
<section><div class="wrap"><h2>Bienvenue</h2><p>${esc(content.introduction)}</p>${strengths ? `<div class="cards">${strengths}</div>` : ''}</div></section>
${gallery ? `<section style="padding-top:0"><div class="wrap"><h2>En images</h2><div class="gallery">${gallery}</div></div></section>` : ''}
${reviews ? `<section style="background:#f1ebe1"><div class="wrap"><h2>Ils nous recommandent</h2>${reviews}</div></section>` : ''}
<section><div class="wrap infos">
<div><h2>Nous trouver</h2><p>${esc(lead.address)}</p>${lead.maps_url ? `<a class="btn" href="${esc(lead.maps_url)}">Itinéraire</a>` : ''}</div>
${hours ? `<div><h2>Horaires</h2><ul>${hours}</ul></div>` : ''}
</div></section>
<footer><div class="wrap">© ${new Date().getFullYear()} ${esc(lead.name)}${credits ? ` · Photos : ${esc(credits)} via Google Maps` : ''}</div></footer>
</body></html>`;
}

const HTML_SCHEMA = obj({
  html: { type: 'string', description: 'Document HTML complet et autonome (CSS inline dans <style>)' },
  palette: { type: 'string', description: 'Palette et direction artistique choisies, en une phrase' },
});

async function integrator(lead, raw, photos, content, feedback, previousHtml) {
  if (!aiAvailable()) return { html: templateSite(lead, raw, photos, content), palette: 'gabarit standard' };
  return askJson({
    system:
      "Tu es l'Intégrateur d'une agence web française haut de gamme. Tu assembles un site vitrine one-page, moderne, " +
      'élégant et unique pour une petite entreprise locale, dans un seul fichier HTML autonome (CSS dans <style>, ' +
      'JS minimal ou aucun, aucune ressource externe sauf Google Fonts). Responsive (mobile d’abord), accessible, rapide, ' +
      'avec une vraie direction artistique adaptée au métier (pas de look générique). Utilise EXACTEMENT les textes ' +
      'du Rédacteur web et les photos du Photographe (chemins relatifs fournis, la première est la photo d’accueil). ' +
      "N'invente rien. Inclure : hero avec photo, appel téléphone (lien tel:), points forts, galerie, avis clients réels, " +
      'horaires, adresse + lien itinéraire Google Maps, pied de page avec crédit des photos. title + meta description SEO local.',
    prompt:
      `Fiche : ${JSON.stringify({ nom: lead.name, metier: lead.category, adresse: lead.address, telephone: lead.phone, note: lead.rating, nombre_avis: lead.reviews_count, lien_maps: lead.maps_url, horaires: raw.hours, avis: raw.reviews })}\n\n` +
      `Textes du Rédacteur web : ${JSON.stringify(content)}\n\nPhotos du Photographe (ordre conseillé) : ${JSON.stringify(photos)}` +
      (feedback ? `\n\nCORRECTIONS EXIGÉES :\n${feedback}\n\nVersion précédente :\n${previousHtml.slice(0, 40000)}` : ''),
    schema: HTML_SCHEMA,
    effort: 'high',
    maxTokens: 64000,
  });
}

// ---------- Le chef d'équipe ----------
export async function run(lead, feedback = '', previous = null, ctx = null) {
  const raw = lead.raw || {};
  const slug = lead.site_slug || previous?.slug || `${slugify(lead.name)}-${lead.id}`;
  const dir = path.join(sitesDir(), slug);
  fs.mkdirSync(dir, { recursive: true });

  const photos = previous?.photos || await delegate({
    ctx, chef: name, helper: 'Photographe',
    task: `Récupère les photos Google Maps de ${lead.name} et choisis la photo d'accueil.`,
    run: () => photographer(raw, dir),
    summary: (p) => (p.length ? `${p.length} photo(s) prêtes, accueil : ${p[0].file}.` : 'Aucune photo disponible sur la fiche.'),
  });

  // Le texte est réécrit seulement si le Boss a demandé des corrections (ou au premier passage).
  const content = previous?.content && !feedback ? previous.content : await delegate({
    ctx, chef: name, helper: 'Rédacteur web',
    task: feedback ? `Revois les textes du site. Retour du Boss : ${feedback}` : `Écris les textes du site de ${lead.name} à partir des vrais avis.`,
    run: (fb) => webWriter(lead, raw, [feedback, fb].filter(Boolean).join('\n')),
    check: contentIssues,
    summary: (c) => `Accroche : « ${c.slogan} » + ${c.points_forts.length} point(s) fort(s).`,
  });

  const built = await delegate({
    ctx, chef: name, helper: 'Intégrateur',
    task: feedback ? `Corrige le site. Retour du Boss : ${feedback}` : 'Assemble le site avec les textes et les photos.',
    run: (fb) => integrator(lead, raw, photos, content, [feedback, fb].filter(Boolean).join('\n'), previous?.html || ''),
    // Le chef fait passer les contrôles du Boss AVANT de lui livrer.
    check: (b) => siteIssues(lead, { html: b.html, photos }).join(' ; ') || null,
    summary: (b) => `Site assemblé (${Math.round(b.html.length / 1024)} Ko) — ${b.palette}.`,
  });

  fs.writeFileSync(path.join(dir, 'index.html'), built.html);
  return {
    slug, html: built.html, photos, content,
    notes: `${built.palette}`, url: `${config.publicUrl}/sites/${slug}/`,
  };
}
