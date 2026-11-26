import { router } from 'expo-router';
import React from 'react';
import { KeyboardAvoidingView, Platform, Pressable, View } from 'react-native';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';

import { EMOTIONS, MOOD_LABELS } from '@/content/modes';
import { todaysMood, useWellbeing, type MoodEntry } from '@/store/wellbeing';
import { HIT, radius, space, useColors } from '@/theme';
import { Button, Chip, ChipGroup, Divider, Field, Icon, IconButton, Scale, Screen, Txt } from '@/ui';

const MOODS = [1, 2, 3, 4, 5] as const;
const SLEEP_DEFAULT = 7;
const SLEEP_MAX = 14;

const formatSleep = (h: number) => {
  const whole = Math.floor(h);
  return h % 1 === 0 ? `${whole} h` : `${whole} h 30`;
};

const close = () => (router.canGoBack() ? router.back() : router.replace('/'));

export default function Humeur() {
  const c = useColors();
  const moods = useWellbeing((s) => s.moods);
  const saveMood = useWellbeing((s) => s.saveMood);
  const [existing] = React.useState(() => todaysMood(moods));

  const [mood, setMood] = React.useState<MoodEntry['mood'] | null>(null);
  const [emotions, setEmotions] = React.useState<string[]>([]);
  const [intensity, setIntensity] = React.useState(0); // 0 = non renseigné
  const [stress, setStress] = React.useState(0); // 0 = non renseigné
  const [energy, setEnergy] = React.useState(0); // 0 = non renseigné
  const [sleep, setSleep] = React.useState<number | null>(null);
  const [note, setNote] = React.useState('');

  const toggleEmotion = (e: string) => setEmotions((xs) => (xs.includes(e) ? xs.filter((x) => x !== e) : [...xs, e]));
  const stepSleep = (delta: number) => setSleep((h) => (h === null ? SLEEP_DEFAULT : Math.min(SLEEP_MAX, Math.max(0, h + delta))));

  const save = () => {
    if (mood === null) return;
    saveMood({ mood, emotions, intensity, stress, energy, sleepHours: sleep, note: note.trim() });
    close();
  };

  const stepper = (label: string, onPress: () => void, child: React.ReactNode, disabled?: boolean) => (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        { width: HIT, height: HIT, borderRadius: radius.pill, borderWidth: 1, borderColor: c.line, alignItems: 'center', justifyContent: 'center' },
        { opacity: disabled ? 0.35 : pressed ? 0.6 : 1 },
      ]}>
      {child}
    </Pressable>
  );

  return (
    <KeyboardAvoidingView testID="mood" style={{ flex: 1, backgroundColor: c.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen footer={<Button label="Enregistrer" testID="mood-save" disabled={mood === null} onPress={save} />}>
        <View style={{ height: 52, flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', marginRight: -space.sm }}>
          <IconButton name="close" label="Fermer" onPress={close} testID="mood-close" />
        </View>

        <Animated.View entering={FadeInDown.duration(450)} style={{ gap: space.sm, marginTop: space.lg }}>
          <Txt variant="title">{'Comment tu te sens, là, maintenant ?'}</Txt>
          <Txt color="textSoft">
            {existing
              ? `Tu as déjà fait le point aujourd'hui (${MOOD_LABELS[existing.mood - 1].toLowerCase()}). Si quelque chose a bougé depuis, tu peux en refaire un.`
              : 'Pas de bonne ou de mauvaise réponse. Choisis ce qui s\'en approche le plus.'}
          </Txt>
        </Animated.View>

        <Animated.View entering={FadeInDown.delay(100).duration(450)} accessibilityRole="radiogroup" accessibilityLabel="Humeur générale" style={{ flexDirection: 'row', marginTop: space.xxl, marginHorizontal: -space.xs }}>
          {MOODS.map((n) => {
            const selected = mood === n;
            return (
              <Pressable
                key={n}
                testID={`mood-${n}`}
                accessibilityRole="radio"
                accessibilityLabel={MOOD_LABELS[n - 1]}
                accessibilityState={{ selected, checked: selected }}
                onPress={() => setMood(n)}
                style={({ pressed }) => [{ flex: 1, alignItems: 'center', gap: space.sm, paddingVertical: space.sm, minHeight: 88 }, pressed && { opacity: 0.7 }]}>
                <View style={{ width: HIT, height: HIT, borderRadius: HIT / 2, borderWidth: 1, alignItems: 'center', justifyContent: 'center', borderColor: selected ? c.sage : c.line, backgroundColor: selected ? c.surfaceAlt : 'transparent' }}>
                  {/* Le point grandit avec l'humeur : un repère visuel, sans visage ni jugement. */}
                  <View style={{ width: 6 + n * 4, height: 6 + n * 4, borderRadius: radius.pill, backgroundColor: selected ? c.primary : c.sage }} />
                </View>
                <Txt variant="caption" color={selected ? 'text' : 'textMuted'} center numberOfLines={2}>{MOOD_LABELS[n - 1]}</Txt>
              </Pressable>
            );
          })}
        </Animated.View>

        {mood !== null ? (
          <Animated.View entering={FadeIn.duration(400)} style={{ marginTop: space.xl, gap: space.xxl }}>
            <View style={{ gap: space.lg }}>
              <Divider />
              <Txt variant="small" color="textMuted">{"C'est noté. La suite est facultative, tu peux enregistrer dès maintenant."}</Txt>
            </View>

            <View style={{ gap: space.md }}>
              <Txt variant="smallMedium">{'Qu\'est-ce qui est présent ?'}</Txt>
              <ChipGroup>
                {EMOTIONS.map((e) => <Chip key={e} label={e} selected={emotions.includes(e)} onPress={() => toggleEmotion(e)} />)}
              </ChipGroup>
            </View>

            <Scale label="Intensité de ce que tu ressens" value={intensity} onChange={setIntensity} low="Légère" high="Très forte" />
            <Scale label="Stress" value={stress} onChange={setStress} low="Détendu·e" high="Très tendu·e" />
            <Scale label="Énergie" value={energy} onChange={setEnergy} low="À plat" high="En forme" />

            <View style={{ gap: space.sm }}>
              <Txt variant="smallMedium">Sommeil de la nuit dernière</Txt>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.lg }}>
                {stepper('Une demi-heure de sommeil en moins', () => stepSleep(-0.5), <View style={{ width: 12, height: 1.6, borderRadius: 1, backgroundColor: c.textSoft }} />, sleep === 0)}
                <Txt variant="bodyMedium" color={sleep === null ? 'textMuted' : 'text'} center style={{ minWidth: 120 }} accessibilityLiveRegion="polite">
                  {sleep === null ? 'Non renseigné' : formatSleep(sleep)}
                </Txt>
                {stepper('Une demi-heure de sommeil en plus', () => stepSleep(0.5), <Icon name="plus" size={18} color={c.textSoft} />, sleep === SLEEP_MAX)}
                <View style={{ flex: 1 }} />
                {sleep !== null ? <Button label="Effacer" kind="quiet" small onPress={() => setSleep(null)} style={{ paddingHorizontal: space.sm }} /> : null}
              </View>
            </View>

            <Field label="Un mot sur ta journée" placeholder="Ce qui a compté, ce qui a pesé…" multiline value={note} onChangeText={setNote} style={{ minHeight: 110 }} />
          </Animated.View>
        ) : null}
      </Screen>
    </KeyboardAvoidingView>
  );
}
