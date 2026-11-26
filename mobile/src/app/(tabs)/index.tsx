import { router } from 'expo-router';
import { useState } from 'react';
import { Platform, Pressable, ScrollView, TextInput, View, type TextStyle } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { MOOD_LABELS, TOPICS, type TopicId } from '@/content/modes';
import { greetingFor } from '@/lib/hydration';
import { sortedChats, useChats } from '@/store/chats';
import { useSettings } from '@/store/settings';
import { todaysMood, useWellbeing } from '@/store/wellbeing';
import { HIT, radius, shadow, space, type, useColors } from '@/theme';
import { Button, Chip, ChipGroup, Icon, IconButton, Screen, Txt, type IconName } from '@/ui';
import { BreathArt, JournalArt, MoodFace, PlantArt, VideoArt } from '@/ui/Illustrations';

const LEVELS = [1, 2, 3, 4, 5] as const;

export default function Home() {
  const c = useColors();
  const { name, defaultMode, prefersVoice } = useSettings();
  const chats = useChats((s) => s.chats);
  const moods = useWellbeing((s) => s.moods);
  const mood = todaysMood(moods);
  const last = sortedChats(chats).find((x) => !x.temporary);
  const [draft, setDraft] = useState('');

  const start = (opts: { topic?: TopicId | null; first?: string; voice?: boolean } = {}) => {
    const id = useChats.getState().create({ mode: defaultMode, topic: opts.topic ?? null });
    // Préférence « conversation vocale » : le bouton principal ouvre directement la voix.
    if (opts.voice ?? (prefersVoice && !opts.topic && !opts.first)) router.push({ pathname: '/voix', params: { id } });
    else router.push({ pathname: '/chat/[id]', params: opts.first ? { id, first: opts.first } : { id } });
  };
  const sendDraft = () => {
    const first = draft.trim();
    setDraft('');
    start(first ? { first } : {});
  };

  return (
    <Screen edges={['top']} testID="home">
      {/* En-tête : qui est là */}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.md, height: 60, marginRight: -space.sm }}>
        <View style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: c.sage, alignItems: 'center', justifyContent: 'center' }}>
          {name ? <Txt variant="bodyMedium" style={{ color: c.onPrimary }}>{name.slice(0, 1).toUpperCase()}</Txt> : <Icon name="leaf" size={20} color={c.onPrimary} />}
        </View>
        <View style={{ flex: 1 }}>
          <Txt variant="caption" color="textMuted">{greetingFor()}</Txt>
          <Txt variant="bodyMedium" numberOfLines={1}>{name || 'Bienvenue'}</Txt>
        </View>
        <IconButton name="history" label="Mes conversations" onPress={() => router.push('/conversations')} />
        <IconButton name="phone" label="Aide urgente" onPress={() => router.push('/aide')} />
      </View>

      {/* Carte principale : la question du jour */}
      <Animated.View entering={FadeInDown.duration(500)} style={{ marginTop: space.md, backgroundColor: c.surfaceAlt, borderRadius: radius.lg + 4, padding: space.xl, overflow: 'hidden' }}>
        <View style={{ position: 'absolute', right: -14, top: -6, opacity: 0.9 }}><PlantArt size={112} /></View>
        <Txt variant="caption" color="textSoft" style={{ marginRight: 96 }}>Prends un moment pour toi</Txt>
        <Txt variant="title" style={{ marginTop: space.xs, marginRight: 76 }}>{"Comment tu te sens aujourd'hui\u00a0?"}</Txt>
        <Txt variant="small" color="textSoft" style={{ marginTop: space.sm, marginRight: 60 }}>Tu peux prendre ton temps. Tu n'as pas besoin de tout expliquer parfaitement.</Txt>
        <View style={[{ flexDirection: 'row', alignItems: 'center', backgroundColor: c.surface, borderRadius: radius.pill, paddingLeft: space.lg, paddingRight: 5, marginTop: space.lg, minHeight: 52 }, shadow]}>
          <TextInput
            testID="home-input"
            accessibilityLabel="Écris ce que tu ressens"
            value={draft}
            onChangeText={setDraft}
            onSubmitEditing={sendDraft}
            returnKeyType="send"
            placeholder="Écris ce que tu ressens…"
            placeholderTextColor={c.textMuted}
            style={[type.body, { flex: 1, color: c.text, minHeight: HIT }, Platform.OS === 'web' && ({ outlineStyle: 'none' } as unknown as TextStyle)]}
          />
          <Pressable testID="home-send" accessibilityRole="button" accessibilityLabel="Envoyer et ouvrir la conversation" onPress={sendDraft} style={({ pressed }) => [{ width: 42, height: 42, borderRadius: 21, backgroundColor: c.primary, alignItems: 'center', justifyContent: 'center' }, pressed && { opacity: 0.8 }]}>
            <Icon name="chevron" size={18} color={c.onPrimary} strokeWidth={2} />
          </Pressable>
        </View>
      </Animated.View>

      {/* Humeur du jour */}
      <Animated.View entering={FadeInDown.delay(100).duration(500)} style={{ marginTop: space.xl }}>
        <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <Txt variant="smallMedium">{mood ? `Aujourd'hui : ${MOOD_LABELS[mood.mood - 1].toLowerCase()}` : 'Ton humeur du moment'}</Txt>
          <Pressable testID="checkin" accessibilityRole="button" accessibilityLabel="Faire le point complet sur mon humeur" hitSlop={10} onPress={() => router.push('/humeur')}>
            <Txt variant="small" color="textSoft">Faire le point</Txt>
          </Pressable>
        </View>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: space.md }} accessibilityRole="radiogroup" accessibilityLabel="Humeur du moment">
          {LEVELS.map((n) => (
            <Pressable key={n} testID={`home-mood-${n}`} accessibilityRole="radio" accessibilityLabel={MOOD_LABELS[n - 1]} accessibilityState={{ checked: mood?.mood === n }} onPress={() => router.push({ pathname: '/humeur', params: { m: String(n) } })} style={({ pressed }) => [{ alignItems: 'center', minWidth: HIT, minHeight: HIT, justifyContent: 'center' }, pressed && { opacity: 0.7 }]}>
              <MoodFace level={n} size={46} selected={mood?.mood === n} />
            </Pressable>
          ))}
        </View>
      </Animated.View>

      {/* Parler */}
      <Animated.View entering={FadeInDown.delay(180).duration(500)} style={{ marginTop: space.xl, gap: space.md }}>
        <View>
          <Txt variant="heading">Je suis là pour t'écouter.</Txt>
          <Txt variant="small" color="textSoft">Par écrit ou à voix haute, à n'importe quelle heure.</Txt>
        </View>
        <Button label="Commencer une conversation" onPress={() => start()} testID="start-chat" />
        <View style={{ flexDirection: 'row', gap: space.md }}>
          <Shortcut icon="wave" label="À voix haute" onPress={() => start({ voice: true })} />
          <Shortcut icon="history" label="Historique" onPress={() => router.push('/conversations')} />
        </View>
        {last ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Reprendre : ${last.title}`} onPress={() => router.push({ pathname: '/chat/[id]', params: { id: last.id } })} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: 36 }, pressed && { opacity: 0.6 }]}>
            <Icon name="chevron" size={14} color={c.textMuted} />
            <Txt variant="small" color="textSoft" numberOfLines={1} style={{ flex: 1 }}>Reprendre : {last.title}</Txt>
          </Pressable>
        ) : null}
      </Animated.View>

      {/* Sujets */}
      <Animated.View entering={FadeInDown.delay(260).duration(500)} style={{ marginTop: space.xl, gap: space.md }}>
        <Txt variant="smallMedium">De quoi veux-tu parler ?</Txt>
        <ChipGroup>{TOPICS.map((t) => <Chip key={t.id} label={t.label} onPress={() => start({ topic: t.id })} />)}</ChipGroup>
      </Animated.View>

      {/* Pour toi */}
      <Animated.View entering={FadeInDown.delay(340).duration(500)} style={{ marginTop: space.xl, gap: space.md }}>
        <Txt variant="smallMedium">Pour toi</Txt>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -space.xl }} contentContainerStyle={{ paddingHorizontal: space.xl, gap: space.md }}>
          <Feature title="Respirer en paix" hint="5 min · guidé" art={<BreathArt size={92} />} tint={c.surfaceAlt} onPress={() => router.push({ pathname: '/exercice/[id]', params: { id: 'coherence' } })} />
          <Feature title="Écrire pour soi" hint="Ton journal privé" art={<JournalArt size={92} />} tint={c.surface} onPress={() => router.push('/ecrire')} />
          <Feature title="Vidéos" hint="Pour aller plus loin" art={<VideoArt size={92} />} tint={c.surfaceAlt} onPress={() => router.push('/videos')} />
          <Feature title="S'ancrer" hint="4 min · les cinq sens" art={<PlantArt size={92} />} tint={c.surface} onPress={() => router.push({ pathname: '/exercice/[id]', params: { id: 'ancrage-54321' } })} />
        </ScrollView>
      </Animated.View>
    </Screen>
  );
}

function Shortcut({ icon, label, onPress }: { icon: IconName; label: string; onPress: () => void }) {
  const c = useColors();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: 52, paddingHorizontal: space.lg, borderRadius: radius.md, backgroundColor: c.surface, borderWidth: 1, borderColor: c.line }, pressed && { opacity: 0.7 }]}>
      <Icon name={icon} size={20} color={c.primary} />
      <Txt variant="small" numberOfLines={1} style={{ flexShrink: 1 }}>{label}</Txt>
    </Pressable>
  );
}

function Feature({ title, hint, art, tint, onPress }: { title: string; hint: string; art: React.ReactNode; tint: string; onPress: () => void }) {
  const c = useColors();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${title}, ${hint}`} onPress={onPress} style={({ pressed }) => [{ width: 148, borderRadius: radius.lg, backgroundColor: tint, borderWidth: 1, borderColor: c.line, padding: space.lg, alignItems: 'center', gap: space.sm }, pressed && { opacity: 0.8 }]}>
      {art}
      <View style={{ alignSelf: 'stretch' }}>
        <Txt variant="smallMedium" numberOfLines={1}>{title}</Txt>
        <Txt variant="caption" color="textMuted" numberOfLines={1}>{hint}</Txt>
      </View>
    </Pressable>
  );
}
