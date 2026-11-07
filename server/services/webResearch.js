// Recherches approfondies sur tout le web (Google, annuaires, réseaux sociaux…) :
//  - findWebsite : l'entreprise a-t-elle VRAIMENT aucun site ? (Google Maps l'oublie souvent)
//  - findEmail   : quelle est son adresse email professionnelle ?
//
// Deux moteurs, utilisés dans cet ordre :
//  1. Google via Serper.dev (SERPER_API_KEY) : vrais résultats Google. On lit les extraits
//     puis on ouvre les pages pour en extraire les emails.
//  2. Claude avec ses outils de recherche et de lecture web (ANTHROPIC_API_KEY) : il cherche
//     comme un humain le ferait (site officiel, Pages Jaunes, Facebook, annuaires, mentions légales).
//
// Chaque email trouvé reçoit un score de confiance, et son domaine est vérifié (enregistrement MX).
import dns from 'node:dns/promises';
import { config } from '../config.js';
import { aiAvailable, askWeb } from '../llm.js';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

// Emails qui appartiennent aux plateformes elles-mêmes, jamais à l'entreprise.
const PLATFORM_DOMAINS = [
  'pagesjaunes.fr', 'solocal.com', 'facebook.com', 'fb.com', 'instagram.com', 'linkedin.com', 'google.com', 'gmail-support',
  'societe.com', 'pappers.fr', 'infogreffe.fr', 'verif.com', 'manageo.fr', 'kompass.com', 'tripadvisor', 'yelp.',
  'mappy.com', 'justacote.com', 'hoodspot.fr', 'cylex', 'annuaire', 'sentry.io', 'wixpress.com', 'wix.com', 'jimdo.com',
  'example.', 'exemple.', 'domain.com', 'email.com', 'votre-domaine', 'monsite', 'sitew.com', 'doctolib.fr', 'planity.com',
  'ovh.net', 'o2switch', 'cloudflare', 'godaddy', 'apple.com', 'w3.org', 'schema.org',
];
const BAD_LOCAL = /^(no-?reply|ne-?pas-?repondre|donotreply|postmaster|abuse|webmaster|privacy|dpo|rgpd|support|sales|press)$/i;
const GENERIC_LOCAL = /^(contact|info|infos|accueil|bonjour|hello|commande|commandes|reservation|rdv|secretariat|atelier|boutique|magasin|agence|devis)$/i;

export function serperAvailable() {
  return Boolean(config.serperKey);
}
export function webSearchAvailable() {
  return serperAvailable() || aiAvailable();
}

const norm = (s = '') => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Mots significatifs du nom (on ignore « le », « chez », « boulangerie »…). */
export function nameTokens(name) {
  const stop = new Set(['le', 'la', 'les', 'de', 'du', 'des', 'chez', 'et', 'sarl', 'sas', 'eurl', 'the', 'aux', 'au', 'l', 'd', 'un', 'une']);
  return norm(name).split(/[^a-z0-9]+/).filter((t) => t.length >= 4 && !stop.has(t));
}

function siteDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; }
}

