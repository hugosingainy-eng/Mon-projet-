// Client Google Places API (New) : recherche d'entreprises + téléchargement des photos.
// Docs : https://developers.google.com/maps/documentation/places/web-service/text-search
import fs from 'node:fs';
import path from 'node:path';
import { config, demoMode } from '../config.js';
import { demoPlaces } from '../demo.js';

const FIELDS = [
  'places.id',
  'places.displayName',
  'places.formattedAddress',
  'places.nationalPhoneNumber',
  'places.internationalPhoneNumber',
  'places.websiteUri',
  'places.googleMapsUri',
  'places.rating',
  'places.userRatingCount',
  'places.businessStatus',
  'places.primaryTypeDisplayName',
  'places.regularOpeningHours.weekdayDescriptions',
  'places.reviews',
  'places.photos',
  'places.editorialSummary',
  'places.location',
  'nextPageToken',
].join(',');

/** Normalise un lieu Google en objet "lead" simple. */
export function normalizePlace(p) {
  return {
    place_id: p.id,
    name: p.displayName?.text || 'Sans nom',
    category: p.primaryTypeDisplayName?.text || '',
    address: p.formattedAddress || '',
    phone: p.nationalPhoneNumber || p.internationalPhoneNumber || '',
    website: p.websiteUri || '',
    maps_url: p.googleMapsUri || '',
    rating: p.rating ?? null,
    reviews_count: p.userRatingCount ?? 0,
    business_status: p.businessStatus || 'OPERATIONAL',
    hours: p.regularOpeningHours?.weekdayDescriptions || [],
    summary: p.editorialSummary?.text || '',
    reviews: (p.reviews || []).slice(0, 5).map((r) => ({
      author: r.authorAttribution?.displayName || 'Client',
      rating: r.rating,
      text: r.text?.text || r.originalText?.text || '',
    })),
    photos: (p.photos || []).slice(0, 8).map((ph) => ({
      name: ph.name,
      width: ph.widthPx,
      height: ph.heightPx,
      attributions: (ph.authorAttributions || []).map((a) => a.displayName),
    })),
    location: p.location || null,
  };
}

/** Recherche textuelle paginée, ex : "boulangerie Lyon". */
export async function searchPlaces(query, city, maxResults = 20) {
  if (demoMode.google) return demoPlaces(query, city).slice(0, maxResults);

  const results = [];
  let pageToken;
  do {
    const res = await fetch('https://places.googleapis.com/v1/places:searchText', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': config.googleMapsKey,
        'X-Goog-FieldMask': FIELDS,
      },
      body: JSON.stringify({
        textQuery: `${query} ${city}`,
        languageCode: 'fr',
        regionCode: 'FR',
        pageSize: Math.min(20, maxResults - results.length),
        ...(pageToken ? { pageToken } : {}),
      }),
    });
    if (!res.ok) {
      throw new Error(`Google Places (${res.status}) : ${(await res.text()).slice(0, 300)}`);
    }
    const data = await res.json();
    results.push(...(data.places || []).map(normalizePlace));
    pageToken = data.nextPageToken;
  } while (pageToken && results.length < maxResults);

  return results.slice(0, maxResults);
}

/**
 * Télécharge les photos Google Maps d'une fiche dans le dossier du site.
 * Renvoie la liste des fichiers locaux + l'attribution obligatoire des auteurs.
 */
export async function downloadPhotos(photos, destDir, max = 6) {
  fs.mkdirSync(destDir, { recursive: true });
  const saved = [];

  for (const [i, ph] of photos.slice(0, max).entries()) {
    try {
      let buffer;
      if (ph.demoUrl || demoMode.google) {
        const url = ph.demoUrl || `https://picsum.photos/seed/${encodeURIComponent(ph.name || i)}/1200/800`;
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        buffer = Buffer.from(await r.arrayBuffer());
      } else {
        const meta = await fetch(
          `https://places.googleapis.com/v1/${ph.name}/media?maxWidthPx=1600&skipHttpRedirect=true&key=${config.googleMapsKey}`
        );
        if (!meta.ok) throw new Error(`HTTP ${meta.status}`);
        const { photoUri } = await meta.json();
        const img = await fetch(photoUri);
        if (!img.ok) throw new Error(`HTTP ${img.status}`);
        buffer = Buffer.from(await img.arrayBuffer());
      }
      const file = `photo-${i + 1}.jpg`;
      fs.writeFileSync(path.join(destDir, file), buffer);
      saved.push({ file, attributions: ph.attributions || [] });
    } catch (err) {
      if (ph.demoUrl) {
        // Mode démo hors ligne : image de remplacement générée localement.
        const file = `photo-${i + 1}.svg`;
        fs.writeFileSync(path.join(destDir, file), placeholderSvg(i));
        saved.push({ file, attributions: ph.attributions || [] });
        continue;
      }
      // Une photo manquante ne bloque pas la création du site.
      console.warn(`Photo ${i + 1} ignorée : ${err.message}`);
    }
  }
  return saved;
}

function placeholderSvg(i) {
  const hues = [18, 32, 145, 200, 265, 340];
  const h = hues[i % hues.length];
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="hsl(${h},45%,62%)"/><stop offset="1" stop-color="hsl(${h + 30},40%,28%)"/></linearGradient></defs>
<rect width="1200" height="800" fill="url(#g)"/><circle cx="${300 + i * 120}" cy="300" r="220" fill="rgba(255,255,255,.12)"/>
<text x="600" y="430" font-family="Georgia" font-size="44" fill="rgba(255,255,255,.75)" text-anchor="middle">Photo de démonstration ${i + 1}</text></svg>`;
}
