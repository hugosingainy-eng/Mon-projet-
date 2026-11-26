import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { EMOTIONS } from '@/content/modes';
import { RichText } from '@/features/chat/RichText';
import { fullDate, JOURNAL_PROMPTS } from '@/features/journal/format';
import { AiError, streamChat, type ChatContext } from '@/lib/ai';
import { parseReply } from '@/lib/tags';
import { useSettings } from '@/store/settings';
import { useWellbeing } from '@/store/wellbeing';
import { radius, space, useColors } from '@/theme';
import { Button, Chip, ChipGroup, Divider, Empty, Field, Header, IconButton, Row, Screen, Toggle, Txt } from '@/ui';
import { confirmAction } from '@/ui/confirm';

const leave = () => (router.canGoBack() ? router.back() : router.replace('/journal'));

export default function JournalEditor() {
  const c = useColors();
  const params = useLocalSearchParams<{ id?: string }>();
  const [entryId, setEntryId] = useState<string | null>(params.id ? String(params.id) : null);
  const entry = useWellbeing((s) => (entryId ? s.journal.find((j) => j.id === entryId) ?? null : null));
  const missing = !!params.id && !entry;

  const [text, setText] = useState(entry?.text ?? '');
  const [prompt, setPrompt] = useState<string | null>(entry?.prompt ?? null);
  const [emotions, setEmotions] = useState<string[]>(entry?.emotions ?? []);
  const [share, setShare] = useState(entry?.shareWithAi ?? useSettings.getState().shareJournalWithAi);
  const [suggestion, setSuggestion] = useState(() => Math.floor(Math.random() * JOURNAL_PROMPTS.length));
  const [openedAt] = useState(() => Date.now());

  const [streaming, setStreaming] = useState<string | null>(null); // réflexion en cours d'arrivée (texte brut)
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  const clean = text.trim();
  const dirty = !entry
    ? clean.length > 0
    : clean !== entry.text || prompt !== entry.prompt || share !== entry.shareWithAi || emotions.join('|') !== entry.emotions.join('|');

  const toggleEmotion = (e: string) => setEmotions((list) => (list.includes(e) ? list.filter((x) => x !== e) : [...list, e]));

  /** Enregistre la page sur le téléphone et renvoie son identifiant. */
  const persist = (shareWithAi = share) => {
    const id = useWellbeing.getState().saveJournal({ ...(entryId ? { id: entryId } : {}), prompt, text: clean, emotions, shareWithAi });
    setEntryId(id);
    return id;
  };

  const save = () => { if (!clean) return; persist(); leave(); };
  // Rien de ce qui est écrit ne doit se perdre en quittant la page.
  const back = () => { abort.current?.abort(); if (clean && dirty) persist(); leave(); };

  const confirmDelete = () => {
    if (!entryId) return;
    const doIt = () => { abort.current?.abort(); useWellbeing.getState().removeJournal(entryId); leave(); };
    confirmAction({ title: 'Supprimer cette page ?', message: 'Elle sera effacée de ton téléphone.', confirmLabel: 'Supprimer', onConfirm: doIt });
  };

  const reflect = async () => {
    // Garde-fou : rien ne part vers l'IA sans le partage explicite de cette page.
    if (!share || !clean || streaming !== null) return;
    const id = persist(true);
    const settings = useSettings.getState();
    const context: ChatContext = {
      name: settings.name,
      mode: 'comprendre',
      styles: settings.styles?.length ? settings.styles : ['douce'],
      frankness: settings.frankness,
      topic: null,
      voice: false,
      memory: null,
      journal: prompt ? `Question choisie : ${prompt}\n\n${clean}` : clean,
      localTime: new Date().toLocaleString('fr-FR', { weekday: 'long', hour: '2-digit', minute: '2-digit' }),
    };
    const controller = new AbortController();
    abort.current = controller;
    setError(null);
    setStreaming('');
    try {
      const raw = await streamChat(
        [{ role: 'user', content: 'Peux-tu m\'aider à réfléchir à cette page de mon journal ?' }],
        context,
        (full) => setStreaming(full),
        controller.signal,
      );
      if (!controller.signal.aborted) useWellbeing.getState().setReflection(id, raw);
    } catch (e) {
      const aborted = (e as Error)?.name === 'AbortError' || controller.signal.aborted;
      if (!aborted) setError(e instanceof AiError ? e.message : 'Je n\'arrive pas à te répondre pour l\'instant. Ta page est bien enregistrée, tu pourras réessayer plus tard.');
    } finally {
      if (abort.current === controller) { abort.current = null; setStreaming(null); }
    }
  };

  if (missing) {
    return (
      <Screen testID="journal-editor" footer={<Button label="Retour au journal" kind="soft" onPress={leave} />}>
        <Header title="Journal" />
        <Empty title="Page introuvable" text="Cette page n'existe plus sur ce téléphone." />
      </Screen>
    );
  }

  const busy = streaming !== null;
  const raw = busy ? streaming : entry?.reflection ?? null;
  const reflection = raw ? parseReply(raw) : null;

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: c.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} testID="journal-editor">
      <Screen footer={<Button label="Enregistrer" disabled={!clean} onPress={save} testID="journal-save" />}>
        <Header onBack={back} right={entryId ? <IconButton name="trash" label="Supprimer cette page" onPress={confirmDelete} testID="journal-delete" /> : undefined} />

        <View style={{ gap: space.xs, marginTop: space.lg }}>
          <Txt variant="caption" color="textMuted">{fullDate(entry?.at ?? openedAt)}</Txt>
          <Txt variant="title">{entry ? 'Ta page' : 'Qu\'est-ce que tu as envie de déposer ?'}</Txt>
        </View>

        <View style={{ marginTop: space.xl, gap: space.md }}>
          {prompt ? (
            <View style={{ gap: space.xs }}>
              <Txt variant="heading">{prompt}</Txt>
              <Button label="Retirer la question" kind="quiet" small style={{ alignSelf: 'flex-start', paddingHorizontal: 0 }} onPress={() => setPrompt(null)} />
            </View>
          ) : (
            <View style={{ gap: space.sm }}>
              <Txt variant="small" color="textMuted">Une piste, si tu ne sais pas par où commencer</Txt>
              <Txt color="textSoft">{JOURNAL_PROMPTS[suggestion]}</Txt>
              <ChipGroup>
                <Chip label="Partir de cette question" onPress={() => setPrompt(JOURNAL_PROMPTS[suggestion])} />
                <Chip label="Une autre" onPress={() => setSuggestion((i) => (i + 1) % JOURNAL_PROMPTS.length)} />
              </ChipGroup>
            </View>
          )}

          <Field
            testID="journal-text"
            value={text}
            onChangeText={setText}
            multiline
            placeholder="Écris comme ça vient. Personne ne lit par-dessus ton épaule."
            style={{ minHeight: 260, paddingBottom: space.lg }}
          />
        </View>

        <View style={{ marginTop: space.xxl, gap: space.md }}>
          <Txt variant="smallMedium" color="textSoft">Ce que tu ressens (facultatif)</Txt>
          <ChipGroup>{EMOTIONS.map((e) => <Chip key={e} label={e} selected={emotions.includes(e)} onPress={() => toggleEmotion(e)} />)}</ChipGroup>
        </View>

        <View style={{ marginTop: space.xxl }}>
          <Divider />
          <Row
            title="Partager cette page avec l'IA"
            hint={share ? 'Seulement cette page, et seulement si tu demandes une réflexion.' : 'Désactivé : cette page reste sur ton téléphone.'}
            icon="lock"
            right={<Toggle value={share} onChange={setShare} label="Partager cette page avec l'IA" />}
          />
          <Divider />
        </View>

        {share && !reflection && !busy ? (
          <Animated.View style={{ marginTop: space.lg, gap: space.sm }}>
            <Button label="Demander une réflexion à l'IA" kind="soft" icon="leaf" disabled={!clean} onPress={reflect} testID="journal-reflect" />
            <Txt variant="caption" color="textMuted">Le texte de cette page sera envoyé à l'IA pour qu'elle puisse te répondre. Rien d'autre de ton journal n'est transmis.</Txt>
          </Animated.View>
        ) : null}

        {error ? (
          <Txt variant="small" color="warn" accessibilityLiveRegion="polite" style={{ marginTop: space.lg }}>{error}</Txt>
        ) : null}

        {busy || reflection ? (
          <Animated.View testID="journal-reflection" style={{ marginTop: space.xl, padding: space.xl, borderRadius: radius.lg, backgroundColor: c.surfaceAlt, gap: space.md }}>
            <Txt variant="smallMedium" color="textSoft">Réflexion de l'IA</Txt>
            {reflection?.text ? <RichText text={reflection.text} /> : <Txt color="textMuted">Je lis ta page…</Txt>}
            {reflection?.crisis ? <Button label="Voir les numéros d'aide" kind="ghost" small icon="phone" onPress={() => router.push('/aide')} /> : null}
            {busy ? (
              <Button label="Arrêter" kind="quiet" small icon="stop" style={{ alignSelf: 'flex-start', paddingHorizontal: 0 }} onPress={() => abort.current?.abort()} />
            ) : (
              <View style={{ gap: space.sm }}>
                <Txt variant="caption" color="textMuted">Une IA peut se tromper. Garde ce qui te parle, laisse le reste.</Txt>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', columnGap: space.xl }}>
                  {share ? <Button label="Redemander" kind="quiet" small style={{ paddingHorizontal: 0 }} onPress={reflect} /> : null}
                  <Button label="Retirer la réflexion" kind="quiet" small style={{ paddingHorizontal: 0 }} onPress={() => entryId && useWellbeing.getState().setReflection(entryId, null)} testID="journal-reflection-remove" />
                </View>
              </View>
            )}
          </Animated.View>
        ) : null}
      </Screen>
    </KeyboardAvoidingView>
  );
}
