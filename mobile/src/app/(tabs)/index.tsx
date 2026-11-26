import { router } from 'expo-router';
import { Pressable, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { MOOD_LABELS, TOPICS, type TopicId } from '@/content/modes';
import { greetingFor } from '@/lib/hydration';
import { sortedChats, useChats } from '@/store/chats';
import { useSettings } from '@/store/settings';
import { todaysMood, useWellbeing } from '@/store/wellbeing';
import { radius, space, useColors } from '@/theme';
import { Button, Card, Chip, ChipGroup, Icon, IconButton, Screen, Txt } from '@/ui';

export default function Home() {
  const c = useColors();
  const { name, defaultMode, prefersVoice } = useSettings();
  const chats = useChats((s) => s.chats);
  const moods = useWellbeing((s) => s.moods);
  const mood = todaysMood(moods);
  const last = sortedChats(chats).find((x) => !x.temporary);

  const start = (topic: TopicId | null = null) => {
    const id = useChats.getState().create({ mode: defaultMode, topic });
    if (prefersVoice && !topic) router.push({ pathname: '/voix', params: { id } });
    else router.push({ pathname: '/chat/[id]', params: { id } });
  };

  return (
    <Screen edges={['top']} testID="home">
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', height: 52, marginRight: -space.sm }}>
        <Icon name="leaf" size={26} strokeWidth={1.4} />
        <View style={{ flexDirection: 'row' }}>
          <IconButton name="history" label="Mes conversations" onPress={() => router.push('/conversations')} />
          <IconButton name="phone" label="Aide urgente" onPress={() => router.push('/aide')} />
        </View>
      </View>

      <Animated.View entering={FadeInDown.duration(500)} style={{ marginTop: space.xl, gap: space.sm }}>
        <Txt variant="display">{greetingFor()}{name ? ` ${name}` : ''},{'\n'}comment tu te sens aujourd'hui ?</Txt>
        <Txt color="textSoft">Tu peux prendre ton temps. Tu n'as pas besoin de tout expliquer parfaitement.</Txt>
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(120).duration(500)}>
        <Card style={{ marginTop: space.xxl, gap: space.lg }}>
          <View style={{ gap: space.xs }}>
            <Txt variant="heading">Je suis là pour t'écouter.</Txt>
            <Txt variant="small" color="textSoft">Par écrit ou à voix haute, à n'importe quelle heure.</Txt>
          </View>
          <Button label="Commencer une conversation" onPress={() => start()} testID="start-chat" />
          {last ? (
            <Pressable accessibilityRole="button" accessibilityLabel={`Reprendre : ${last.title}`} onPress={() => router.push({ pathname: '/chat/[id]', params: { id: last.id } })} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: 36 }, pressed && { opacity: 0.6 }]}>
              <Icon name="history" size={16} color={c.textMuted} />
              <Txt variant="small" color="textSoft" numberOfLines={1} style={{ flex: 1 }}>Reprendre : {last.title}</Txt>
            </Pressable>
          ) : null}
        </Card>
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(220).duration(500)} style={{ marginTop: space.xxl, gap: space.md }}>
        <Txt variant="smallMedium" color="textSoft">De quoi veux-tu parler ?</Txt>
        <ChipGroup>{TOPICS.map((t) => <Chip key={t.id} label={t.label} onPress={() => start(t.id)} />)}</ChipGroup>
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(320).duration(500)} style={{ marginTop: space.xxl }}>
        <Pressable accessibilityRole="button" accessibilityLabel="Faire le point sur mon humeur" testID="checkin" onPress={() => router.push('/humeur')} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.lg, padding: space.lg, borderRadius: radius.lg, backgroundColor: c.surfaceAlt }, pressed && { opacity: 0.8 }]}>
          <Icon name="heart" size={24} color={c.primary} />
          <View style={{ flex: 1 }}>
            <Txt variant="bodyMedium">{mood ? `Aujourd'hui : ${MOOD_LABELS[mood.mood - 1].toLowerCase()}` : 'Faire le point du jour'}</Txt>
            <Txt variant="small" color="textSoft">{mood ? 'Tu peux refaire le point quand tu veux.' : 'Une minute pour noter ton humeur.'}</Txt>
          </View>
          <Icon name="chevron" size={18} color={c.textMuted} />
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Vidéos" onPress={() => router.push('/videos')} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.lg, paddingHorizontal: space.lg, minHeight: 60 }, pressed && { opacity: 0.6 }]}>
          <Icon name="video" size={22} color={c.textSoft} />
          <Txt variant="bodyMedium" style={{ flex: 1 }}>Vidéos pour aller plus loin</Txt>
          <Icon name="chevron" size={18} color={c.textMuted} />
        </Pressable>
      </Animated.View>
    </Screen>
  );
}
