import React from 'react';
import Svg, { Circle, Path } from 'react-native-svg';

import { useColors } from '@/theme';

// Illustration d'accueil : formes organiques et feuillage, dessinés en vectoriel aux couleurs de l'app.
// Direction visuelle explorée avec Canva (visuel de référence : média MAHcBJjjsUw).
export function Botanical({ size = 220 }: { size?: number }) {
  const c = useColors();
  const leaf = (x: number, y: number, r: number, s = 1) =>
    `M${x} ${y} q ${10 * s} ${-14 * s} ${22 * s} ${-12 * s} q ${-4 * s} ${14 * s} ${-22 * s} ${12 * s} Z`.replace(/NaN/g, '0') + ` `;
  const stem = [
    [118, 150, 1], [126, 132, 1], [135, 114, 1], [145, 97, 0.95], [156, 81, 0.9], [167, 66, 0.8],
  ] as const;
  const stemL = [
    [116, 146, 1], [124, 128, 1], [133, 110, 1], [143, 93, 0.95], [154, 78, 0.85],
  ] as const;
  return (
    <Svg width={size} height={size} viewBox="0 0 240 240" accessibilityElementsHidden importantForAccessibility="no">
      <Path d="M52 176c-6-28 18-50 48-46 22 3 34-12 54-6 26 8 34 40 16 60-20 22-58 22-88 18-16-2-27-12-30-26Z" fill={c.sageLight} />
      <Circle cx={150} cy={138} r={30} fill={c.sage} opacity={0.55} />
      <Circle cx={126} cy={152} r={11} fill={c.primary} opacity={0.85} />
      <Path d="M112 168 C 124 130, 146 92, 178 52" stroke={c.primary} strokeWidth={1.6} strokeLinecap="round" fill="none" opacity={0.8} />
      {stem.map(([x, y, s], i) => <Path key={`r${i}`} d={leaf(x, y, 0, s)} fill={c.sage} />)}
      {stemL.map(([x, y, s], i) => (
        <Path key={`l${i}`} d={`M${x} ${y} q ${-16 * s} ${-4 * s} ${-22 * s} ${-16 * s} q ${15 * s} ${-1 * s} ${22 * s} ${16 * s} Z`} fill={c.sage} opacity={0.8} />
      ))}
      <Path d="M70 150 C 66 132, 68 116, 76 100" stroke={c.sage} strokeWidth={1.4} strokeLinecap="round" fill="none" />
      {[[76, 100], [66, 112], [80, 118], [64, 128], [78, 134]].map(([x, y], i) => <Circle key={`b${i}`} cx={x} cy={y} r={6.5} fill={c.sage} opacity={0.65} />)}
    </Svg>
  );
}
