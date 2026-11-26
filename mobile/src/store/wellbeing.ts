import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { dayKey, deviceStorage, uid } from '@/lib/storage';

export type MoodEntry = {
  id: string;
  day: string; // AAAA-MM-JJ
  at: number;
  mood: 1 | 2 | 3 | 4 | 5;
  emotions: string[];
  intensity: number; // 1–5, 0 = non renseigné
  stress: number; // 1–5, 0 = non renseigné
  energy: number; // 1–5, 0 = non renseigné
  sleepHours: number | null; // facultatif
  note: string;
};

export type JournalEntry = {
  id: string;
  at: number;
  prompt: string | null; // question guidée éventuelle
  text: string;
  emotions: string[];
  shareWithAi: boolean; // par entrée, désactivé par défaut
  reflection: string | null; // réflexion de l'IA, uniquement si demandée
};

export type ExerciseLog = { id: string; exerciseId: string; at: number; helpful: boolean | null };
export type Goal = { id: string; text: string; createdAt: number; doneAt: number | null };
export type SavedVideo = { id: string; title: string; channel: string; url: string; why: string; category: string; savedAt: number };

type Wellbeing = {
  moods: MoodEntry[];
  journal: JournalEntry[];
  exerciseLogs: ExerciseLog[];
  goals: Goal[];
  videos: SavedVideo[];
  saveMood: (e: Omit<MoodEntry, 'id' | 'day' | 'at'>) => void;
  removeMood: (id: string) => void;
  saveJournal: (e: Omit<JournalEntry, 'id' | 'at' | 'reflection'> & { id?: string }) => string;
  setReflection: (id: string, reflection: string | null) => void;
  removeJournal: (id: string) => void;
  logExercise: (exerciseId: string, helpful?: boolean | null) => void;
  addGoal: (text: string) => void;
  toggleGoal: (id: string) => void;
  removeGoal: (id: string) => void;
  saveVideo: (v: Omit<SavedVideo, 'savedAt'>) => void;
  removeVideo: (id: string) => void;
  clear: () => void;
};

export const useWellbeing = create<Wellbeing>()(
  persist(
    (set) => ({
      moods: [],
      journal: [],
      exerciseLogs: [],
      goals: [],
      videos: [],
      saveMood: (e) => set((s) => ({ moods: [...s.moods, { ...e, id: uid(), day: dayKey(), at: Date.now() }] })),
      removeMood: (id) => set((s) => ({ moods: s.moods.filter((m) => m.id !== id) })),
      saveJournal: (e) => {
        const id = e.id ?? uid();
        set((s) => {
          const existing = s.journal.find((j) => j.id === id);
          const entry: JournalEntry = { reflection: null, at: Date.now(), ...existing, ...e, id };
          return { journal: existing ? s.journal.map((j) => (j.id === id ? entry : j)) : [entry, ...s.journal] };
        });
        return id;
      },
      setReflection: (id, reflection) => set((s) => ({ journal: s.journal.map((j) => (j.id === id ? { ...j, reflection } : j)) })),
      removeJournal: (id) => set((s) => ({ journal: s.journal.filter((j) => j.id !== id) })),
      logExercise: (exerciseId, helpful = null) => set((s) => ({ exerciseLogs: [...s.exerciseLogs, { id: uid(), exerciseId, at: Date.now(), helpful }] })),
      addGoal: (text) => set((s) => (text.trim() ? { goals: [...s.goals, { id: uid(), text: text.trim(), createdAt: Date.now(), doneAt: null }] } : s)),
      toggleGoal: (id) => set((s) => ({ goals: s.goals.map((g) => (g.id === id ? { ...g, doneAt: g.doneAt ? null : Date.now() } : g)) })),
      removeGoal: (id) => set((s) => ({ goals: s.goals.filter((g) => g.id !== id) })),
      saveVideo: (v) => set((s) => (s.videos.some((x) => x.id === v.id) ? s : { videos: [{ ...v, savedAt: Date.now() }, ...s.videos] })),
      removeVideo: (id) => set((s) => ({ videos: s.videos.filter((v) => v.id !== id) })),
      clear: () => set({ moods: [], journal: [], exerciseLogs: [], goals: [], videos: [] }),
    }),
    { name: 'confie.wellbeing', storage: deviceStorage, version: 1 },
  ),
);

export const todaysMood = (moods: MoodEntry[]) => {
  const today = dayKey();
  return [...moods].reverse().find((m) => m.day === today) ?? null;
};
