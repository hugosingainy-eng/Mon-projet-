import React from 'react';
import Svg, { Circle, Path } from 'react-native-svg';

import { useColors } from '@/theme';

// Jeu d'icônes unique, au trait fin, pour garder une interface cohérente.
const PATHS = {
  leaf: ['M12 21V11', 'M12 15c-4.5 0-7-3-7-7.5 4.5 0 7 3 7 7.5Z', 'M12 11c0-4.5 2.5-7.5 7-7.5 0 4.5-2.5 7.5-7 7.5Z'],
  home: ['M4 11.5 12 5l8 6.5', 'M6.5 10v9h11v-9'],
  journal: ['M7 4h10a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z', 'M9 9h6', 'M9 13h4'],
  breathe: ['M12 20c4.4 0 8-3.6 8-8s-3.6-8-8-8-8 3.6-8 8 3.6 8 8 8Z', 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z'],
  progress: ['M5 19V13', 'M10 19V8', 'M15 19v-8', 'M20 19V5'],
  profile: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z', 'M5 20c.8-3.2 3.6-5 7-5s6.2 1.8 7 5'],
  back: ['M14.5 6 8.5 12l6 6'],
  chevron: ['m9.5 6 6 6-6 6'],
  close: ['M6.5 6.5 17.5 17.5', 'M17.5 6.5 6.5 17.5'],
  send: ['M12 19V5', 'm6 11 6-6 6 6'],
  mic: ['M12 15a3 3 0 0 0 3-3V7a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z', 'M6.5 11.5a5.5 5.5 0 0 0 11 0', 'M12 17v3'],
  micOff: ['M9 9v3a3 3 0 0 0 4.6 2.5', 'M15 11V7a3 3 0 0 0-5.7-1.3', 'M6.5 11.5a5.5 5.5 0 0 0 8.6 4.5', 'M12 17v3', 'M4 4l16 16'],
  wave: ['M4 12v0', 'M8 9v6', 'M12 5v14', 'M16 9v6', 'M20 12v0'],
  plus: ['M12 5v14', 'M5 12h14'],
  minus: ['M5 12h14'],
  more: ['M6 12h.01', 'M12 12h.01', 'M18 12h.01'],
  history: ['M4.5 12a7.5 7.5 0 1 0 2.4-5.5', 'M4.5 5v3.5H8', 'M12 8.5V12l2.5 1.5'],
  play: ['M9 6.5v11l9-5.5-9-5.5Z'],
  stop: ['M8 8h8v8H8Z'],
  bookmark: ['M7.5 4.5h9v15l-4.5-3.5-4.5 3.5v-15Z'],
  trash: ['M5 7.5h14', 'M9.5 7.5V5h5v2.5', 'M7.5 7.5l.7 11.5h7.6l.7-11.5'],
  edit: ['M5 19h3.5L19 8.5 15.5 5 5 15.5V19Z'],
  check: ['m5.5 12.5 4.5 4.5 8.5-10'],
  shield: ['M12 4 5.5 6.5v5c0 4 2.8 7 6.5 8.5 3.7-1.5 6.5-4.5 6.5-8.5v-5L12 4Z'],
  brain: ['M12 19a7 7 0 1 0-6.2-3.8L5 19l3.9-.9A7 7 0 0 0 12 19Z', 'M9.5 11.5h5', 'M9.5 14h3'],
  heart: ['M12 19.5s-7-4.3-7-9.5a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.2-7 9.5-7 9.5Z'],
  video: ['M4.5 7.5h10v9h-10Z', 'm14.5 10.5 5-2.5v8l-5-2.5'],
  moon: ['M19 14.5A7.5 7.5 0 0 1 9.5 5 7.5 7.5 0 1 0 19 14.5Z'],
  bell: ['M7 16.5V11a5 5 0 0 1 10 0v5.5l1.5 1.5h-13L7 16.5Z', 'M10.5 20.5h3'],
  phone: ['M7 4.5h3l1.5 4-2 1.5a10 10 0 0 0 4.5 4.5l1.5-2 4 1.5v3a1.5 1.5 0 0 1-1.6 1.5C10.7 18.4 5.6 13.3 5.5 6.1A1.5 1.5 0 0 1 7 4.5Z'],
  sliders: ['M4 8h9', 'M17 8h3', 'M4 16h3', 'M11 16h9'],
  text: ['M5 7h14', 'M5 12h14', 'M5 17h9'],
  download: ['M12 4.5v10', 'm7.5 10.5 4.5 4.5 4.5-4.5', 'M5 19.5h14'],
  target: ['M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z', 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z'],
  clock: ['M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z', 'M12 8v4.5l3 1.5'],
  lock: ['M7 11h10v8.5H7Z', 'M9 11V8a3 3 0 0 1 6 0v3'],
} as const;

const DOTS: Partial<Record<keyof typeof PATHS, [number, number][]>> = {
  sliders: [[15, 8], [9, 16]],
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 22, color, strokeWidth = 1.6 }: { name: IconName; size?: number; color?: string; strokeWidth?: number }) {
  const c = useColors();
  const stroke = color ?? c.sage;
  const heavy = name === 'more' || name === 'wave';
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" accessibilityElementsHidden importantForAccessibility="no">
      {PATHS[name].map((d) => (
        <Path key={d} d={d} stroke={stroke} strokeWidth={heavy ? strokeWidth + 0.8 : strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
      ))}
      {DOTS[name]?.map(([cx, cy]) => <Circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={2} stroke={stroke} strokeWidth={strokeWidth} fill="none" />)}
    </Svg>
  );
}
