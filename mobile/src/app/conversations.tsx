import { router } from 'expo-router';
import { View } from 'react-native';

import { MODES } from '@/content/modes';
import { sortedChats, useChats } from '@/store/chats';
import { useSettings } from '@/store/settings';
import { space } from '@/theme';
import { Button, Divider, Empty, Header, Row, Screen, Txt } from '@/ui';

const when = (t: number) => {
  const d = new Date(t);
  const days = Math.floor((Date.now() - t) / 86400000);
  if (days < 1 && d.getDate() === new Date().getDate()) return `Aujourd'hui, ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`;
  if (days < 7) return d.toLocaleDateString('fr-FR', { weekday: 'long' });
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
};

export default function Conversations() {
  const chats = useChats((s) => s.chats);
  const list = sortedChats(chats).filter((c) => !c.temporary);
  const start = (temporary: boolean) =>
    router.push({ pathname: '/chat/[id]', params: { id: useChats.getState().create({ mode: useSettings.getState().defaultMode, temporary }) } });
  return (
    <Screen testID="conversations" footer={
      <View style={{ gap: space.xs }}>
        <Button label="Nouvelle conversation" onPress={() => start(false)} />
        <Button label="Conversation temporaire" kind="quiet" small onPress={() => start(true)} />
      </View>
    }>
      <Header title="Mes conversations" />
      {list.length === 0 ? (
        <Empty title="Rien pour l'instant" text="Tes conversations apparaîtront ici. Tu pourras les reprendre, les renommer ou les supprimer." />
      ) : (
        <View style={{ marginTop: space.md }}>
          {list.map((c, i) => (
            <View key={c.id}>
              {i > 0 ? <Divider /> : null}
              <Row title={c.title} hint={`${when(c.updatedAt)} · ${MODES.find((m) => m.id === c.mode)?.label}`} onPress={() => router.push({ pathname: '/chat/[id]', params: { id: c.id } })} />
            </View>
          ))}
        </View>
      )}
      <Txt variant="caption" color="textMuted" style={{ marginTop: space.xl }}>Une conversation temporaire n'est ni enregistrée ni mémorisée.</Txt>
    </Screen>
  );
}
