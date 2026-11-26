import { useState } from 'react';
import { View } from 'react-native';
import Animated, { FadeIn, LinearTransition } from 'react-native-reanimated';

import { Sheet } from '@/features/chat/ModeSheet';
import { confirmAction } from '@/features/profile/confirm';
import { useMemory, type MemoryItem } from '@/store/memory';
import { useSettings } from '@/store/settings';
import { space } from '@/theme';
import { Button, Divider, Empty, Field, Header, IconButton, Row, Screen, SectionTitle, Toggle, Txt } from '@/ui';

const dateOf = (t: number) => new Date(t).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
const SOURCES: Record<MemoryItem['source'], string> = { ia: 'retenu par l\'IA', moi: 'ajouté par toi' };

export default function MemoryScreen() {
  const on = useSettings((s) => s.memory === 'on');
  const items = useMemory((s) => s.items);
  const [draft, setDraft] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const list = [...items].reverse();

  const add = () => {
    if (!draft.trim()) return;
    const id = useMemory.getState().add(draft, 'moi');
    setNote(id ? null : 'C\'est déjà noté.');
    if (id) setDraft('');
  };
  const saveEdit = () => {
    if (editing?.text.trim()) useMemory.getState().edit(editing.id, editing.text);
    setEditing(null);
  };
  const removeOne = (item: MemoryItem) =>
    confirmAction({ title: 'Effacer cet élément ?', message: `« ${item.text} » ne sera plus retenu.`, confirmLabel: 'Effacer', onConfirm: () => useMemory.getState().remove(item.id) });
  const clearAll = () =>
    confirmAction({ title: 'Tout effacer ?', message: 'Tout ce que ton IA a retenu sera supprimé de ton téléphone. C\'est définitif.', confirmLabel: 'Tout effacer', onConfirm: () => useMemory.getState().clear() });

  return (
    <Screen testID="memory">
      <Header title="Mémoire" />
      <View style={{ gap: space.md, marginTop: space.lg }}>
        <Txt variant="title">Ce que mon IA retient</Txt>
        <Txt color="textSoft">
          La mémoire, c'est une courte liste de choses que ton IA garde d'une conversation à l'autre pour mieux te comprendre. Elle est facultative, et elle ne contient rien d'autre que ce que tu vois ici.
        </Txt>
      </View>

      <View style={{ marginTop: space.xl }}>
        <Row icon="brain" title="Mémoire" hint={on ? 'Activée. Cette liste est transmise à l\'IA pendant tes conversations.' : 'Désactivée. Rien n\'est retenu ni transmis.'} right={<Toggle label="Mémoire" value={on} onChange={(v) => useSettings.getState().set({ memory: v ? 'on' : 'off' })} />} />
        <Divider />
      </View>

      <View style={{ marginTop: space.xl, gap: space.md }}>
        <Field label="Ajouter quelque chose toi-même" value={draft} onChangeText={(t) => { setDraft(t); setNote(null); }} placeholder="Par exemple : je préfère qu'on me tutoie" maxLength={240} onSubmitEditing={add} returnKeyType="done" testID="memory-input" />
        {note ? <Txt variant="small" color="textSoft">{note}</Txt> : null}
        <Button label="Ajouter" kind="soft" icon="plus" small disabled={!draft.trim()} onPress={add} style={{ alignSelf: 'flex-start' }} testID="memory-add" />
      </View>

      {list.length === 0 ? (
        <Empty title="Rien n'est retenu" text={on ? 'Quand ton IA retiendra quelque chose, tu le verras ici. Tu pourras le corriger ou l\'effacer.' : 'La mémoire est désactivée. Tu peux quand même noter ici ce que tu aimerais qu\'elle sache.'} />
      ) : (
        <>
          <SectionTitle>{list.length > 1 ? `${list.length} éléments` : '1 élément'}</SectionTitle>
          {list.map((item, i) => (
            <Animated.View key={item.id} entering={FadeIn.duration(250)} layout={LinearTransition.duration(200)}>
              {i > 0 ? <Divider /> : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.xs, paddingVertical: space.md }}>
                <View style={{ flex: 1, gap: space.xs }}>
                  <Txt>{item.text}</Txt>
                  <Txt variant="caption" color="textMuted">{dateOf(item.at)} · {SOURCES[item.source]}</Txt>
                </View>
                <IconButton name="edit" size={20} label={`Modifier : ${item.text}`} onPress={() => setEditing({ id: item.id, text: item.text })} />
                <IconButton name="trash" size={20} label={`Effacer : ${item.text}`} onPress={() => removeOne(item)} />
              </View>
            </Animated.View>
          ))}
          <View style={{ marginTop: space.xl }}>
            <Divider />
            <Row icon="trash" title="Tout effacer" danger onPress={clearAll} />
          </View>
        </>
      )}

      <Sheet visible={editing !== null} onClose={() => setEditing(null)} title="Modifier">
        <View style={{ gap: space.lg }}>
          <Field value={editing?.text ?? ''} onChangeText={(text) => setEditing((e) => (e ? { ...e, text } : e))} maxLength={240} autoFocus multiline style={{ minHeight: 96 }} />
          <Button label="Enregistrer" disabled={!editing?.text.trim()} onPress={saveEdit} />
        </View>
      </Sheet>
    </Screen>
  );
}
