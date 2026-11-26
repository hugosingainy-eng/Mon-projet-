import { router } from 'expo-router';
import React from 'react';
import { Pressable, View } from 'react-native';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';

import { exerciseById } from '@/content/exercises';
import { MoodChart } from '@/features/progress/MoodChart';
import { helpfulExercises, lastDays, times, topEmotions, weekPhrases } from '@/features/progress/stats';
import { todaysMood, useWellbeing } from '@/store/wellbeing';
import { HIT, radius, space, useColors } from '@/theme';
import { Button, Divider, Empty, Field, Icon, IconButton, Row, Screen, SectionTitle, Txt } from '@/ui';

export default function Progres() {
  const c = useColors();
  const moods = useWellbeing((s) => s.moods);
  const exerciseLogs = useWellbeing((s) => s.exerciseLogs);
  const journalCount = useWellbeing((s) => s.journal.length);
  const goals = useWellbeing((s) => s.goals);
  const addGoal = useWellbeing((s) => s.addGoal);
  const toggleGoal = useWellbeing((s) => s.toggleGoal);
  const removeGoal = useWellbeing((s) => s.removeGoal);
  const [draft, setDraft] = React.useState('');

  const days = lastDays(moods, 14);
  const hasRecent = days.some((d) => d.entry);
  const phrases = weekPhrases(moods);
  const emotions = topEmotions(moods);
  const helped = helpfulExercises(exerciseLogs)
    .map((h) => ({ ...h, title: exerciseById(h.exerciseId)?.title }))
    .filter((h): h is typeof h & { title: string } => !!h.title);
  const doneToday = !!todaysMood(moods);
  const nExo = exerciseLogs.length;

  const submitGoal = () => {
    if (!draft.trim()) return;
    addGoal(draft);
    setDraft('');
  };

  return (
    <Screen edges={['top']} testID="progress">
      <Animated.View entering={FadeInDown.duration(450)} style={{ marginTop: space.xxl, gap: space.sm }}>
        <Txt variant="display">Ton chemin</Txt>
        <Txt color="textSoft">{"Quelques repères pour voir d'où tu viens, à ton rythme."}</Txt>
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(100).duration(450)}>
        <SectionTitle>Humeur, 14 derniers jours</SectionTitle>
        {moods.length === 0 ? (
          <Empty title="Rien à afficher pour l'instant" text="Note ton humeur de temps en temps, et tu verras ici comment elle évolue." />
        ) : (
          <View style={{ gap: space.lg }}>
            {hasRecent
              ? <MoodChart days={days} />
              : <Txt variant="small" color="textSoft">{"Pas de note ces deux dernières semaines. Tu peux reprendre quand tu veux, il n'y a rien à rattraper."}</Txt>}
            {phrases.length > 0 ? (
              <View style={{ gap: space.xs }}>
                {phrases.map((p) => <Txt key={p} variant="small" color="textSoft">{p}</Txt>)}
              </View>
            ) : null}
          </View>
        )}
        <Button
          label={doneToday ? 'Refaire le point' : 'Faire le point du jour'}
          kind="soft"
          icon="heart"
          testID="progress-checkin"
          onPress={() => router.push('/humeur')}
          style={{ marginTop: space.lg }}
        />
      </Animated.View>

      {emotions.length > 0 ? (
        <Animated.View entering={FadeIn.delay(200).duration(450)}>
          <SectionTitle>Ce qui revient le plus</SectionTitle>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm }}>
            {emotions.map((e) => (
              <View key={e.label} style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.sm, paddingHorizontal: space.lg, paddingVertical: space.sm, borderRadius: radius.pill, backgroundColor: c.surfaceAlt }}>
                <Txt variant="small">{e.label}</Txt>
                <Txt variant="caption" color="textSoft">{times(e.count)}</Txt>
              </View>
            ))}
          </View>
        </Animated.View>
      ) : null}

      <Animated.View entering={FadeIn.delay(250).duration(450)}>
        <SectionTitle>Ce que tu as fait pour toi</SectionTitle>
        <Row
          icon="breathe"
          title={nExo === 0 ? 'Aucun exercice pour l\'instant' : `${nExo} ${nExo > 1 ? 'exercices faits' : 'exercice fait'}`}
          hint={nExo === 0
            ? 'Ils t\'attendent dans l\'onglet Exercices, quand tu en as envie.'
            : helped.length > 0
              ? `Ce qui t'a aidé : ${helped.map((h) => (h.count > 1 ? `${h.title} (${times(h.count)})` : h.title)).join(', ')}`
              : 'Après un exercice, tu peux noter s\'il t\'a aidé.'}
        />
        <Divider />
        <Row
          icon="journal"
          title={journalCount === 0 ? 'Aucune page de journal pour l\'instant' : `${journalCount} ${journalCount > 1 ? 'pages de journal' : 'page de journal'}`}
          hint={journalCount === 0 ? 'Quelques lignes suffisent pour commencer.' : 'Écrites pour toi, gardées sur ton appareil.'}
        />
      </Animated.View>

      <Animated.View entering={FadeIn.delay(300).duration(450)}>
        <SectionTitle>Tes objectifs</SectionTitle>
        {goals.length === 0 ? (
          <Txt variant="small" color="textSoft" style={{ marginBottom: space.lg }}>
            {"Un petit pas concret vaut mieux qu'une grande résolution. Tu peux en noter un ici."}
          </Txt>
        ) : (
          <View style={{ marginBottom: space.md }}>
            {goals.map((g) => {
              const done = !!g.doneAt;
              return (
                <View key={g.id} style={{ flexDirection: 'row', alignItems: 'center', minHeight: 52, marginLeft: -space.sm, marginRight: -space.sm }}>
                  <Pressable
                    accessibilityRole="checkbox"
                    accessibilityLabel={g.text}
                    accessibilityState={{ checked: done }}
                    onPress={() => toggleGoal(g.id)}
                    style={({ pressed }) => [{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: HIT, paddingVertical: space.sm }, pressed && { opacity: 0.6 }]}>
                    <View style={{ width: HIT, height: HIT, alignItems: 'center', justifyContent: 'center' }}>
                      <View style={{ width: 24, height: 24, borderRadius: 12, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center', borderColor: done ? c.sage : c.textMuted, backgroundColor: done ? c.sage : 'transparent' }}>
                        {done ? <Icon name="check" size={16} color={c.onPrimary} strokeWidth={2} /> : null}
                      </View>
                    </View>
                    <Txt color={done ? 'textMuted' : 'text'} style={[{ flex: 1 }, done && { textDecorationLine: 'line-through' }]}>{g.text}</Txt>
                  </Pressable>
                  <IconButton name="trash" label={`Supprimer l'objectif : ${g.text}`} size={20} color={c.textMuted} onPress={() => removeGoal(g.id)} />
                </View>
              );
            })}
          </View>
        )}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm }}>
          <View style={{ flex: 1 }}>
            <Field
              placeholder="Un nouvel objectif"
              value={draft}
              onChangeText={setDraft}
              onSubmitEditing={submitGoal}
              returnKeyType="done"
              maxLength={140}
              testID="goal-input"
            />
          </View>
          <IconButton name="plus" label="Ajouter l'objectif" filled color={c.text} onPress={submitGoal} testID="goal-add" />
        </View>
      </Animated.View>

      <Txt variant="caption" color="textMuted" center style={{ marginTop: space.xxxl }}>
        Ce sont tes notes personnelles, pas une évaluation médicale.
      </Txt>
    </Screen>
  );
}
