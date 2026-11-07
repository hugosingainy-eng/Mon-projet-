// Agent 1 — Prospecteur : cherche les entreprises sur Google Maps.
import { searchPlaces } from '../services/googlePlaces.js';

export const name = 'Prospecteur';

export async function run({ query, city, maxResults }) {
  const places = await searchPlaces(query, city, maxResults);
  return places;
}
