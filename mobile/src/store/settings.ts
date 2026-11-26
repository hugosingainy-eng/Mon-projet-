import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { ModeId, StyleId, TopicId } from '@/content/modes';
import { deviceStorage } from '@/lib/storage';

export type MemoryMode = 'off' | 'on';

type Settings = {
  onboarded: boolean;
  consentAt: number | null; // consentement à l'envoi des messages au fournisseur d'IA
  name: string;
  topics: TopicId[];
  style: StyleId;
  frankness: 1 | 2 | 3; // 1 = tout en douceur … 3 = sans filtre
  defaultMode: ModeId;
  memory: MemoryMode;
  prefersVoice: boolean;
  notifications: boolean;
  appearance: 'system' | 'light' | 'dark';
  voiceId: string | null;
  voiceRate: number;
  showTranscript: boolean;
  shareJournalWithAi: boolean;
  set: (patch: Partial<Omit<Settings, 'set' | 'reset'>>) => void;
  reset: () => void;
};

const initial = {
  onboarded: false,
  consentAt: null,
  name: '',
  topics: [] as TopicId[],
  style: 'douce' as StyleId,
  frankness: 2 as const,
  defaultMode: 'ecoute' as ModeId,
  memory: 'off' as MemoryMode, // la mémoire n'est jamais activée sans choix explicite
  prefersVoice: false,
  notifications: false,
  appearance: 'system' as const,
  voiceId: null,
  voiceRate: 1,
  showTranscript: true,
  shareJournalWithAi: false,
};

export const useSettings = create<Settings>()(
  persist(
    (set) => ({
      ...initial,
      set: (patch) => set(patch),
      reset: () => set(initial),
    }),
    { name: 'confie.settings', storage: deviceStorage, version: 1 },
  ),
);
