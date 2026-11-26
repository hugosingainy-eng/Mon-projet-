import * as Speech from 'expo-speech';

export type FrenchVoice = { id: string; label: string };

// Débits proposés pour la lecture à voix haute (valeur passée à expo-speech).
export const VOICE_RATES = [
  { value: 0.85, label: 'Plus lente' },
  { value: 1, label: 'Normale' },
  { value: 1.15, label: 'Plus rapide' },
] as const;

const REGIONS: Record<string, string> = { fr: 'France', ca: 'Canada', be: 'Belgique', ch: 'Suisse' };
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Voix françaises installées sur l'appareil. Liste vide si la synthèse vocale n'est pas disponible. */
export async function listFrenchVoices(): Promise<FrenchVoice[]> {
  try {
    let all = await Speech.getAvailableVoicesAsync();
    // Sur le web, le navigateur charge parfois ses voix avec un léger retard.
    if (all.length === 0) { await wait(500); all = await Speech.getAvailableVoicesAsync(); }
    const seen = new Set<string>();
    return all
      .filter((v) => v.language?.toLowerCase().replace('_', '-').startsWith('fr'))
      .filter((v) => (seen.has(v.identifier) ? false : (seen.add(v.identifier), true)))
      .map((v) => {
        const region = REGIONS[v.language.toLowerCase().replace('_', '-').split('-')[1] ?? ''];
        return { id: v.identifier, label: region && !v.name.includes(region) ? `${v.name} · ${region}` : v.name };
      })
      .sort((a, b) => a.label.localeCompare(b.label, 'fr'));
  } catch {
    return [];
  }
}
