import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import Animated from 'react-native-reanimated';

import { MODES, STYLES, TOPICS, type ModeId, type StyleId, type TopicId } from '@/content/modes';
import { enterApp } from '@/lib/nav';
import { useSettings } from '@/store/settings';
import { space, useColors } from '@/theme';
import { Button, Chip, ChipGroup, Field, Header, Icon, Row, Screen, Toggle, Txt } from '@/ui';

const FRANKNESS = ['Tout en douceur', 'Équilibré', 'Sans filtre'] as const;

export default function Onboarding() {
  const c = useColors();
  const save = useSettings((s) => s.set);
  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [topics, setTopics] = useState<TopicId[]>([]);
  const [styles, setStyles] = useState<StyleId[]>([]);
  const toggleStyle = (id: StyleId) => setStyles((x) => (x.includes(id) ? x.filter((y) => y !== id) : [...x, id]));
  const [frankness, setFrankness] = useState<1 | 2 | 3>(2);
  const [mode, setMode] = useState<ModeId>('ecoute');
  const [memory, setMemory] = useState(false);
  const [voice, setVoice] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [consent, setConsent] = useState(false);

  const toggleTopic = (id: TopicId) => setTopics((t) => (t.includes(id) ? t.filter((x) => x !== id) : [...t, id]));

  const steps = [
    {
      title: 'Comment veux-tu que je t\'appelle ?',
      hint: 'Un prénom ou un pseudonyme. Tu peux aussi ne rien mettre.',
      body: <Field value={name} onChangeText={setName} placeholder="Ton prénom ou un surnom" maxLength={40} autoCapitalize="words" returnKeyType="next" />,
    },
    {
      title: 'De quoi aimerais-tu parler ?',
      hint: 'Choisis ce qui te parle, ou passe cette étape.',
      body: <ChipGroup>{TOPICS.filter((t) => t.id !== 'autre').map((t) => <Chip key={t.id} label={t.label} selected={topics.includes(t.id)} onPress={() => toggleTopic(t.id)} />)}</ChipGroup>,
    },
    {
      title: 'Comment préfères-tu qu\'on te parle ?',
      hint: 'Tu peux en cocher plusieurs. Tu pourras changer à tout moment.',
      body: (
        <View style={{ gap: space.xl }}>
          <View>{STYLES.map((s) => <Row key={s.id} testID={`style-${s.id}`} title={s.label} hint={s.hint} onPress={() => toggleStyle(s.id)} right={<Check on={styles.includes(s.id)} />} />)}</View>
          <View style={{ gap: space.md }}>
            <Txt variant="smallMedium">Niveau de franchise</Txt>
            <ChipGroup>{FRANKNESS.map((f, i) => <Chip key={f} label={f} selected={frankness === i + 1} onPress={() => setFrankness((i + 1) as 1 | 2 | 3)} />)}</ChipGroup>
          </View>
        </View>
      ),
    },
    {
      title: 'En général, tu préfères…',
      hint: 'Je te reposerai la question à chaque conversation.',
      body: <View>{MODES.map((m) => <Row key={m.id} title={m.label} hint={m.hint} onPress={() => setMode(m.id)} right={<Radio on={mode === m.id} />} />)}</View>,
    },
    {
      title: 'Quelques réglages',
      hint: 'Tout est désactivé par défaut. C\'est toi qui décides.',
      body: (
        <View>
          <Row title="Mémoire" hint="Je retiens ce qui compte pour toi d'une conversation à l'autre. Tu peux tout voir et tout effacer." right={<Toggle label="Mémoire" value={memory} onChange={setMemory} />} />
          <Row title="Conversation vocale" hint="Ouvrir le mode vocal par défaut." right={<Toggle label="Conversation vocale" value={voice} onChange={setVoice} />} />
          <Row title="Rappels" hint="Un petit rappel pour prendre de tes nouvelles." right={<Toggle label="Rappels" value={notifications} onChange={setNotifications} />} />
        </View>
      ),
    },
    {
      title: 'Avant de commencer',
      hint: null,
      body: (
        <View style={{ gap: space.lg }}>
          <Txt color="textSoft">Je suis une intelligence artificielle. Je peux t'écouter et t'aider à y voir clair, mais je ne remplace ni un psychologue ni un médecin, et je ne pose pas de diagnostic.</Txt>
          <Txt color="textSoft">Pour te répondre, tes messages sont envoyés de façon sécurisée à un fournisseur d'IA (Anthropic). Ton journal, ton suivi d'humeur et tes exercices restent sur ton téléphone.</Txt>
          <Txt color="textSoft">Si tu es en danger ou en détresse, appelle le 3114 (prévention du suicide, 24h/24) ou le 112.</Txt>
          <Row title="J'ai compris et j'accepte" right={<Toggle label="J'ai compris et j'accepte" value={consent} onChange={setConsent} />} />
        </View>
      ),
    },
  ];

  const last = step === steps.length - 1;
  const finish = () => {
    save({ onboarded: true, consentAt: Date.now(), name: name.trim(), topics, styles: styles.length ? styles : ['douce'], frankness, defaultMode: mode, memory: memory ? 'on' : 'off', prefersVoice: voice, notifications });
    enterApp();
  };
  const current = steps[step];

  return (
    // `key` : chaque étape repart du haut de la page (sinon elle s'affiche déjà défilée, titre coupé).
    <Screen
      key={step}
      testID="onboarding"
      footer={
        <View style={{ gap: space.xs }}>
          <Button label={last ? 'Entrer' : 'Continuer'} disabled={last && !consent} onPress={() => (last ? finish() : setStep(step + 1))} />
          {!last ? <Button label="Passer" kind="quiet" small onPress={() => setStep(step + 1)} /> : null}
        </View>
      }>
      <Header onBack={() => (step === 0 ? router.back() : setStep(step - 1))} />
      <View style={{ flexDirection: 'row', gap: 6, marginTop: space.sm, marginBottom: space.xxl }} accessibilityLabel={`Étape ${step + 1} sur ${steps.length}`}>
        {steps.map((_, i) => <View key={i} style={{ flex: 1, height: 3, borderRadius: 2, backgroundColor: i <= step ? c.sage : c.line }} />)}
      </View>
      <Animated.View key={step} style={{ gap: space.md }}>
        <Txt variant="title">{current.title}</Txt>
        {current.hint ? <Txt variant="small" color="textSoft">{current.hint}</Txt> : null}
        <View style={{ marginTop: space.lg }}>{current.body}</View>
      </Animated.View>
    </Screen>
  );
}

function Check({ on }: { on: boolean }) {
  const c = useColors();
  return (
    <View style={{ width: 24, height: 24, borderRadius: 7, borderWidth: 1.5, borderColor: on ? c.primary : c.textMuted, backgroundColor: on ? c.primary : 'transparent', alignItems: 'center', justifyContent: 'center' }}>
      {on ? <Icon name="check" size={16} color={c.onPrimary} strokeWidth={2.4} /> : null}
    </View>
  );
}

function Radio({ on }: { on: boolean }) {
  const c = useColors();
  return (
    <View style={{ width: 22, height: 22, borderRadius: 11, borderWidth: 1.5, borderColor: on ? c.primary : c.textMuted, alignItems: 'center', justifyContent: 'center' }}>
      {on ? <View style={{ width: 11, height: 11, borderRadius: 6, backgroundColor: c.primary }} /> : null}
    </View>
  );
}
