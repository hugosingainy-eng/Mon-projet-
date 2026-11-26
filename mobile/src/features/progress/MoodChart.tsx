import React from 'react';
import { View } from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';
import Svg, { Circle, Line } from 'react-native-svg';

import { MOOD_LABELS } from '@/content/modes';
import { space, useColors } from '@/theme';
import { Txt } from '@/ui';

import { shortDate, type DayPoint } from './stats';

const H = 132;
const PAD = 10;

// Courbe discrète de l'humeur : un point par jour noté, rien pour les jours sans note.
export function MoodChart({ days }: { days: DayPoint[] }) {
  const c = useColors();
  const [w, setW] = React.useState(0);
  const n = days.length;
  const x = (i: number) => PAD + (n > 1 ? (i * (w - 2 * PAD)) / (n - 1) : 0);
  const y = (mood: number) => PAD + ((5 - mood) * (H - 2 * PAD)) / 4;
  const noted = days.filter((d) => d.entry).length;
  const summary = `Humeur des ${n} derniers jours : ${noted} ${noted > 1 ? 'jours notés' : 'jour noté'}. `
    + days.filter((d) => d.entry).map((d) => `${shortDate(d.date)}, ${MOOD_LABELS[d.entry!.mood - 1].toLowerCase()}`).join(' ; ');

  return (
    <View style={{ gap: space.sm }}>
      <View style={{ flexDirection: 'row', gap: space.md }}>
        <View style={{ height: H, justifyContent: 'space-between', paddingVertical: 2 }}>
          <Txt variant="caption" color="textMuted">{MOOD_LABELS[4]}</Txt>
          <Txt variant="caption" color="textMuted">{MOOD_LABELS[2]}</Txt>
          <Txt variant="caption" color="textMuted">{MOOD_LABELS[0]}</Txt>
        </View>
        <View
          style={{ flex: 1, height: H }}
          onLayout={(e) => setW(e.nativeEvent.layout.width)}
          accessible
          accessibilityRole="image"
          accessibilityLabel={summary}>
          {w > 0 ? (
            <Animated.View entering={FadeIn.duration(500)}>
              <Svg width={w} height={H}>
                {[1, 3, 5].map((m) => (
                  <Line key={m} x1={PAD} x2={w - PAD} y1={y(m)} y2={y(m)} stroke={c.line} strokeWidth={1} />
                ))}
                {days.map((d, i) => {
                  const next = days[i + 1];
                  if (!d.entry || !next?.entry) return null;
                  return (
                    <Line key={`l-${d.key}`} x1={x(i)} y1={y(d.entry.mood)} x2={x(i + 1)} y2={y(next.entry.mood)} stroke={c.sage} strokeWidth={2} strokeLinecap="round" />
                  );
                })}
                {days.map((d, i) => (d.entry
                  ? <Circle key={d.key} cx={x(i)} cy={y(d.entry.mood)} r={i === n - 1 ? 5.5 : 4.5} fill={i === n - 1 ? c.primary : c.sage} stroke={c.bg} strokeWidth={2} />
                  : null))}
              </Svg>
            </Animated.View>
          ) : null}
        </View>
      </View>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <Txt variant="caption" color="textMuted">{days[0] ? shortDate(days[0].date) : ''}</Txt>
        <Txt variant="caption" color="textMuted">{"Aujourd'hui"}</Txt>
      </View>
    </View>
  );
}
