import { dayKey } from '@/lib/storage';
import type { ExerciseLog, MoodEntry } from '@/store/wellbeing';

export type DayPoint = { key: string; date: Date; entry: MoodEntry | null };

// Les n derniers jours, du plus ancien à aujourd'hui, avec la dernière note de chaque jour.
export function lastDays(moods: MoodEntry[], n: number): DayPoint[] {
  const byDay = new Map<string, MoodEntry>();
  for (const m of moods) {
    const prev = byDay.get(m.day);
    if (!prev || m.at >= prev.at) byDay.set(m.day, m);
  }
  const out: DayPoint[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const date = new Date();
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() - i);
    const key = dayKey(date);
    out.push({ key, date, entry: byDay.get(key) ?? null });
  }
  return out;
}

const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

export function weekAverages(moods: MoodEntry[]) {
  const days = lastDays([], 14).map((d) => d.key);
  const prevKeys = new Set(days.slice(0, 7));
  const curKeys = new Set(days.slice(7));
  const cur = moods.filter((m) => curKeys.has(m.day));
  const prev = moods.filter((m) => prevKeys.has(m.day));
  return {
    stress: { cur: mean(cur.map((m) => m.stress).filter((n) => n > 0)), prev: mean(prev.map((m) => m.stress).filter((n) => n > 0)) },
    energy: { cur: mean(cur.map((m) => m.energy).filter((n) => n > 0)), prev: mean(prev.map((m) => m.energy).filter((n) => n > 0)) },
  };
}

type Words = { low: string; mid: string; high: string; lower: string; higher: string };
const STRESS: Words = { low: 'plutôt bas', mid: 'modéré', high: 'plutôt élevé', lower: 'un peu plus bas', higher: 'un peu plus haut' };
const ENERGY: Words = { low: 'plutôt basse', mid: 'moyenne', high: 'plutôt bonne', lower: 'un peu plus basse', higher: 'un peu plus haute' };

function phrase(subject: string, w: Words, cur: number | null, prev: number | null): string | null {
  if (cur === null) return null;
  const level = cur < 2.34 ? w.low : cur < 3.67 ? w.mid : w.high;
  const base = `${subject} a été ${level} ces 7 derniers jours`;
  if (prev === null) return `${base}.`;
  const diff = cur - prev;
  if (Math.abs(diff) < 0.5) return `${base}, à peu près comme la semaine d'avant.`;
  return `${base}, ${diff < 0 ? w.lower : w.higher} que la semaine d'avant.`;
}

// Des mots simples plutôt que des chiffres : ce sont des repères, pas des mesures.
export function weekPhrases(moods: MoodEntry[]): string[] {
  const a = weekAverages(moods);
  return [
    phrase('Ton stress', STRESS, a.stress.cur, a.stress.prev),
    phrase('Ton énergie', ENERGY, a.energy.cur, a.energy.prev),
  ].filter((x): x is string => x !== null);
}

export function topEmotions(moods: MoodEntry[], max = 5): { label: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const m of moods) for (const e of m.emotions) counts.set(e, (counts.get(e) ?? 0) + 1);
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, 'fr'))
    .slice(0, max);
}

export function helpfulExercises(logs: ExerciseLog[]): { exerciseId: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const l of logs) if (l.helpful === true) counts.set(l.exerciseId, (counts.get(l.exerciseId) ?? 0) + 1);
  return [...counts.entries()].map(([exerciseId, count]) => ({ exerciseId, count })).sort((a, b) => b.count - a.count);
}

export const times = (n: number) => `${n} fois`;

export function shortDate(d: Date): string {
  try {
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  } catch {
    return `${d.getDate()}/${d.getMonth() + 1}`;
  }
}
