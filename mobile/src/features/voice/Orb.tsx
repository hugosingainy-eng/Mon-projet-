import React, { useEffect } from 'react';
import { Pressable, View } from 'react-native';
import Animated, {
  Easing, cancelAnimation, useAnimatedStyle, useReducedMotion, useSharedValue, withRepeat, withSequence, withTiming,
  type SharedValue,
} from 'react-native-reanimated';

import { useColors } from '@/theme';

export type OrbMode = 'rest' | 'listening' | 'thinking' | 'speaking';

// Durée d'un demi-cycle. Rien de rapide : la respiration d'écoute est proche d'un souffle calme.
const HALF_CYCLE: Record<OrbMode, number> = { rest: 0, listening: 4200, thinking: 1700, speaking: 2600 };
const soft = Easing.inOut(Easing.sin);

/**
 * Le cercle central du mode vocal : trois disques superposés qui bougent lentement.
 * - écoute : respiration ample et lente, qui suit légèrement le volume de la voix ;
 * - réflexion : le cœur pulse doucement, le reste est presque immobile ;
 * - réponse : les couches se croisent et une onde s'éloigne du centre.
 * Les passages d'un état à l'autre sont fondus (les poids `w*`), jamais brusques.
 */
export function Orb({ mode, level, size, onPress, label, disabled }: {
  mode: OrbMode;
  level: SharedValue<number>; // volume de la voix, 0 à 1
  size: number;
  onPress?: () => void;
  label: string;
  disabled?: boolean;
}) {
  const c = useColors();
  const still = useReducedMotion();
  const t = useSharedValue(0); // va-et-vient 0 → 1 → 0
  const wave = useSharedValue(0); // onde 0 → 1, en boucle
  const wListen = useSharedValue(0);
  const wThink = useSharedValue(0);
  const wSpeak = useSharedValue(0);

  useEffect(() => {
    const blend = { duration: 700, easing: soft };
    wListen.set(withTiming(mode === 'listening' ? 1 : 0, blend));
    wThink.set(withTiming(mode === 'thinking' ? 1 : 0, blend));
    wSpeak.set(withTiming(mode === 'speaking' ? 1 : 0, blend));

    cancelAnimation(t);
    cancelAnimation(wave);
    if (still || mode === 'rest') {
      // Mouvements réduits (réglage d'accessibilité) ou pause : le cercle reste posé.
      t.set(withTiming(0, blend));
      wave.set(0);
      return;
    }
    const half = { duration: HALF_CYCLE[mode], easing: soft };
    t.set(withSequence(withTiming(0, { duration: 500, easing: soft }), withRepeat(withTiming(1, half), -1, true)));
    wave.set(mode === 'speaking' ? withRepeat(withTiming(1, { duration: 3600, easing: Easing.out(Easing.quad) }), -1, false) : 0);
  }, [mode, still, t, wave, wListen, wThink, wSpeak]);

  const halo = useAnimatedStyle(() => ({
    opacity: 0.55 + 0.25 * wListen.get() * t.get() + 0.15 * wSpeak.get() * (1 - t.get()),
    transform: [{ scale: 0.88 + t.get() * (0.12 * wListen.get() + 0.03 * wThink.get() + 0.07 * wSpeak.get()) + 0.04 * level.get() * wListen.get() }],
  }));
  const middle = useAnimatedStyle(() => ({
    opacity: 0.4 + 0.15 * wThink.get() * t.get(),
    // En réponse, cette couche va à contretemps du halo : c'est ce qui distingue ce mouvement.
    transform: [{ scale: 0.92 + 0.08 * wListen.get() * t.get() + 0.04 * wThink.get() * t.get() + 0.08 * wSpeak.get() * (1 - t.get()) + 0.07 * level.get() * wListen.get() }],
  }));
  const core = useAnimatedStyle(() => ({
    opacity: 1 - 0.4 * wThink.get() * (1 - t.get()),
    transform: [{ scale: 0.95 + t.get() * (0.03 * wListen.get() + 0.05 * wThink.get() + 0.05 * wSpeak.get()) + 0.05 * level.get() * wListen.get() }],
  }));
  const ripple = useAnimatedStyle(() => ({
    opacity: 0.22 * wSpeak.get() * (1 - wave.get()),
    transform: [{ scale: 0.55 + 0.45 * wave.get() }],
  }));

  const disc = (d: number) => ({ position: 'absolute' as const, width: d, height: d, borderRadius: d / 2 });

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      onPress={onPress}
      style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Animated.View style={[disc(size), { backgroundColor: c.sageLight }, halo]} />
      <Animated.View style={[disc(size), { backgroundColor: c.sage }, ripple]} />
      <Animated.View style={[disc(size * 0.74), { backgroundColor: c.sage }, middle]} />
      <Animated.View style={[disc(size * 0.48), { backgroundColor: c.sage }, core]} />
      {/* Au repos, un point clair au centre : le cercle paraît « fermé », pas éteint. */}
      {mode === 'rest' ? <View style={[disc(size * 0.1), { backgroundColor: c.surface, opacity: 0.7 }]} /> : null}
    </Pressable>
  );
}
