// Outils d'audit d'un site existant (sans navigateur), utilisés par les sous-agents
// de l'Auditeur : Technicien, Analyste SEO, Enquêteur contact.
import { config, demoMode } from '../config.js';

const UA = 'Mozilla/5.0 (compatible; AgenceAuditBot/1.0)';

function pick(re, html) {
  const m = html.match(re);
  return m ? m[1].trim() : '';
}

async function fetchPage(url, timeout = 20000) {
  const res = await fetch(url, {
    headers: { 'User-Agent': UA, Accept: 'text/html' },
    redirect: 'follow',
    signal: AbortSignal.timeout(timeout),
  });
  return { status: res.status, finalUrl: res.url || url, html: (await res.text()).slice(0, 600000) };
}

export function extractEmails(html) {
  const found = new Set();
  for (const m of html.matchAll(/mailto:([^"'?\s>]+)/gi)) found.add(decodeURIComponent(m[1]).toLowerCase());
  for (const m of html.matchAll(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi)) found.add(m[0].toLowerCase());
  return [...found].filter(
    (e) => !/\.(png|jpe?g|gif|webp|svg)$/i.test(e) && !/(sentry|wixpress|example|domain\.com|u003e)/i.test(e)
  );
}

const check = (label, ok, weight, detail = '') => ({ label, ok, weight, detail });

/** 🛠️ Technicien : accessibilité, sécurité, mobile, vitesse, technologies. */
export async function technicalAudit(url) {
  const t0 = Date.now();
  let page;
  try {
    page = await fetchPage(url);
  } catch (err) {
    return {
      url, finalUrl: url, reachable: false, status: 0, error: err.message, loadMs: Date.now() - t0, html: '',
      checks: [check('Site accessible', false, 100, err.message)],
    };
  }
  const loadMs = Date.now() - t0;
  const { html, finalUrl, status } = page;
  const years = [...html.matchAll(/(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})/gi)].map((m) => +m[1]);
  const copyrightYear = years.length ? Math.max(...years) : null;
  const textLength = html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<[^>]+>/g, ' ').replace(/\s+/g, ' ').length;

  return {
    url, finalUrl, status, loadMs, html, copyrightYear,
    reachable: status > 0 && status < 400,
    checks: [
      check('Site accessible (HTTP 200)', status >= 200 && status < 400, 15, `HTTP ${status}`),
      check('HTTPS sécurisé', finalUrl.startsWith('https://'), 12, finalUrl),
      check('Adapté au mobile (meta viewport)', /<meta[^>]+name=["']viewport/i.test(html), 15),
      check('Chargement < 3 s', loadMs < 3000, 8, `${loadMs} ms`),
      check('Contenu suffisant', textLength > 1500, 8, `${textLength} caractères`),
      check('Pas de technologies obsolètes (Flash, frames)', !/(<frameset|\.swf|<marquee|<font )/i.test(html), 8),
      check('Copyright à jour', copyrightYear ? copyrightYear >= new Date().getFullYear() - 2 : true, 6, copyrightYear ? `© ${copyrightYear}` : 'non trouvé'),
      check('Moyen de contact visible', /(tel:|mailto:|<form)/i.test(html), 8),
    ],
  };
}

async function pageSpeed(url) {
  if (demoMode.google || !config.pageSpeedKey) return null;
  try {
    const api = `https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=${encodeURIComponent(url)}&strategy=mobile&category=performance&category=seo&key=${config.pageSpeedKey}`;
    const r = await fetch(api, { signal: AbortSignal.timeout(60000) });
    if (!r.ok) return null;
    const c = (await r.json()).lighthouseResult?.categories || {};
    return { performance: Math.round((c.performance?.score ?? 0) * 100), seo: Math.round((c.seo?.score ?? 0) * 100) };
  } catch {
    return null;
  }
}

/** 📈 Analyste SEO : balises, données structurées, PageSpeed. */
export async function seoAudit({ html, finalUrl, reachable }) {
  const title = pick(/<title[^>]*>([^<]*)<\/title>/i, html);
  const description = pick(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']*)/i, html);
  return {
    title,
    description,
    pageSpeed: reachable ? await pageSpeed(finalUrl) : null,
    checks: [
      check('Titre de page présent', title.length >= 10, 6, title.slice(0, 80)),
      check('Meta description SEO', description.length >= 50, 6, description.slice(0, 120)),
      check('Données structurées / Open Graph', /(og:title|application\/ld\+json)/i.test(html), 4),
      check('Images avec texte alternatif', !/<img(?![^>]*\balt=)[^>]*>/i.test(html), 4),
    ],
  };
}

/** 🕵️ Enquêteur contact : emails de la page d'accueil puis des pages contact / mentions légales. */
export async function findContactEmails({ html, finalUrl, reachable }) {
  const emails = new Set(extractEmails(html || ''));
  const visited = [];
  if (reachable && emails.size === 0) {
    const links = [...(html || '').matchAll(/href=["']([^"'#]+)["']/gi)]
      .map((m) => m[1])
      .filter((h) => /(contact|mentions|legal|a-propos|about)/i.test(h));
    const candidates = [...new Set([...links, '/contact', '/mentions-legales'])].slice(0, 4);
    for (const href of candidates) {
      try {
        const u = new URL(href, finalUrl);
        if (u.origin !== new URL(finalUrl).origin) continue;
        const page = await fetchPage(u.href, 10000);
        visited.push(u.pathname);
        extractEmails(page.html).forEach((e) => emails.add(e));
        if (emails.size) break;
      } catch { /* page absente */ }
    }
  }
  return { emails: [...emails], visited };
}

/** Note technique globale sur 100 à partir des rapports des sous-agents. */
export function combineScore(tech, seo) {
  const checks = [...tech.checks, ...seo.checks];
  let score = tech.reachable === false ? 5 : checks.reduce((s, c) => s + (c.ok ? c.weight : 0), 0);
  if (seo.pageSpeed) score = Math.round(score * 0.6 + ((seo.pageSpeed.performance + seo.pageSpeed.seo) / 2) * 0.4);
  return { checks, score };
}
