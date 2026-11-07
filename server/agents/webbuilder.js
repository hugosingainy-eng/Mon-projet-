// Agent 4 — Créateur de sites : fabrique un site vitrine à partir de la fiche Google Maps
// (photos, avis, horaires, téléphone, adresse).
import fs from 'node:fs';
import path from 'node:path';
import { config } from '../config.js';
import { downloadPhotos } from '../services/googlePlaces.js';
import { askJson, aiAvailable, obj } from '../llm.js';

export const name = 'Créateur de site';

export function slugify(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
}

export function sitesDir() {
  return path.join(config.dataDir, 'sites');
}

const esc = (s = '') => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const SCHEMA = obj({
  html: { type: 'string', description: 'Document HTML complet et autonome (CSS inline dans <style>)' },
  palette: { type: 'string', description: 'Palette et direction artistique choisies, en une phrase' },
  notes: { type: 'string', description: 'Ce qui a été fait / corrigé' },
});

/** Gabarit sans IA (mode démo ou secours). */
function templateSite(lead, raw, photos) {
  const hero = photos[0]?.file || '';
  const tel = (lead.phone || '').replace(/\s/g, '');
  const gallery = photos.slice(1).map((p) => `<img src="${p.file}" alt="${esc(lead.name)}" loading="lazy">`).join('');
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
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.gallery img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:10px}
blockquote{margin:0 0 20px;padding:24px;background:#fff;border-radius:12px;border-left:4px solid var(--accent)}
cite{font:14px system-ui,sans-serif;color:var(--muted)}
.infos{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:32px}
ul{padding-left:18px}footer{padding:32px 0;font:13px system-ui,sans-serif;color:var(--muted);border-top:1px solid #e6dfd4}
</style></head><body>
<header><div class="wrap"><div class="tag">${esc(lead.category)}${lead.rating ? ` · ★ ${lead.rating}/5 (${lead.reviews_count} avis Google)` : ''}</div>
<h1>${esc(lead.name)}</h1><p>${esc(raw.summary || `Votre ${lead.category.toLowerCase()} de confiance, au cœur du quartier.`)}</p>
${tel ? `<a class="btn" href="tel:${tel}">Appeler le ${esc(lead.phone)}</a>` : ''}</div></header>
${gallery ? `<section><div class="wrap"><h2>En images</h2><div class="gallery">${gallery}</div></div></section>` : ''}
${reviews ? `<section style="background:#f1ebe1"><div class="wrap"><h2>Ils nous recommandent</h2>${reviews}</div></section>` : ''}
<section><div class="wrap infos">
<div><h2>Nous trouver</h2><p>${esc(lead.address)}</p>${lead.maps_url ? `<a class="btn" href="${esc(lead.maps_url)}">Itinéraire</a>` : ''}</div>
${hours ? `<div><h2>Horaires</h2><ul>${hours}</ul></div>` : ''}
</div></section>
<footer><div class="wrap">© ${new Date().getFullYear()} ${esc(lead.name)}${credits ? ` · Photos : ${esc(credits)} via Google Maps` : ''}</div></footer>
</body></html>`;
}

export async function run(lead, feedback = '', previousHtml = '') {
  const raw = lead.raw || {};
  const slug = lead.site_slug || `${slugify(lead.name)}-${lead.id}`;
  const dir = path.join(sitesDir(), slug);

  // Les photos ne sont téléchargées qu'une fois.
  let photos;
  const manifest = path.join(dir, 'photos.json');
  if (fs.existsSync(manifest)) {
    photos = JSON.parse(fs.readFileSync(manifest, 'utf8'));
  } else {
    photos = await downloadPhotos(raw.photos || [], dir);
    fs.writeFileSync(manifest, JSON.stringify(photos));
  }

  let html;
  let notes = 'Gabarit standard (mode sans IA).';
  if (!aiAvailable()) {
    html = templateSite(lead, raw, photos);
  } else {
    const result = await askJson({
      system:
        "Tu es le Créateur de sites d'une agence web française haut de gamme. Tu produis un site vitrine one-page, " +
        "moderne, élégant et unique pour une petite entreprise locale, dans un seul fichier HTML autonome (CSS dans <style>, " +
        'JS minimal ou aucun, aucune ressource externe sauf Google Fonts). Le site doit être responsive (mobile d’abord), ' +
        'accessible, rapide, avec une vraie direction artistique adaptée au métier (pas de look générique). ' +
        "Utilise UNIQUEMENT les vraies informations fournies : n'invente ni prix, ni services précis, ni chiffres, ni faux avis. " +
        'Les photos sont disponibles en chemins relatifs (photo-1.jpg, …). Inclure : hero avec photo, appel à l’action ' +
        "téléphone (lien tel:), galerie, avis clients réels, horaires, adresse + lien itinéraire Google Maps, pied de page avec " +
        'le crédit des photos. Balises title et meta description optimisées pour le SEO local. Tout le texte en français.',
      prompt:
        `Fiche Google Maps :\n${JSON.stringify({
          nom: lead.name, metier: lead.category, adresse: lead.address, telephone: lead.phone,
          note: lead.rating, nombre_avis: lead.reviews_count, lien_maps: lead.maps_url,
          description: raw.summary, horaires: raw.hours, avis: raw.reviews,
          ancien_site: lead.website || null,
        }, null, 2)}\n\nPhotos disponibles :\n${JSON.stringify(photos)}` +
        (feedback
          ? `\n\nLe Boss a REFUSÉ ta version précédente. Corrige impérativement :\n${feedback}\n\nVersion précédente :\n${previousHtml.slice(0, 40000)}`
          : ''),
      schema: SCHEMA,
      effort: 'high',
      maxTokens: 64000,
    });
    html = result.html;
    notes = `${result.palette} — ${result.notes}`;
  }

  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'index.html'), html);
  return { slug, html, photos, notes, url: `${config.publicUrl}/sites/${slug}/` };
}
