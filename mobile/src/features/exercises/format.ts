import type { Exercise } from '@/content/exercises';

export const formatMinutes = (minutes: number) => `${minutes} min`;

export type BreathPhase = { key: 'inhale' | 'hold' | 'exhale' | 'holdAfter'; word: string; seconds: number; scale: number };

const SMALL = 0.55;

/** Les temps d'un cycle de respiration, dans l'ordre, avec la taille visée par le cercle. */
export function breathPhases(breath: NonNullable<Exercise['breath']>): BreathPhase[] {
  const phases: BreathPhase[] = [{ key: 'inhale', word: 'Inspire', seconds: breath.inhale, scale: 1 }];
  if (breath.hold) phases.push({ key: 'hold', word: 'Retiens', seconds: breath.hold, scale: 1 });
  phases.push({ key: 'exhale', word: 'Expire', seconds: breath.exhale, scale: SMALL });
  if (breath.holdAfter) phases.push({ key: 'holdAfter', word: 'Retiens', seconds: breath.holdAfter, scale: SMALL });
  return phases;
}

export const BREATH_REST_SCALE = SMALL;
