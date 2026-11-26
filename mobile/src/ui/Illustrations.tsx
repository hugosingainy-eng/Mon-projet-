import React from 'react';
import Svg, { Circle, Ellipse, Path, Rect } from 'react-native-svg';

import { useColors } from '@/theme';

// Visages d'humeur, au trait, du plus difficile (1) au plus léger (5).
const MOUTHS = ['M8.5 16.2c1.2-1.6 5.8-1.6 7 0', 'M9 15.8c1-.9 5-.9 6 0', 'M9 15.2h6', 'M9 14.6c1 1.2 5 1.2 6 0', 'M8.3 14c1.4 2.6 6 2.6 7.4 0'] as const;

export function MoodFace({ level, size = 34, selected }: { level: 1 | 2 | 3 | 4 | 5; size?: number; selected?: boolean }) {
  const c = useColors();
  const stroke = selected ? c.onPrimary : c.primary;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
      <Circle cx={12} cy={12} r={10.2} fill={selected ? c.primary : c.surface} stroke={selected ? c.primary : c.sage} strokeWidth={1.3} />
      {level === 1 ? (
        <>
          <Path d="M7.6 9.2l2.6 1.1" stroke={stroke} strokeWidth={1.4} strokeLinecap="round" />
          <Path d="M16.4 9.2l-2.6 1.1" stroke={stroke} strokeWidth={1.4} strokeLinecap="round" />
        </>
      ) : level === 5 ? (
        <>
          <Path d="M7.7 10.4c.5-1.1 1.9-1.1 2.4 0" stroke={stroke} strokeWidth={1.4} strokeLinecap="round" fill="none" />
          <Path d="M13.9 10.4c.5-1.1 1.9-1.1 2.4 0" stroke={stroke} strokeWidth={1.4} strokeLinecap="round" fill="none" />
        </>
      ) : (
        <>
          <Circle cx={9} cy={10} r={1.05} fill={stroke} />
          <Circle cx={15} cy={10} r={1.05} fill={stroke} />
        </>
      )}
      <Path d={MOUTHS[level - 1]} stroke={stroke} strokeWidth={1.4} strokeLinecap="round" fill="none" />
    </Svg>
  );
}

type Art = { size?: number };

/** Plante en pot : le calme, la respiration. */
export function PlantArt({ size = 96 }: Art) {
  const c = useColors();
  return (
    <Svg width={size} height={size} viewBox="0 0 96 96" accessibilityElementsHidden importantForAccessibility="no">
      <Ellipse cx={48} cy={84} rx={26} ry={4} fill={c.sage} opacity={0.25} />
      <Path d="M48 62C46 46 40 36 30 28" stroke={c.primary} strokeWidth={1.4} strokeLinecap="round" fill="none" />
      <Path d="M48 62c1-18 6-30 18-40" stroke={c.primary} strokeWidth={1.4} strokeLinecap="round" fill="none" />
      <Path d="M48 62V34" stroke={c.primary} strokeWidth={1.4} strokeLinecap="round" />
      <Path d="M30 28c-10 0-16 6-18 14 9 2 17-3 18-14Z" fill={c.sage} />
      <Path d="M66 22c10-2 17 3 20 11-9 4-18 0-20-11Z" fill={c.sage} />
      <Path d="M48 34c-7-6-8-14-4-22 8 4 10 13 4 22Z" fill={c.sage} opacity={0.75} />
      <Path d="M39 44c-8 1-13-3-15-9 7-3 13 1 15 9Z" fill={c.sage} opacity={0.6} />
      <Path d="M57 42c7 2 13-1 16-7-6-4-13-1-16 7Z" fill={c.sage} opacity={0.6} />
      <Path d="M33 62h30l-3.5 20a3 3 0 0 1-3 2.5h-17a3 3 0 0 1-3-2.5L33 62Z" fill={c.accent} opacity={0.85} />
      <Rect x={31} y={59} width={34} height={6} rx={3} fill={c.accent} />
    </Svg>
  );
}

/** Cercles qui s'ouvrent : respirer, s'apaiser. */
export function BreathArt({ size = 96 }: Art) {
  const c = useColors();
  return (
    <Svg width={size} height={size} viewBox="0 0 96 96" accessibilityElementsHidden importantForAccessibility="no">
      <Circle cx={48} cy={50} r={36} fill={c.sage} opacity={0.18} />
      <Circle cx={48} cy={50} r={25} fill={c.sage} opacity={0.3} />
      <Circle cx={48} cy={50} r={14} fill={c.sage} />
      <Path d="M48 56V44" stroke={c.surface} strokeWidth={1.6} strokeLinecap="round" />
      <Path d="M48 50c-4 0-6-2.5-6-6 4 0 6 2.5 6 6Z" fill={c.surface} />
      <Path d="M48 46c0-3.5 2-6 6-6 0 3.5-2 6-6 6Z" fill={c.surface} />
      <Circle cx={78} cy={22} r={4} fill={c.accent} opacity={0.8} />
      <Circle cx={16} cy={30} r={2.5} fill={c.accent} opacity={0.6} />
    </Svg>
  );
}

/** Carnet et feuille : écrire pour soi. */
export function JournalArt({ size = 96 }: Art) {
  const c = useColors();
  return (
    <Svg width={size} height={size} viewBox="0 0 96 96" accessibilityElementsHidden importantForAccessibility="no">
      <Ellipse cx={48} cy={84} rx={28} ry={4} fill={c.sage} opacity={0.25} />
      <Rect x={22} y={20} width={46} height={60} rx={6} fill={c.surface} stroke={c.sage} strokeWidth={1.4} />
      <Path d="M30 20v60" stroke={c.sage} strokeWidth={1.4} />
      <Path d="M38 36h22M38 46h22M38 56h14" stroke={c.sage} strokeWidth={1.6} strokeLinecap="round" />
      <Path d="M62 78C64 64 70 56 80 50" stroke={c.primary} strokeWidth={1.4} strokeLinecap="round" fill="none" />
      <Path d="M80 50c6 6 6 14 0 20-7-4-8-13 0-20Z" fill={c.sage} />
      <Path d="M68 62c-7-2-10-8-8-15 7 2 10 8 8 15Z" fill={c.sage} opacity={0.7} />
    </Svg>
  );
}

/** Écran et lecture : apprendre en vidéo. */
export function VideoArt({ size = 96 }: Art) {
  const c = useColors();
  return (
    <Svg width={size} height={size} viewBox="0 0 96 96" accessibilityElementsHidden importantForAccessibility="no">
      <Ellipse cx={48} cy={84} rx={28} ry={4} fill={c.sage} opacity={0.25} />
      <Rect x={14} y={24} width={68} height={46} rx={8} fill={c.sage} opacity={0.35} />
      <Circle cx={48} cy={47} r={13} fill={c.primary} />
      <Path d="M44.5 41v12l10-6-10-6Z" fill={c.surface} />
      <Path d="M36 78h24" stroke={c.sage} strokeWidth={2} strokeLinecap="round" />
      <Circle cx={74} cy={32} r={3} fill={c.accent} />
    </Svg>
  );
}
