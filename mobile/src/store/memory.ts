import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { deviceStorage, uid } from '@/lib/storage';

// « Ce que mon IA retient » : une liste courte, lisible et modifiable par la personne.
export type MemoryItem = { id: string; text: string; at: number; source: 'ia' | 'moi' };

type Memory = {
  items: MemoryItem[];
  add: (text: string, source?: MemoryItem['source']) => string | null;
  edit: (id: string, text: string) => void;
  remove: (id: string) => void;
  clear: () => void;
};

const MAX_ITEMS = 60;

export const useMemory = create<Memory>()(
  persist(
    (set, get) => ({
      items: [],
      add: (text, source = 'ia') => {
        const clean = text.replace(/\s+/g, ' ').trim().slice(0, 240);
        if (!clean || get().items.some((i) => i.text.toLowerCase() === clean.toLowerCase())) return null;
        const id = uid().slice(-6);
        set((s) => ({ items: [...s.items, { id, text: clean, at: Date.now(), source }].slice(-MAX_ITEMS) }));
        return id;
      },
      edit: (id, text) => set((s) => ({ items: s.items.map((i) => (i.id === id ? { ...i, text: text.trim().slice(0, 240) } : i)).filter((i) => i.text) })),
      remove: (id) => set((s) => ({ items: s.items.filter((i) => i.id !== id) })),
      clear: () => set({ items: [] }),
    }),
    { name: 'confie.memory', storage: deviceStorage, version: 1 },
  ),
);
