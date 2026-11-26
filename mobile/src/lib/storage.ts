import AsyncStorage from '@react-native-async-storage/async-storage';
import { createJSONStorage } from 'zustand/middleware';

// Toutes les données personnelles restent sur l'appareil tant que la synchronisation n'est pas activée.
export const deviceStorage = createJSONStorage(() => AsyncStorage);

export const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);

export const dayKey = (d: Date | number = new Date()) => {
  const x = new Date(d);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`;
};

export async function wipeDevice() {
  const keys = await AsyncStorage.getAllKeys();
  await AsyncStorage.multiRemove(keys.filter((k) => k.startsWith('confie.')));
}
