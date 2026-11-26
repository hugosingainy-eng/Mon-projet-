import AsyncStorage from '@react-native-async-storage/async-storage';
import { createJSONStorage, type StateStorage } from 'zustand/middleware';

// Toutes les données personnelles restent sur l'appareil tant que la synchronisation n'est pas activée.
// Si le stockage est bloqué (navigation privée, cadre isolé, quota plein), l'app continue de
// fonctionner en gardant les données en mémoire le temps de la visite, au lieu de rester blanche.
const memory = new Map<string, string>();
let blocked = false;

const safeStorage: StateStorage = {
  getItem: async (key) => {
    if (blocked) return memory.get(key) ?? null;
    try { return await AsyncStorage.getItem(key); } catch { blocked = true; return memory.get(key) ?? null; }
  },
  setItem: async (key, value) => {
    memory.set(key, value);
    if (blocked) return;
    try { await AsyncStorage.setItem(key, value); } catch { blocked = true; }
  },
  removeItem: async (key) => {
    memory.delete(key);
    if (blocked) return;
    try { await AsyncStorage.removeItem(key); } catch { blocked = true; }
  },
};

export const deviceStorage = createJSONStorage(() => safeStorage);
/** Vrai si rien ne peut être enregistré sur cet appareil : les données disparaîtront à la fermeture. */
export const storageBlocked = () => blocked;

export const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);

export const dayKey = (d: Date | number = new Date()) => {
  const x = new Date(d);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
};

export async function wipeDevice() {
  for (const k of [...memory.keys()]) if (k.startsWith('confie.')) memory.delete(k);
  try {
    const keys = await AsyncStorage.getAllKeys();
    await AsyncStorage.multiRemove(keys.filter((k) => k.startsWith('confie.')));
  } catch { /* stockage bloqué : la mémoire est déjà vidée */ }
}
