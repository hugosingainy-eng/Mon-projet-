import { useEffect, useState } from 'react';
import { View } from 'react-native';
import Animated, { cancelAnimation, Easing, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';

import type { Exercise } from '@/content/exercises';
import { space, useColors } from '@/theme';
import { Button, Txt } from '@/ui';

import { BREATH_REST_SCALE, breathPhases } from './format';

const SIZE = 248;
const LEAD_IN = 3; // secondes pour s'installer avant le premier cycle

/**
 * Respiration guidée : un cercle qui grandit à l'inspiration et se resserre à l'expiration,
 * au rythme exact de l'exercice. `onEnd` est appelé à la fin des cycles ou à l'arrêt.
 */
export function BreathGuide({ breath, onEnd }: { breath: NonNullable<Exercise['breath']>; onEnd: () => void }) {
  const c = useColors();
  const phases = breathPhases(breath);
  const cycleSeconds = phases.reduce((sum, p) => sum + p.seconds, 0);
  // Une seule horloge, calée sur l'heure réelle pour ne pas dériver : tout le reste en découle.
  const [elapsed, setElapsed] = useState(0);
  const scale = useSharedValue(BREATH_REST_SCALE);

  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 250);
    return () => clearInterval(t);
  }, []);

  const started = elapsed >= LEAD_IN;
  const total = Math.max(0, elapsed - LEAD_IN);
  const finished = total >= cycleSeconds * breath.cycles;
  const cycle = Math.min(breath.cycles, Math.floor(total / cycleSeconds) + 1);
  let offset = total % cycleSeconds;
  let index = 0;
  while (index < phases.length - 1 && offset >= phases[index].seconds) { offset -= phases[index].seconds; index += 1; }
  const phase = phases[index];
  const left = started ? phase.seconds - offset : LEAD_IN - elapsed;

  // À chaque nouvelle phase, le cercle rejoint sa taille en douceur, sur toute la durée de la phase.
  useEffect(() => {
    if (!started || finished) return;
    scale.value = withTiming(phase.scale, { duration: phase.seconds * 1000, easing: Easing.inOut(Easing.sin) });
  }, [started, finished, index, cycle, phase.scale, phase.seconds, scale]);

  useEffect(() => { if (finished) onEnd(); }, [finished, onEnd]);

  useEffect(() => () => cancelAnimation(scale), [scale]);

  const circle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const word = started ? phase.word : 'Installe-toi';

  return (
    <Animated.View style={{ flex: 1 }} testID="breath-guide">
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.xxl }}>
        <View style={{ width: SIZE, height: SIZE, alignItems: 'center', justifyContent: 'center' }}>
          <View style={{ position: 'absolute', width: SIZE, height: SIZE, borderRadius: SIZE / 2, borderWidth: 1, borderColor: c.line }} />
          <Animated.View style={[{ position: 'absolute', width: SIZE, height: SIZE, borderRadius: SIZE / 2, backgroundColor: c.sageLight, borderWidth: 1, borderColor: c.sage }, circle]} />
          <View accessible accessibilityLiveRegion="polite" accessibilityLabel={word} style={{ alignItems: 'center' }}>
            <Txt variant="title">{word}</Txt>
            <Txt variant="small" color="textSoft">{left}</Txt>
          </View>
        </View>
        <Txt variant="small" color="textMuted">{started ? `Cycle ${cycle} sur ${breath.cycles}` : 'On commence dans un instant.'}</Txt>
      </View>
      <View style={{ gap: space.md, paddingBottom: space.lg }}>
        <Txt variant="caption" color="textMuted" center>Si tu ressens une gêne, arrête et respire normalement.</Txt>
        <Button label="Arrêter" kind="soft" icon="stop" onPress={onEnd} testID="breath-stop" />
      </View>
    </Animated.View>
  );
}
