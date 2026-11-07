// Analyse technique d'un site existant (sans navigateur) + extraction des emails de contact.
import { config, demoMode } from '../config.js';

const UA = 'Mozilla/5.0 (compatible; AgenceAuditBot/1.0)';

function pick(re, html) {
  const m = html.match(re);
  return m ? m[1].trim() : '';
}

export function extractEmails(html) {
  const found = new Set();
  for (const m of html.matchAll(/mailto:([^"'?\s>]+)/gi)) found.add(decodeURIComponent(m[1]).toLowerCase());
  for (const m of html.matchAll(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi)) found.add(m[0].toLowerCase());
  return [...found].filter(
    (e) => !/\.(png|jpe?g|gif|webp|svg)$/i.test(e) && !/(sentry|wixpress|example|domain\.com|u003e)/i.test(e)
  );
}

async function pageSpeed(url) {
  if (demoMode.google || !config.pageSpeedKey) return null;
  try {
    const api = `https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=${encodeURIComponent(url)}&strategy=mobile&category=performance&category=seo&key=${config.pageSpeedKey}`;
    const r = await fetch(api, { signal: AbortSignal.timeout(60000) });
    if (!r.ok) return null;
    const j = await r.json();
    const c = j.lighthouseResult?.categories || {};
    return {
      performance: Math.round((c.performance?.score ?? 0) * 100),
      seo: Math.round((c.seo?.score ?? 0) * 100),
    };
  } catch {
    return null;
  }
}

/**
 * Renvoie des mesures objectives + une note technique sur 100.
 * Plus la note est basse, plus le site est mauvais (= meilleure opportunité).
 */
export async function auditWebsite(url) {
  const checks = [];
  const add = (label, ok, weight, detail = '') => checks.push({ label, ok, weight, detail });
  let html = '';
  let finalUrl = url;
  let status = 0;
  let loadMs = 0;

  const t0 = Date.now();
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': UA, Accept: 'text/html' },
      redirect: 'follow',
      signal: AbortSignal.timeout(20000),
    });
    status = res.status;
    finalUrl = res.url || url;
    html = (await res.text()).slice(0, 600000);
  } catch (err) {
    loadMs = Date.now() - t0;
    return {
      url, reachable: false, error: err.message, score: 5, loadMs, emails: [],
      checks: [{ label: 'Site accessible', ok: false, weight: 100, detail: err.message }],
      excerpt: '',
    };
  }
  loadMs = Date.now() - t0;

  const lower = html.toLowerCase();
  const title = pick(/<title[^>]*>([^<]*)<\/title>/i, html);
  const description = pick(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']*)/i, html);
  const years = [...html.matchAll(/(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})/gi)].map((m) => +m[1]);
  const copyrightYear = years.length ? Math.max(...years) : null;
  const thisYear = new Date().getFullYear();
  const textLength = html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<[^>]+>/g, ' ').replace(/\s+/g, ' ').length;

  add('Site accessible (HTTP 200)', status >= 200 && status < 400, 15, `HTTP ${status}`);
  add('HTTPS sécurisé', finalUrl.startsWith('https://'), 12, finalUrl);
  add('Adapté au mobile (meta viewport)', /<meta[^>]+name=["']viewport/i.test(html), 15);
  add('Titre de page présent', title.length >= 10, 6, title.slice(0, 80));
  add('Meta description SEO', description.length >= 50, 6, description.slice(0, 120));
  add('Chargement < 3 s', loadMs < 3000, 8, `${loadMs} ms`);
  add('Contenu suffisant', textLength > 1500, 8, `${textLength} caractères`);
  add('Pas de technologies obsolètes (Flash, frames)', !/(<frameset|\.swf|<marquee|<font )/i.test(html), 8);
  add('Copyright à jour', copyrightYear ? copyrightYear >= thisYear - 2 : true, 6, copyrightYear ? `© ${copyrightYear}` : 'non trouvé');
  add('Moyen de contact visible', /(tel:|mailto:|<form)/i.test(lower), 8);
  add('Données structurées / Open Graph', /(og:title|application\/ld\+json)/i.test(html), 4);
  add('Images avec texte alternatif', !/<img(?![^>]*\balt=)[^>]*>/i.test(html), 4);

  let score = checks.reduce((s, c) => s + (c.ok ? c.weight : 0), 0);
  const psi = await pageSpeed(finalUrl);
  if (psi) score = Math.round(score * 0.6 + ((psi.performance + psi.seo) / 2) * 0.4);

  return {
    url,
    finalUrl,
    reachable: status > 0 && status < 400,
    status,
    loadMs,
    title,
    description,
    copyrightYear,
    pageSpeed: psi,
    checks,
    score,
    emails: extractEmails(html),
    // Extrait de texte pour que l'agent IA juge aussi le contenu/design.
    excerpt: html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, '').slice(0, 6000),
  };
}
