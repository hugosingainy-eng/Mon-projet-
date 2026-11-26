import { router } from 'expo-router';
import { Pressable, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { entryDate } from '@/features/journal/format';
import { useWellbeing, type JournalEntry } from '@/store/wellbeing';
import { space, useColors } from '@/theme';
import { Button, Divider, Empty, Icon, Screen, Txt } from '@/ui';
import { Hero, JournalArt } from '@/ui/Illustrations';

export default function Journal() {
  const c = useColors();
  const journal = useWellbeing((s) => s.journal);
  const entries = [...journal].sort((a, b) => b.at - a.at);

  return (
    <Screen edges={['top']} testID="journal">
      <Hero caption="Rien que pour toi" title="Journal" text="Un endroit pour poser tes pensées, sans avoir à les expliquer à qui que ce soit." art={<JournalArt size={104} />}>
        <Button label="Écrire" icon="edit" onPress={() => router.push('/ecrire')} testID="journal-write" />
      </Hero>

      {entries.length === 0 ? (
        <Empty title="Ta première page t'attend" text="Quelques lignes suffisent. Tu peux écrire librement ou partir d'une question." />
      ) : (
        <Animated.View style={{ marginTop: space.xl }}>
          {entries.map((e, i) => (
            <View key={e.id}>
              {i > 0 ? <Divider /> : null}
              <EntryRow entry={e} />
            </View>
          ))}
        </Animated.View>
      )}

      <View style={{ flexDirection: 'row', gap: space.sm, marginTop: space.xl, alignItems: 'flex-start' }}>
        <Icon name="lock" size={16} color={c.textMuted} />
        <Txt variant="caption" color="textMuted" style={{ flex: 1 }}>
          Ton journal reste sur ton téléphone. Il n'est jamais partagé avec l'IA, sauf si tu le demandes pour une page précise.
        </Txt>
      </View>
    </Screen>
  );
}

function EntryRow({ entry }: { entry: JournalEntry }) {
  const date = entryDate(entry.at);
  const preview = entry.text.trim();
  const marks = [...entry.emotions, ...(entry.reflection ? ['Réflexion de l\'IA'] : [])];
  return (
    <Pressable
      testID={`journal-entry-${entry.id}`}
      accessibilityRole="button"
      accessibilityLabel={`Page du ${date}. ${preview.slice(0, 80)}`}
      onPress={() => router.push({ pathname: '/ecrire', params: { id: entry.id } })}
      style={({ pressed }) => [{ paddingVertical: space.lg, gap: space.xs, minHeight: 64 }, pressed && { opacity: 0.6 }]}>
      <Txt variant="caption" color="textMuted">{date}</Txt>
      {entry.prompt ? <Txt variant="small" color="textSoft" numberOfLines={1}>{entry.prompt}</Txt> : null}
      <Txt numberOfLines={3}>{preview}</Txt>
      {marks.length ? <Txt variant="small" color="textSoft" numberOfLines={2}>{marks.join(' · ')}</Txt> : null}
    </Pressable>
  );
}
