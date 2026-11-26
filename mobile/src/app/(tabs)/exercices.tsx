import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';

import { EXERCISES, type Exercise, type ExerciseCategory } from '@/content/exercises';
import { formatMinutes } from '@/features/exercises/format';
import { useWellbeing } from '@/store/wellbeing';
import { space, useColors } from '@/theme';
import { Chip, Divider, Icon, Screen, Txt, type IconName } from '@/ui';
import { BreathArt, Hero } from '@/ui/Illustrations';

const CATEGORY_ICON: Partial<Record<Exercise['category'], IconName>> = {
  Respiration: 'breathe', Ancrage: 'leaf', Relaxation: 'moon', Stress: 'heart', 'Pensées répétitives': 'brain',
  Réflexion: 'edit', Communication: 'text', 'Confiance en soi': 'shield', Sommeil: 'moon', Objectifs: 'target',
};

// Les catégories, dans l'ordre où elles apparaissent dans la bibliothèque.
const CATEGORIES = EXERCISES.reduce<ExerciseCategory[]>((all, e) => (all.includes(e.category) ? all : [...all, e.category]), []);

export default function Exercises() {
  const [category, setCategory] = useState<ExerciseCategory | null>(null);
  const logs = useWellbeing((s) => s.exerciseLogs);
  const helped = new Set(logs.filter((l) => l.helpful).map((l) => l.exerciseId));
  const groups = (category ? [category] : CATEGORIES).map((name) => ({ name, items: EXERCISES.filter((e) => e.category === name) }));

  return (
    <Screen edges={['top']} testID="exercises">
      <Hero caption="À ton rythme" title="Exercices" text="Des techniques simples et connues. Aucune n'est obligatoire, et aucune ne marche pour tout le monde." art={<BreathArt size={104} />} />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled"
        style={{ marginTop: space.xl, marginHorizontal: -space.xl }}
        contentContainerStyle={{ paddingHorizontal: space.xl, gap: space.sm }}>
        <Chip label="Tout" selected={category === null} onPress={() => setCategory(null)} />
        {CATEGORIES.map((name) => <Chip key={name} label={name} selected={category === name} onPress={() => setCategory(category === name ? null : name)} />)}
      </ScrollView>

      <Animated.View key={category ?? 'tout'} entering={FadeIn.duration(400)} style={{ marginTop: space.md }}>
        {groups.map((g) => (
          <View key={g.name} style={{ marginTop: space.xl }}>
            <Txt variant="smallMedium" color="textMuted" accessibilityRole="header" style={{ marginBottom: space.xs }}>{g.name}</Txt>
            {g.items.map((e, i) => (
              <View key={e.id}>
                {i > 0 ? <Divider /> : null}
                <ExerciseRow exercise={e} helped={helped.has(e.id)} />
              </View>
            ))}
          </View>
        ))}
      </Animated.View>

      <Txt variant="caption" color="textMuted" style={{ marginTop: space.xxl }}>
        Ces exercices peuvent aider au quotidien. Ils ne remplacent ni un suivi médical ni un accompagnement psychologique.
      </Txt>
    </Screen>
  );
}

function ExerciseRow({ exercise, helped }: { exercise: Exercise; helped: boolean }) {
  const c = useColors();
  const minutes = formatMinutes(exercise.minutes);
  return (
    <Pressable
      testID={`exercise-${exercise.id}`}
      accessibilityRole="button"
      accessibilityLabel={`${exercise.title}, ${minutes}. ${exercise.goal}`}
      onPress={() => router.push({ pathname: '/exercice/[id]', params: { id: exercise.id } })}
      style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.lg, minHeight: 72, paddingVertical: space.lg }, pressed && { opacity: 0.6 }]}>
      <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: c.surfaceAlt, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name={CATEGORY_ICON[exercise.category] ?? 'leaf'} size={22} color={c.primary} />
      </View>
      <View style={{ flex: 1, gap: space.xs }}>
        <Txt variant="bodyMedium">{exercise.title}</Txt>
        <Txt variant="small" color="textSoft">{exercise.goal}</Txt>
        <Txt variant="caption" color="textMuted">{minutes}{exercise.breath ? ' · guidé' : ''}{helped ? ' · t\'a déjà aidé' : ''}</Txt>
      </View>
      <Icon name="chevron" size={18} color={c.textMuted} />
    </Pressable>
  );
}
