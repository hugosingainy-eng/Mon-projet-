import { useEffect, useState } from 'react';

import { useChats } from '@/store/chats';
import { useMemory } from '@/store/memory';
import { useSettings } from '@/store/settings';
import { useWellbeing } from '@/store/wellbeing';

const stores = [useSettings, useChats, useMemory, useWellbeing];

/** Vrai une fois les données de l'appareil relues. */
export function useHydrated() {
  const [ready, setReady] = useState(() => stores.every((s) => s.persist.hasHydrated()));
  useEffect(() => {
    if (ready) return;
    const check = () => { if (stores.every((s) => s.persist.hasHydrated())) setReady(true); };
    const unsubs = stores.map((s) => s.persist.onFinishHydration(check));
    check();
    return () => unsubs.forEach((u) => u());
  }, [ready]);
  return ready;
}

export function greetingFor(date = new Date()) {
  const h = date.getHours();
  return h < 5 ? 'Bonsoir' : h < 18 ? 'Bonjour' : 'Bonsoir';
}
