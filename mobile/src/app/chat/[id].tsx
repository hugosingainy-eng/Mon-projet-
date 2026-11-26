import { router, useLocalSearchParams } from 'expo-router';
import React, { useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, TextInput, View, type TextStyle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withDelay, withRepeat, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { MODES, TOPICS } from '@/content/modes';
import { ModeSheet, Sheet } from '@/features/chat/ModeSheet';
import { RichText } from '@/features/chat/RichText';
import { useChatSession } from '@/features/chat/session';
import { CrisisCard, ExerciseSuggestion, VideoSuggestion } from '@/features/chat/Suggestions';
import { parseReply } from '@/lib/tags';
import { useChats, type Message } from '@/store/chats';
import { useSettings } from '@/store/settings';
import { HIT, MAX_WIDTH, radius, shadow, space, type, useColors } from '@/theme';
import { Button, Chip, ChipGroup, Field, Icon, IconButton, Row, Txt } from '@/ui';
import { goHome } from '@/lib/nav';
import { confirmAction } from '@/ui/confirm';
import { PlantArt } from '@/ui/Illustrations';

const STARTERS = ['Je ne sais pas par où commencer', 'J\'ai besoin de vider mon sac', 'Il s\'est passé quelque chose', 'J\'ai une question que je n\'ose poser à personne'];

export default function ChatScreen() {
  const { id, first } = useLocalSearchParams<{ id: string; first?: string }>();
  const c = useColors();
  const insets = useSafeAreaInsets();
  const session = useChatSession(id);
  const { chat, streaming, busy, error, notes } = session;
  const name = useSettings((s) => s.name);
  const [text, setText] = useState('');
  const [inputHeight, setInputHeight] = useState(HIT);
  const [modeOpen, setModeOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const scroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const sentFirst = useRef(false);

  // Message de départ transmis par l'accueil (accès rapide par sujet).
  useEffect(() => {
    if (first && chat && chat.messages.length === 0 && !sentFirst.current) {
      sentFirst.current = true;
      session.send(first);
    }
  }, [first, chat, session]);

  if (!chat) {
    return (
      <View style={{ flex: 1, backgroundColor: c.bg, alignItems: 'center', justifyContent: 'center', gap: space.lg, padding: space.xl }}>
        <Txt center color="textSoft">Cette conversation n'existe plus.</Txt>
        <Button label="Retour à l'accueil" kind="soft" onPress={goHome} />
      </View>
    );
  }

  const mode = MODES.find((m) => m.id === chat.mode)!;
  const submit = () => {
    if (!text.trim() || busy) return;
    const t = text;
    setText('');
    session.send(t);
  };
  const toBottom = () => requestAnimationFrame(() => scroll.current?.scrollToEnd({ animated: true }));
  const confirmDelete = () => {
    setMenuOpen(false);
    const doIt = () => { goHome(); useChats.getState().remove(chat.id); };
    confirmAction({ title: 'Supprimer cette conversation ?', message: 'Elle sera effacée de ton téléphone.', confirmLabel: 'Supprimer', onConfirm: doIt });
  };

  const empty = chat.messages.length === 0 && !busy;

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: c.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} testID="chat">
      <View style={{ paddingTop: insets.top, width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', paddingHorizontal: space.md }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', height: 56, gap: space.xs }}>
          <IconButton name="back" label="Retour" onPress={() => (router.canGoBack() ? router.back() : goHome())} />
          <Pressable accessibilityRole="button" accessibilityLabel={`Mode : ${mode.label}. Changer`} testID="mode-pill" onPress={() => setModeOpen(true)} style={{ flex: 1, alignItems: 'center', minHeight: HIT, justifyContent: 'center' }}>
            <Txt variant="smallMedium" numberOfLines={1}>{chat.messages.length ? chat.title : 'Nouvelle conversation'}</Txt>
            <Txt variant="caption" color="textMuted">{mode.label}{chat.temporary ? ' · temporaire' : ''} · changer</Txt>
          </Pressable>
          <IconButton name="more" label="Options de la conversation" onPress={() => setMenuOpen(true)} />
        </View>
      </View>

      <ScrollView ref={scroll} style={{ flex: 1 }} onContentSizeChange={toBottom} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}
        contentContainerStyle={{ width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', paddingHorizontal: space.xl, paddingTop: space.lg, paddingBottom: space.xl, gap: space.lg, flexGrow: 1 }}>
        {empty ? (
          <Animated.View style={{ flexGrow: 1, justifyContent: 'center', gap: space.md }}>
            <View style={{ marginLeft: -space.sm, marginBottom: -space.sm }}><PlantArt size={84} /></View>
            <Txt variant="title">{name ? `Je t'écoute, ${name}.` : 'Je t\'écoute.'}</Txt>
            <Txt color="textSoft">Prends ton temps. Tu n'as pas besoin de tout expliquer parfaitement.</Txt>
            <View style={{ gap: space.sm, marginTop: space.lg }} testID="mode-question">
              <Txt variant="smallMedium" color="textSoft">Comment veux-tu que je t'aide aujourd'hui ?</Txt>
              <ChipGroup>{MODES.map((m) => <Chip key={m.id} label={m.label} selected={chat.mode === m.id} onPress={() => useChats.getState().setMode(chat.id, m.id)} />)}</ChipGroup>
            </View>
            <View style={{ gap: space.sm, marginTop: space.lg, alignItems: 'flex-start' }}>
              {(chat.topic && chat.topic !== 'autre' ? [TOPICS.find((t) => t.id === chat.topic)!.starter, STARTERS[0]] : STARTERS.slice(0, 3)).map((s) => (
                <Pressable key={s} accessibilityRole="button" onPress={() => session.send(s)} style={({ pressed }) => [{ backgroundColor: c.surfaceAlt, borderRadius: radius.md, paddingHorizontal: space.lg, minHeight: 46, justifyContent: 'center' }, pressed && { opacity: 0.6 }]}>
                  <Txt variant="small">{s}</Txt>
                </Pressable>
              ))}
            </View>
          </Animated.View>
        ) : null}

        {chat.messages.map((m) => <Bubble key={m.id} message={m} />)}
        {streaming !== null ? (streaming.trim() ? <AiBubble raw={streaming} live /> : <Thinking />) : null}

        {notes.map((n) => (
          <Animated.View key={n.id} style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm, alignSelf: 'flex-start' }}>
            <Icon name="bookmark" size={15} color={c.textMuted} />
            <Txt variant="caption" color="textMuted" style={{ flexShrink: 1 }}>{n.kind === 'retenu' ? `Retenu : ${n.text}` : n.text}</Txt>
            {n.kind === 'retenu' ? <Pressable accessibilityRole="button" hitSlop={10} onPress={() => session.undoNote(n)}><Txt variant="caption" color="textSoft" style={{ textDecorationLine: 'underline' }}>Annuler</Txt></Pressable> : null}
          </Animated.View>
        ))}

        {error ? (
          <View style={{ alignItems: 'center', gap: space.sm, paddingVertical: space.sm }} accessibilityLiveRegion="polite">
            <Txt variant="small" center style={{ color: c.warn, maxWidth: 300 }}>{error.message}</Txt>
            {session.needsReply ? <Button label="Réessayer" kind="ghost" small onPress={() => session.retry()} /> : null}
          </View>
        ) : null}
      </ScrollView>

      <View style={{ width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', paddingHorizontal: space.lg, paddingBottom: Math.max(insets.bottom, space.lg), paddingTop: space.xs }}>
        <View style={[{ flexDirection: 'row', alignItems: 'flex-end', gap: space.sm, backgroundColor: c.surface, borderRadius: 28, paddingLeft: space.xl, paddingRight: space.sm, paddingVertical: space.sm }, shadow]}>
          <TextInput
            testID="composer"
            accessibilityLabel="Ton message"
            value={text}
            onChangeText={setText}
            placeholder="Écris ce que tu as sur le cœur…"
            placeholderTextColor={c.textMuted}
            multiline
            maxLength={6000}
            onContentSizeChange={(e) => setInputHeight(Math.min(140, Math.max(HIT, e.nativeEvent.contentSize.height)))}
            onKeyPress={(e) => {
              const ev = e.nativeEvent as unknown as { key: string; shiftKey?: boolean };
              if (Platform.OS === 'web' && ev.key === 'Enter' && !ev.shiftKey) { e.preventDefault(); submit(); }
            }}
            style={[type.body, { flex: 1, color: c.text, height: text ? inputHeight : HIT, paddingTop: 10, paddingBottom: 8 }, Platform.OS === 'web' && ({ outlineStyle: 'none' } as unknown as TextStyle)]}
          />
          {busy ? (
            <RoundButton icon="stop" label="Arrêter la réponse" onPress={session.stop} />
          ) : text.trim() ? (
            <RoundButton icon="send" label="Envoyer" onPress={submit} testID="send" />
          ) : (
            <RoundButton icon="wave" label="Passer en mode vocal" soft onPress={() => router.push({ pathname: '/voix', params: { id: chat.id, from: 'chat' } })} testID="voice" />
          )}
        </View>
      </View>

      <ModeSheet visible={modeOpen} value={chat.mode} onClose={() => setModeOpen(false)} onPick={(m) => useChats.getState().setMode(chat.id, m)} />
      <Sheet visible={menuOpen} onClose={() => setMenuOpen(false)}>
        <Row icon="plus" title="Nouvelle conversation" onPress={() => { setMenuOpen(false); router.replace({ pathname: '/chat/[id]', params: { id: useChats.getState().create({ mode: useSettings.getState().defaultMode }) } }); }} />
        <Row icon="history" title="Mes conversations" onPress={() => { setMenuOpen(false); router.push('/conversations'); }} />
        {!chat.temporary ? <Row icon="edit" title="Renommer" onPress={() => { setMenuOpen(false); setRenaming(chat.title); }} /> : null}
        <Row icon="phone" title="Aide urgente" onPress={() => { setMenuOpen(false); router.push('/aide'); }} />
        <Row icon="trash" title="Supprimer la conversation" danger onPress={confirmDelete} />
      </Sheet>
      <Sheet visible={renaming !== null} onClose={() => setRenaming(null)} title="Renommer">
        <View style={{ gap: space.lg }}>
          <Field value={renaming ?? ''} onChangeText={setRenaming} maxLength={60} autoFocus />
          <Button label="Enregistrer" onPress={() => { useChats.getState().rename(chat.id, renaming ?? ''); setRenaming(null); }} />
        </View>
      </Sheet>
    </KeyboardAvoidingView>
  );
}

function RoundButton({ icon, label, onPress, soft, testID }: { icon: 'send' | 'stop' | 'wave'; label: string; onPress: () => void; soft?: boolean; testID?: string }) {
  const c = useColors();
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [{ width: HIT, height: HIT, borderRadius: HIT / 2, backgroundColor: soft ? c.surfaceAlt : c.primary, alignItems: 'center', justifyContent: 'center' }, pressed && { opacity: 0.8 }]}>
      <Icon name={icon} size={20} color={soft ? c.primary : c.onPrimary} strokeWidth={2} />
    </Pressable>
  );
}

