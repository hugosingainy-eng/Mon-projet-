import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import Animated from 'react-native-reanimated';

import { exerciseById, type Exercise } from '@/content/exercises';
import { BreathGuide } from '@/features/exercises/BreathGuide';
import { breathPhases, formatMinutes } from '@/features/exercises/format';
import { useWellbeing } from '@/store/wellbeing';
import { radius, space, useColors } from '@/theme';
import { Button, Empty, Header, Screen, Txt } from '@/ui';

type Stage = 'detail' | 'guide' | 'feedback';

const leave = () => (router.canGoBack() ? router.back() : router.replace('/exercices'));

export default function ExerciseScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const exercise = exerciseById(String(id ?? ''));
  const [stage, setStage] = useState<Stage>('detail');

  if (!exercise) {
    return (
      <Screen testID="exercise" footer={<Button label="Voir tous les exercices" kind="soft" onPress={() => router.replace('/exercices')} />}>
        <Header />
        <Empty title="Exercice introuvable" text="Cet exercice n'existe pas ou plus. Tu peux en choisir un autre dans la bibliothèque." />
      </Screen>
    );
  }

  if (stage === 'guide') {
    return (
      <Screen testID="exercise" scroll={false}>
        <Header title={exercise.title} onBack={() => setStage('detail')} />
        {exercise.breath
          ? <BreathGuide breath={exercise.breath} onEnd={() => setStage('feedback')} />
          : <StepGuide steps={exercise.steps} onEnd={() => setStage('feedback')} />}
      </Screen>
    );
  }

  if (stage === 'feedback') {
    const answer = (helpful: boolean | null) => { useWellbeing.getState().logExercise(exercise.id, helpful); leave(); };
    return (
      <Screen testID="exercise" scroll={false}>
        <Animated.View style={{ flex: 1, justifyContent: 'center', gap: space.xxl }}>
          <View style={{ gap: space.sm }}>
            <Txt variant="title">Est-ce que ça t'a aidé ?</Txt>
            <Txt color="textSoft">Il n'y a pas de bonne réponse. Ça me permet seulement de te proposer ce qui te convient.</Txt>
          </View>
          <View style={{ gap: space.md }}>
            <Button label="Oui" onPress={() => answer(true)} testID="helpful-yes" />
            <Button label="Pas vraiment" kind="soft" onPress={() => answer(false)} testID="helpful-no" />
            <Button label="Passer" kind="quiet" onPress={() => answer(null)} testID="helpful-skip" />
          </View>
        </Animated.View>
      </Screen>
    );
  }

  return (
    <Screen testID="exercise" footer={<Button label={exercise.breath ? 'Commencer la respiration guidée' : 'Commencer pas à pas'} onPress={() => setStage('guide')} testID="exercise-start" />}>
      <Header />
      <Detail exercise={exercise} />
    </Screen>
  );
}

function Detail({ exercise }: { exercise: Exercise }) {
  const c = useColors();
  const rhythm = exercise.breath
    ? `${breathPhases(exercise.breath).map((p) => `${p.word.toLowerCase()} ${p.seconds} s`).join(' · ')} · ${exercise.breath.cycles} cycles`
    : null;
  return (
    <Animated.View>
      <View style={{ gap: space.sm, marginTop: space.lg }}>
        <Txt variant="caption" color="textMuted">{exercise.category} · {formatMinutes(exercise.minutes)}</Txt>
        <Txt variant="title" accessibilityRole="header">{exercise.title}</Txt>
        <Txt color="textSoft">{exercise.goal}</Txt>
      </View>

      <Section title="Pourquoi ça peut aider">
        <Txt>{exercise.why}</Txt>
      </Section>

      <Section title="Comment faire">
        <View style={{ gap: space.md }}>
          {exercise.steps.map((step, i) => (
            <View key={step} style={{ flexDirection: 'row', gap: space.md }}>
              <Txt variant="bodyMedium" color="sage" style={{ minWidth: 20 }}>{i + 1}</Txt>
              <Txt style={{ flex: 1 }}>{step}</Txt>
            </View>
          ))}
        </View>
        {rhythm ? <Txt variant="small" color="textMuted" style={{ marginTop: space.md }}>Rythme : {rhythm}.</Txt> : null}
      </Section>

      {exercise.limits ? (
        <View style={{ marginTop: space.xxl, padding: space.lg, borderRadius: radius.md, backgroundColor: c.surfaceAlt, gap: space.xs }}>
          <Txt variant="smallMedium">Les limites de cet exercice</Txt>
          <Txt variant="small" color="textSoft">{exercise.limits}</Txt>
        </View>
      ) : null}

      <Txt variant="caption" color="textMuted" style={{ marginTop: space.xl }}>D'où ça vient : {exercise.source}</Txt>
    </Animated.View>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ marginTop: space.xxl, gap: space.md }}>
      <Txt variant="heading" accessibilityRole="header">{title}</Txt>
      {children}
    </View>
  );
}

/** Mode pas à pas : une seule consigne à l'écran, on avance quand on est prêt. */
function StepGuide({ steps, onEnd }: { steps: string[]; onEnd: () => void }) {
  const c = useColors();
  const [index, setIndex] = useState(0);
  const last = index === steps.length - 1;
  return (
    <View style={{ flex: 1 }} testID="step-guide">
      <View accessibilityRole="progressbar" accessibilityLabel={`Étape ${index + 1} sur ${steps.length}`} style={{ flexDirection: 'row', gap: space.xs, marginTop: space.md }}>
        {steps.map((s, i) => <View key={s} style={{ flex: 1, height: 3, borderRadius: radius.pill, backgroundColor: i <= index ? c.sage : c.line }} />)}
      </View>
      <Animated.View key={index} style={{ flex: 1, justifyContent: 'center', gap: space.lg }}>
        <Txt variant="small" color="textMuted">Étape {index + 1} sur {steps.length}</Txt>
        <Txt variant="title">{steps[index]}</Txt>
        <Txt variant="small" color="textSoft">Prends le temps qu'il te faut.</Txt>
      </Animated.View>
      <View style={{ flexDirection: 'row', gap: space.md, paddingBottom: space.lg }}>
        {index > 0 ? <Button label="Précédent" kind="soft" style={{ flex: 1 }} onPress={() => setIndex(index - 1)} testID="step-prev" /> : null}
        <Button label={last ? 'Terminer' : 'Suivant'} style={{ flex: 1 }} onPress={() => (last ? onEnd() : setIndex(index + 1))} testID="step-next" />
      </View>
    </View>
  );
}