/** Emails présents dans un texte, y compris les formes masquées : « contact [at] domaine.fr », « arobase ». */
export function findEmailsInText(text = '') {
  const t = text
    .replace(/&#64;|&#x40;|%40/gi, '@')
    .replace(/\s*[[(]\s*(?:at|arobase|@)\s*[\])]\s*/gi, '@')
    .replace(/\s+arobase\s+/gi, '@')
    .replace(/\s*[[(]\s*(?:dot|point)\s*[\])]\s*/gi, '.');
  const out = new Set();
  for (const m of t.matchAll(/mailto:([^"'?\s>]+)/gi)) out.add(decodeURIComponent(m[1]));
  for (const m of t.matchAll(/[A-Z0-9._%+-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)*\.[A-Z]{2,}/gi)) out.add(m[0]);
  return [...out]
    .map((e) => e.toLowerCase().replace(/^[._-]+|[._-]+$/g, ''))
    .filter((e) => /^[^@\s]+@[^@\s]+\.[a-z]{2,}$/.test(e) && !/\.(png|jpe?g|gif|webp|svg|css|js)$/.test(e));
}

export function isPlatformEmail(email) {
  const [local, domain = ''] = email.split('@');
  return BAD_LOCAL.test(local) || PLATFORM_DOMAINS.some((p) => domain.includes(p));
}

/**
 * Score de confiance 0-100 : cet email appartient-il bien à cette entreprise ?
 * @param {string} email
 * @param {object} lead
 * @param {object} evidence  { pageHasName, pageHasPhone, inSnippet, sourceUrl }
 */
export function scoreEmail(email, lead, evidence = {}) {
  if (isPlatformEmail(email)) return 0;
  const [local, domain] = email.split('@');
  let s = 10;
  const own = siteDomain(lead.website || '');
  if (own && (domain === own || domain.endsWith('.' + own))) s += 45;
  const tokens = nameTokens(lead.name);
  if (tokens.some((t) => norm(domain).includes(t) || norm(local).includes(t))) s += 25;
  if (evidence.pageHasName) s += 10;
  if (evidence.pageHasPhone) s += 15;
  if (evidence.inSnippet) s += 5;
  if (GENERIC_LOCAL.test(local)) s += 5;
  if (evidence.sourceUrl && own && siteDomain(evidence.sourceUrl) === own) s += 10;
  return Math.min(100, s);
}

/** Le domaine de l'email peut-il recevoir du courrier ? (enregistrement MX) */
export async function domainAcceptsMail(email, resolveMx = dns.resolveMx) {
  try {
    const mx = await resolveMx(email.split('@')[1]);
    return Array.isArray(mx) && mx.length > 0;
  } catch {
    return false;
  }
}

export function buildQueries(lead) {
  const city = (lead.address.split(',').pop() || '').replace(/\d{5}/, '').trim();
  const phone = (lead.phone || '').trim();
  return [
    `"${lead.name}" ${city} email contact`,
    phone ? `"${phone}" email` : null,
    `"${lead.name}" ${city} "@"`,
  ].filter(Boolean);
}

async function googleSearch(q) {
  const res = await fetch('https://google.serper.dev/search', {
    method: 'POST',
    headers: { 'X-API-KEY': config.serperKey, 'Content-Type': 'application/json' },
    body: JSON.stringify({ q, gl: 'fr', hl: 'fr', num: 10 }),
    signal: AbortSignal.timeout(20000),
  });
  if (!res.ok) throw new Error(`Recherche Google (${res.status}) : ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  return (data.organic || []).map((r) => ({ title: r.title, link: r.link, snippet: r.snippet || '' }));
}

async function fetchText(url) {
  const res = await fetch(url, { headers: { 'User-Agent': UA, Accept: 'text/html' }, redirect: 'follow', signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.text()).slice(0, 800000);
}

/** Ajoute ou renforce un candidat. */
function addCandidate(map, email, score, source) {
  const cur = map.get(email);
  if (!cur || score > cur.score) map.set(email, { email, score, source, sources: [...new Set([...(cur?.sources || []), source])] });
  else cur.sources = [...new Set([...cur.sources, source])];
}

/** Moteur 1 : Google (Serper) + lecture des pages trouvées. */
async function searchWithGoogle(lead, exclude, log) {
  const candidates = new Map();
  const digits = (lead.phone || '').replace(/\D/g, '').slice(-9);
  const tokens = nameTokens(lead.name);
  const visited = new Set();

  for (const q of buildQueries(lead)) {
    const results = await googleSearch(q);
    log(`Google : « ${q} » → ${results.length} résultat(s).`);

    // Les extraits Google contiennent souvent l'email directement.
    for (const r of results) {
      for (const e of findEmailsInText(`${r.title} ${r.snippet}`)) {
        if (exclude.includes(e)) continue;
        const hay = norm(`${r.title} ${r.snippet}`);
        addCandidate(candidates, e, scoreEmail(e, lead, {
          inSnippet: true, sourceUrl: r.link,
          pageHasName: tokens.some((t) => hay.includes(t)),
          pageHasPhone: digits && `${r.snippet}`.replace(/\D/g, '').includes(digits),
        }), r.link);
      }
    }

    // Puis on ouvre les meilleures pages (site officiel, annuaires, Facebook…).
    for (const r of results.slice(0, 5)) {
      if (visited.has(r.link)) continue;
      visited.add(r.link);
      try {
        const html = await fetchText(r.link);
        const text = norm(html);
        const pageHasName = tokens.length ? tokens.every((t) => text.includes(t)) : false;
        const pageHasPhone = Boolean(digits) && html.replace(/\D/g, '').includes(digits);
        for (const e of findEmailsInText(html)) {
          if (exclude.includes(e)) continue;
          addCandidate(candidates, e, scoreEmail(e, lead, { pageHasName, pageHasPhone, sourceUrl: r.link }), r.link);
        }
      } catch { /* page protégée ou indisponible */ }
    }

    const best = [...candidates.values()].sort((a, b) => b.score - a.score)[0];
    if (best && best.score >= 60) break; // assez sûr, inutile de chercher plus
  }
  return [...candidates.values()].sort((a, b) => b.score - a.score);
}

/** Moteur 2 : Claude cherche lui-même sur le web. */
async function searchWithClaude(lead, exclude, feedback) {
  const r = await askWeb({
    system:
      "Tu es le Détective email d'une agence web française. Tu retrouves l'adresse email PROFESSIONNELLE publique d'une " +
      'petite entreprise en cherchant sur le web : site officiel (pages contact, mentions légales), Pages Jaunes, page ' +
      'Facebook, annuaires professionnels, societe.com, articles locaux. Règles : ne donne QUE un email que tu as réellement ' +
      "vu écrit sur une page, avec l'URL de cette page. Jamais d'email deviné ou reconstitué. Vérifie que la page parle bien " +
      "de cette entreprise (même nom, même ville ou même téléphone). N'utilise pas les emails des plateformes elles-mêmes.",
    prompt:
      `Entreprise : ${lead.name}\nMétier : ${lead.category}\nAdresse : ${lead.address}\nTéléphone : ${lead.phone || 'inconnu'}\n` +
      `Site : ${lead.website || 'aucun'}\nFiche Google Maps : ${lead.maps_url || ''}\n` +
      (exclude.length ? `Emails déjà écartés (ne pas les reproposer) : ${exclude.join(', ')}\n` : '') +
      (feedback ? `Remarque du Boss sur ta recherche précédente : ${feedback}\n` : '') +
      '\nTermine ta réponse par un objet JSON seul : ' +
      '{"email": "adresse ou null", "source_url": "page où tu l\'as vu ou null", "extrait": "phrase de la page contenant l\'email", "pourquoi": "comment tu sais que c\'est la bonne entreprise"}',
    maxSearches: 6,
    maxFetches: 6,
  });
  const email = r.email && typeof r.email === 'string' ? r.email.trim().toLowerCase() : null;
  if (!email || exclude.includes(email) || !/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/.test(email)) return [];

  // On ne croit pas sur parole : on revérifie la page source quand c'est possible.
  let pageHasName = false;
  let pageHasPhone = false;
  let confirmed = false;
  if (r.source_url) {
    try {
      const html = await fetchText(r.source_url);
      confirmed = findEmailsInText(html).includes(email);
      const text = norm(html);
      pageHasName = nameTokens(lead.name).every((t) => text.includes(t));
      const digits = (lead.phone || '').replace(/\D/g, '').slice(-9);
      pageHasPhone = Boolean(digits) && html.replace(/\D/g, '').includes(digits);
    } catch { /* page non accessible depuis le serveur */ }
  }
  const score = scoreEmail(email, lead, { pageHasName, pageHasPhone, sourceUrl: r.source_url, inSnippet: confirmed });
  return [{ email, score: confirmed ? score : Math.min(score, 55), source: r.source_url || 'recherche web', sources: [r.source_url].filter(Boolean), extract: r.extrait, why: r.pourquoi, confirmed }];
}

/**
 * Cherche l'email d'une entreprise sur tout le web.
 * @returns {Promise<{email: string|null, score: number, source: string|null, mxOk: boolean, engine: string, alternatives: object[], log: string[]}>}
 */
export async function findEmail(lead, { exclude = [], feedback = '' } = {}) {
  const log = [];
  let candidates = [];
  let engine = 'aucun';

  if (serperAvailable()) {
    engine = 'Google';
    try {
      candidates = await searchWithGoogle(lead, exclude, (m) => log.push(m));
    } catch (err) {
      log.push(`Google indisponible : ${err.message}`);
    }
  }
  if ((!candidates.length || candidates[0].score < 50) && aiAvailable()) {
    engine = engine === 'Google' ? 'Google + Claude' : 'Claude (recherche web)';
    try {
      const more = await searchWithClaude(lead, exclude, feedback);
      log.push(more.length ? `Claude a trouvé ${more[0].email} sur ${more[0].source}.` : 'Claude n’a trouvé aucun email publié.');
      candidates = [...more, ...candidates].sort((a, b) => b.score - a.score);
    } catch (err) {
      log.push(`Recherche Claude impossible : ${err.message}`);
    }
  }
  if (engine === 'aucun') {
    log.push('Aucun moteur de recherche configuré : ajoutez SERPER_API_KEY (Google) ou ANTHROPIC_API_KEY.');
  }

  const valid = candidates.filter((c) => c.score > 0);
  const best = valid[0] || null;
  return {
    email: best?.email || null,
    score: best?.score || 0,
    source: best?.source || null,
    extract: best?.extract || null,
    mxOk: best ? await domainAcceptsMail(best.email) : false,
    engine,
    alternatives: valid.slice(1, 4).map(({ email, score, source }) => ({ email, score, source })),
    log,
  };
}

// =====================================================================================
// Vérification du site internet
// =====================================================================================

// Sites qui ne sont PAS le site de l'entreprise (annuaires, réseaux sociaux, plateformes).
const DIRECTORY_DOMAINS = [
  ...PLATFORM_DOMAINS, 'twitter.com', 'x.com', 'tiktok.com', 'youtube.com', 'pinterest.', 'waze.com', 'apple.com',
  'leboncoin.fr', 'lefigaro.fr', 'ouest-france.fr', 'actu.fr', 'leparisien.fr', 'wikipedia.org', 'bing.com',
  'ubereats.com', 'deliveroo.fr', 'justeat', 'thefork.fr', 'lafourchette.com', 'restaurantguru', 'petitfute.com',
  'habitatpresto.com', 'travaux.com', 'starofservice', 'houzz.fr', 'kelplombier', 'treatwell', 'booksy.com',
  'linternaute.com', 'horaires.lefigaro', 'pagesblanches', '118712', '118000', 'lacentrale', 'autoplus', 'mapstr',
  'societeinfo', 'entreprises.lefigaro', 'b-reputation', 'firmania', 'europages', 'indeed', 'hellowork', 'gralon',
];
const SOCIAL = /(facebook\.com|instagram\.com|linkedin\.com|tiktok\.com)/i;

export function isDirectory(url) {
  const d = siteDomain(url);
  return !d || DIRECTORY_DOMAINS.some((p) => d.includes(p.replace(/\.$/, '')));
}

function cityOf(lead) {
  return (lead.address.split(',').pop() || '').replace(/\d{5}/, '').trim();
}

/** Score 0-100 : cette page est-elle le site officiel de l'entreprise ? */
export function scoreWebsite(url, lead, page = {}) {
  if (isDirectory(url)) return 0;
  const d = norm(siteDomain(url));
  const tokens = nameTokens(lead.name);
  let s = 0;
  if (tokens.some((t) => d.includes(t))) s += 35;
  if (page.hasPhone) s += 40;
  if (page.hasName) s += 20;
  if (page.hasCity) s += 10;
  if (page.hasAddress) s += 15;
  return Math.min(100, s);
}

async function inspectPage(url, lead) {
  const html = await fetchText(url);
  const text = norm(html);
  const digits = (lead.phone || '').replace(/\D/g, '').slice(-9);
  const street = norm(lead.address.split(',')[0] || '').replace(/^\d+\s*/, '');
  return {
    hasPhone: Boolean(digits) && html.replace(/\D/g, '').includes(digits),
    hasName: nameTokens(lead.name).length > 0 && nameTokens(lead.name).every((t) => text.includes(t)),
    hasCity: cityOf(lead) ? text.includes(norm(cityOf(lead))) : false,
    hasAddress: street.length > 6 && text.includes(street),
  };
}

/** Moteur 1 : Google (Serper). */
async function websiteWithGoogle(lead, exclude, log) {
  const queries = [`"${lead.name}" ${cityOf(lead)}`, lead.phone ? `"${lead.phone}"` : null, `${lead.name} ${lead.category} ${cityOf(lead)} site officiel`].filter(Boolean);
  const candidates = new Map();
  const social = new Set();
  for (const q of queries) {
    const results = await googleSearch(q);
    log.push(`Google : « ${q} » → ${results.length} résultat(s).`);
    for (const r of results.slice(0, 8)) {
      if (SOCIAL.test(r.link)) {
        const hay = norm(`${r.title} ${r.snippet}`);
        if (nameTokens(lead.name).some((t) => hay.includes(t))) social.add(r.link);
        continue;
      }
      if (isDirectory(r.link)) continue;
      const home = new URL(r.link).origin + '/';
      if (candidates.has(home) || exclude.includes(home)) continue;
      let page = {};
      try { page = await inspectPage(r.link, lead); } catch { /* inaccessible */ }
      candidates.set(home, { url: home, score: scoreWebsite(r.link, lead, page), evidence: page, found_on: r.link });
    }
    const best = [...candidates.values()].sort((a, b) => b.score - a.score)[0];
    if (best && best.score >= 70) break;
  }
  return { candidates: [...candidates.values()].sort((a, b) => b.score - a.score), social: [...social] };
}

/** Moteur 2 : Claude cherche lui-même. */
async function websiteWithClaude(lead, exclude, feedback) {
  const r = await askWeb({
    system:
      "Tu es le Vérificateur de site d'une agence web française. Google Maps n'indique pas de site pour cette entreprise, " +
      "mais c'est souvent un oubli. Fais une recherche approfondie pour savoir si elle a SON PROPRE site internet " +
      '(nom de domaine à elle). Les annuaires (Pages Jaunes, societe.com…), plateformes de réservation et réseaux sociaux ' +
      "ne comptent PAS comme un site, mais note les pages Facebook/Instagram trouvées. Vérifie que le site trouvé est bien " +
      "celui de cette entreprise (même téléphone, même adresse ou même nom dans la même ville). Ne devine jamais une URL.",
    prompt:
      `Entreprise : ${lead.name}\nMétier : ${lead.category}\nAdresse : ${lead.address}\nTéléphone : ${lead.phone || 'inconnu'}\n` +
      (exclude.length ? `Sites déjà écartés : ${exclude.join(', ')}\n` : '') +
      (feedback ? `Remarque du Boss : ${feedback}\n` : '') +
      '\nTermine par un objet JSON seul : {"site": "URL du site officiel ou null", "reseaux": ["URLs des pages réseaux sociaux"], "preuve": "ce qui prouve que c\'est bien elle", "certitude": "haute|moyenne|faible"}',
    maxSearches: 5,
    maxFetches: 4,
  });
  const out = { candidates: [], social: Array.isArray(r.reseaux) ? r.reseaux.filter((u) => SOCIAL.test(u)).slice(0, 4) : [] };
  if (r.site && typeof r.site === 'string' && /^https?:\/\//.test(r.site) && !isDirectory(r.site)) {
    let page = {};
    let reachable = false;
    try { page = await inspectPage(r.site, lead); reachable = true; } catch { /* inaccessible depuis le serveur */ }
    let score = scoreWebsite(r.site, lead, page);
    if (!reachable && r.certitude === 'haute') score = Math.max(score, 60);
    out.candidates.push({ url: r.site, score, evidence: { ...page, preuve: r.preuve, certitude: r.certitude }, found_on: 'recherche web Claude' });
  }
  return out;
}

/**
 * Vérifie sur tout le web si l'entreprise a un site que Google Maps ne montre pas.
 * @returns {Promise<{website: string|null, score: number, evidence: object|null, social: string[], engine: string, searched: boolean, log: string[]}>}
 */
export async function findWebsite(lead, { exclude = [], feedback = '' } = {}) {
  const log = [];
  let candidates = [];
  const social = new Set();
  let engine = 'aucun';

  if (serperAvailable()) {
    engine = 'Google';
    try {
      const g = await websiteWithGoogle(lead, exclude, log);
      candidates = g.candidates;
      g.social.forEach((u) => social.add(u));
    } catch (err) {
      log.push(`Google indisponible : ${err.message}`);
    }
  }
  if ((!candidates.length || candidates[0].score < 55) && aiAvailable()) {
    engine = engine === 'Google' ? 'Google + Claude' : 'Claude (recherche web)';
    try {
      const c = await websiteWithClaude(lead, exclude, feedback);
      c.social.forEach((u) => social.add(u));
      candidates = [...c.candidates, ...candidates].sort((a, b) => b.score - a.score);
      log.push(c.candidates.length ? `Claude a trouvé ${c.candidates[0].url}.` : 'Claude confirme : aucun site officiel trouvé.');
    } catch (err) {
      log.push(`Recherche Claude impossible : ${err.message}`);
    }
  }
  if (engine === 'aucun') log.push('Aucun moteur de recherche configuré : ajoutez SERPER_API_KEY (Google) ou ANTHROPIC_API_KEY.');

  const best = candidates[0] && candidates[0].score >= 55 ? candidates[0] : null;
  return {
    website: best?.url || null,
    score: best?.score || 0,
    evidence: best?.evidence || null,
    foundOn: best?.found_on || null,
    rejected: candidates.filter((c) => c !== best).slice(0, 3).map(({ url, score }) => ({ url, score })),
    social: [...social],
    engine,
    searched: engine !== 'aucun',
    log,
  };
}