function Bubble({ message }: { message: Message }) {
  const c = useColors();
  if (message.role === 'assistant') return <AiBubble raw={message.content} />;
  return (
    <Animated.View style={{ alignSelf: 'flex-end', maxWidth: '86%', backgroundColor: c.surfaceAlt, borderRadius: radius.lg, borderBottomRightRadius: 6, paddingHorizontal: space.lg, paddingVertical: space.md }}>
      <Txt>{message.content}</Txt>
    </Animated.View>
  );
}

function AiBubble({ raw, live }: { raw: string; live?: boolean }) {
  const p = parseReply(raw);
  return (
    <Animated.View style={{ alignSelf: 'flex-start', maxWidth: '94%', gap: space.md }} testID={live ? 'ai-live' : 'ai-message'}>
      <RichText text={p.text} />
      {!live && p.crisis ? <CrisisCard /> : null}
      {!live ? p.exercises.map((id) => <ExerciseSuggestion key={id} id={id} />) : null}
      {!live ? p.videos.map((q) => <VideoSuggestion key={q} query={q} />) : null}
    </Animated.View>
  );
}

function Thinking() {
  return (
    <View style={{ flexDirection: 'row', gap: 6, paddingVertical: space.md, alignSelf: 'flex-start' }} accessibilityLabel="Confie réfléchit" testID="thinking">
      {[0, 1, 2].map((i) => <Dot key={i} delay={i * 220} />)}
    </View>
  );
}

function Dot({ delay }: { delay: number }) {
  const c = useColors();
  const o = useSharedValue(0.25);
  useEffect(() => { o.value = withDelay(delay, withRepeat(withTiming(1, { duration: 800 }), -1, true)); }, [delay, o]);
  const style = useAnimatedStyle(() => ({ opacity: o.value, transform: [{ scale: 0.8 + o.value * 0.2 }] }));
  return <Animated.View style={[{ width: 8, height: 8, borderRadius: 4, backgroundColor: c.sage }, style]} />;
}
