import { router } from 'expo-router';
import { useState } from 'react';
import { Platform, Pressable, ScrollView, TextInput, View, type TextStyle } from 'react-native';
import Animated from 'react-native-reanimated';

import { MOOD_LABELS, TOPICS, type TopicId } from '@/content/modes';
import { greetingFor } from '@/lib/hydration';
import { sortedChats, useChats } from '@/store/chats';
import { useSettings } from '@/store/settings';
import { todaysMood, useWellbeing } from '@/store/wellbeing';
import { alpha, HIT, radius, shadow, shadowSoft, space, type, useColors } from '@/theme';
import { Button, Icon, IconButton, Screen, Txt, type IconName } from '@/ui';
import { BreathArt, JournalArt, MoodFace, PlantArt, VideoArt } from '@/ui/Illustrations';

const LEVELS = [1, 2, 3, 4, 5] as const;
const MOOD_SHORT = ['Très dur', 'Dur', 'Moyen', 'Bien', 'Très bien'] as const;
const TOPIC_ICON: Record<TopicId, IconName> = {
  amour: 'heart', moral: 'leaf', stress: 'breathe', confiance: 'shield', motivation: 'progress', solitude: 'profile', autre: 'plus',
};

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

  // Du sable (difficile) au vert (léger) : la couleur porte l'humeur autant que le visage.
  const moodTint = [alpha(c.accent, 0.42), alpha(c.accent, 0.22), c.surface, c.surfaceAlt, alpha(c.sage, 0.6)];

  return (
    <Screen edges={['top']} testID="home">
      <Animated.View>
        {/* Qui est là */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.md, height: 64, marginRight: -space.sm }}>
          <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: c.primary, alignItems: 'center', justifyContent: 'center' }}>
            {name ? <Txt variant="bodyMedium" style={{ color: c.onPrimary }}>{name.slice(0, 1).toUpperCase()}</Txt> : <Icon name="leaf" size={20} color={c.onPrimary} />}
          </View>
          <View style={{ flex: 1 }}>
            <Txt variant="caption" color="textMuted">{greetingFor()}</Txt>
            <Txt variant="heading" numberOfLines={1}>{name || 'Bienvenue'}</Txt>
          </View>
          <IconButton name="history" label="Mes conversations" color={c.text} onPress={() => router.push('/conversations')} />
          <IconButton name="phone" label="Aide urgente" color={c.text} onPress={() => router.push('/aide')} />
        </View>

        {/* Le bloc principal : une seule entrée, parler */}
        <View style={{ marginTop: space.sm, backgroundColor: c.surfaceAlt, borderRadius: radius.xl, padding: space.xl, overflow: 'hidden' }}>
          <View style={{ position: 'absolute', right: -70, top: -70, width: 220, height: 220, borderRadius: 110, backgroundColor: alpha(c.sage, 0.35) }} />
          <View style={{ position: 'absolute', right: -4, top: 6 }}><PlantArt size={132} /></View>
          <Txt variant="caption" color="textSoft" style={{ marginRight: 120 }}>Prends un moment pour toi</Txt>
          <Txt variant="display" style={{ marginTop: space.xs, marginRight: 96 }}>{"Comment tu te sens aujourd'hui ?"}</Txt>
          <Txt variant="small" color="textSoft" style={{ marginTop: space.md }}>Je suis là pour t'écouter. Tu peux prendre ton temps, tu n'as pas besoin de tout expliquer parfaitement.</Txt>

          <View style={[{ flexDirection: 'row', alignItems: 'center', backgroundColor: c.surface, borderRadius: radius.pill, paddingLeft: space.xl, paddingRight: 6, marginTop: space.lg, minHeight: 56 }, shadow]}>
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
            <Pressable testID="home-send" accessibilityRole="button" accessibilityLabel="Envoyer et ouvrir la conversation" onPress={sendDraft} style={({ pressed }) => [{ width: 44, height: 44, borderRadius: 22, backgroundColor: c.primary, alignItems: 'center', justifyContent: 'center' }, pressed && { opacity: 0.8 }]}>
              <Icon name="send" size={20} color={c.onPrimary} strokeWidth={2} />
            </Pressable>
          </View>

          <Button label="Commencer une conversation" onPress={() => start()} testID="start-chat" style={{ marginTop: space.md }} />
          <Pressable accessibilityRole="button" accessibilityLabel="Parler à voix haute" onPress={() => start({ voice: true })} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.sm, minHeight: HIT, marginTop: space.xs }, pressed && { opacity: 0.6 }]}>
            <Icon name="mic" size={18} color={c.text} />
            <Txt variant="smallMedium">À voix haute</Txt>
          </Pressable>
        </View>

        {last ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Reprendre : ${last.title}`} onPress={() => router.push({ pathname: '/chat/[id]', params: { id: last.id } })} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.md, marginTop: space.md, paddingHorizontal: space.lg, minHeight: 56, borderRadius: radius.md, backgroundColor: c.surface }, shadowSoft, pressed && { opacity: 0.7 }]}>
            <Icon name="history" size={18} color={c.text} />
            <Txt variant="small" numberOfLines={1} style={{ flex: 1 }}>Reprendre : {last.title}</Txt>
            <Icon name="chevron" size={16} color={c.textMuted} />
          </Pressable>
        ) : null}

        {/* Humeur : cinq grandes formes à toucher */}
        <View style={{ marginTop: space.xxl }}>
          <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' }}>
            <Txt variant="heading">{mood ? `Aujourd'hui : ${MOOD_LABELS[mood.mood - 1].toLowerCase()}` : 'Ton humeur du moment'}</Txt>
            <Pressable testID="checkin" accessibilityRole="button" accessibilityLabel="Faire le point complet sur mon humeur" hitSlop={10} onPress={() => router.push('/humeur')}>
              <Txt variant="smallMedium" color="textSoft">Faire le point</Txt>
            </Pressable>
          </View>
          <View style={{ flexDirection: 'row', gap: space.sm, marginTop: space.md }} accessibilityRole="radiogroup" accessibilityLabel="Humeur du moment">
            {LEVELS.map((n) => {
              const on = mood?.mood === n;
              return (
                <Pressable key={n} testID={`home-mood-${n}`} accessibilityRole="radio" accessibilityLabel={MOOD_LABELS[n - 1]} accessibilityState={{ checked: on }} onPress={() => router.push({ pathname: '/humeur', params: { m: String(n) } })}
                  style={({ pressed }) => [{ flex: 1, alignItems: 'center', gap: 6, paddingVertical: space.md, borderRadius: radius.md, backgroundColor: on ? c.primary : moodTint[n - 1], transform: [{ scale: pressed ? 0.95 : 1 }] }]}>
                  <MoodFace level={n} size={36} selected={on} bare />
                  <Txt variant="caption" numberOfLines={1} style={{ color: on ? c.onPrimary : c.text, fontSize: 12 }}>{MOOD_SHORT[n - 1]}</Txt>
                </Pressable>
              );
            })}
          </View>
        </View>

        {/* Sujets : des cases pleines, pas des contours */}
        <View style={{ marginTop: space.xxl }}>
          <Txt variant="heading">De quoi veux-tu parler ?</Txt>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.md }}>
            {TOPICS.map((t) => (
              <Pressable key={t.id} accessibilityRole="button" accessibilityLabel={t.label} onPress={() => start({ topic: t.id })}
                style={({ pressed }) => [{ flexBasis: '47%', flexGrow: 1, flexDirection: 'row', alignItems: 'center', gap: space.md, minHeight: 60, paddingHorizontal: space.md, borderRadius: radius.md, backgroundColor: c.surface }, shadowSoft, pressed && { opacity: 0.75 }]}>
                <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: c.surfaceAlt, alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name={TOPIC_ICON[t.id]} size={19} color={c.primary} />
                </View>
                <Txt variant="smallMedium" style={{ flex: 1 }}>{t.label}</Txt>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Pour toi */}
        <View style={{ marginTop: space.xxl }}>
          <Txt variant="heading">Pour toi</Txt>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -space.xl, marginTop: space.md }} contentContainerStyle={{ paddingHorizontal: space.xl, gap: space.md }}>
            <Feature title="Respirer en paix" hint="5 min, guidé" art={<BreathArt size={104} />} tint={c.surfaceAlt} onPress={() => router.push({ pathname: '/exercice/[id]', params: { id: 'coherence' } })} />
            <Feature title="Vidéos" hint="Pour aller plus loin" art={<VideoArt size={104} />} tint={alpha(c.accent, 0.24)} onPress={() => router.push('/videos')} />
            <Feature title="Écrire pour soi" hint="Ton journal privé" art={<JournalArt size={104} />} tint={c.surfaceAlt} onPress={() => router.push('/ecrire')} />
            <Feature title="S'ancrer" hint="4 min, les cinq sens" art={<PlantArt size={104} />} tint={alpha(c.accent, 0.24)} onPress={() => router.push({ pathname: '/exercice/[id]', params: { id: 'ancrage-54321' } })} />
          </ScrollView>
        </View>
      </Animated.View>
    </Screen>
  );
}

function Feature({ title, hint, art, tint, onPress }: { title: string; hint: string; art: React.ReactNode; tint: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${title}, ${hint}`} onPress={onPress} style={({ pressed }) => [{ width: 164, borderRadius: radius.lg, backgroundColor: tint, padding: space.lg, gap: space.sm, transform: [{ scale: pressed ? 0.97 : 1 }] }]}>
      <View style={{ alignItems: 'center' }}>{art}</View>
      <View>
        <Txt variant="bodyMedium" numberOfLines={1}>{title}</Txt>
        <Txt variant="caption" color="textSoft" numberOfLines={1}>{hint}</Txt>
      </View>
    </Pressable>
  );
}
