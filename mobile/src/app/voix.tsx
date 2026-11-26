import * as Haptics from 'expo-haptics';
import { router, useLocalSearchParams } from 'expo-router';
import React, { useRef, useState } from 'react';
import { Linking, Platform, Pressable, ScrollView, View, useWindowDimensions } from 'react-native';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Orb, type OrbMode } from '@/features/voice/Orb';
import { useVoiceConversation, type VoicePhase } from '@/features/voice/useVoiceConversation';
import { useSettings } from '@/store/settings';
import { HIT, MAX_WIDTH, space, useColors } from '@/theme';
import { Button, Icon, Toggle, Txt, type IconName } from '@/ui';
import { goHome } from '@/lib/nav';

// Le mode vocal : une conversation mains libres, plein écran.
//
// Ce qu'il faut savoir (et ne pas promettre) :
// - On ne peut pas couper la parole à Confie en parlant : pendant qu'il répond, le micro est
//   fermé, sinon il s'entendrait lui-même. L'interruption se fait au toucher (cercle ou bouton).
// - Sur iOS et Android, il faut un « development build » : la reconnaissance vocale n'existe
//   pas dans Expo Go, où cet écran propose simplement d'écrire.
// - Sur le web, cela dépend du navigateur (API Web Speech : Chrome, Edge, Safari ; pas Firefox).
// - La fin de phrase est détectée par un silence d'environ deux secondes. Dans un lieu
//   bruyant, toucher le cercle permet de dire « j'ai fini » sans attendre.

const ORB_MODE: Record<VoicePhase, OrbMode> = {
  checking: 'rest', explain: 'rest', denied: 'rest', unavailable: 'rest', idle: 'rest', error: 'rest',
  listening: 'listening', thinking: 'thinking', speaking: 'speaking',
};

export default function VoiceScreen() {
  const { id, from } = useLocalSearchParams<{ id: string; from?: string }>();
  const c = useColors();
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  const v = useVoiceConversation(id);
  const [showTranscript, setShowTranscript] = useState(() => useSettings.getState().showTranscript);
  const transcript = useRef<React.ComponentRef<typeof ScrollView>>(null);

  const { phase, muted } = v;
  const live = phase === 'listening' || phase === 'thinking' || phase === 'speaking' || phase === 'idle';
  const canInterrupt = phase === 'thinking' || phase === 'speaking';
  const listeningOpen = phase === 'listening' && !muted;

  // En quittant l'écran, le hook arrête micro, voix et génération (nettoyage au démontage).
  const quit = () => (router.canGoBack() ? router.back() : router.replace({ pathname: '/chat/[id]', params: { id } }));
  // Ouvert depuis la conversation : on y revient. Ouvert depuis l'accueil : on ouvre la conversation à la place.
  // (Sans cela, deux écrans de conversation s'empilaient et le bouton retour semblait ne rien faire.)
  const write = () => { v.stopAll(); if (from === 'chat' && router.canGoBack()) router.back(); else router.replace({ pathname: '/chat/[id]', params: { id } }); };
  const help = () => { v.pause(); router.push('/aide'); };

  if (!v.chat) {
    return (
      <View testID="voice" style={{ flex: 1, backgroundColor: c.bg, alignItems: 'center', justifyContent: 'center', gap: space.lg, padding: space.xl }}>
        <Txt testID="voice-state" center color="textSoft">Cette conversation n'existe plus.</Txt>
        <Button label="Retour à l'accueil" kind="soft" onPress={goHome} />
      </View>
    );
  }

  const label: Record<VoicePhase, string> = {
    checking: ' ',
    explain: 'Avant de commencer',
    denied: 'Le micro n\'est pas autorisé',
    unavailable: 'La voix n\'est pas disponible ici',
    idle: 'En pause',
    listening: muted ? 'Micro coupé' : 'Je t\'écoute',
    thinking: 'Je réfléchis',
    speaking: v.greeting ? 'Je suis là' : 'Je te réponds',
    error: 'Un petit contretemps',
  };

  const hint =
    phase === 'idle' ? 'Touche le cercle pour reprendre.'
    : phase === 'listening' ? (muted ? 'Je n\'entends rien tant que le micro est coupé.' : v.heard ? 'Marque une pause quand tu as fini, ou touche le cercle.' : 'Parle quand tu veux. Je te réponds dès que tu marques une pause.')
    : canInterrupt ? 'Touche le cercle pour m\'interrompre.'
    : null;

  const orbLabel =
    canInterrupt ? 'Interrompre la réponse'
    : phase === 'idle' ? 'Reprendre la conversation'
    : listeningOpen ? 'J\'ai fini de parler'
    : label[phase];
  const orbPress = canInterrupt ? v.interrupt : phase === 'idle' ? v.resume : listeningOpen ? v.finishNow : undefined;
  const orbSize = Math.round(Math.min(width * 0.56, height * 0.28, 230));

  const hasTranscript = showTranscript && live && (!!v.heard || !!v.reply);

  return (
    <View testID="voice" style={{ flex: 1, backgroundColor: c.bg, paddingTop: insets.top }}>
      <View style={{ width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', flex: 1 }}>
        {/* Haut de l'écran : uniquement du secondaire. Tout l'essentiel est en bas, sous le pouce. */}
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 56, paddingHorizontal: space.xl, gap: space.md }}>
          <View style={{ flexShrink: 1 }}>
            {v.crisis ? (
              <Animated.View>
                <Button label="Aide urgente" icon="phone" kind="ghost" small onPress={help} />
              </Animated.View>
            ) : null}
          </View>
          {live ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: HIT }}>
              <Txt variant="caption" color="textMuted">Transcription</Txt>
              <Toggle value={showTranscript} onChange={setShowTranscript} label="Afficher la transcription" />
            </View>
          ) : null}
        </View>

        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.xl, gap: space.xl }}>
          <Orb mode={ORB_MODE[phase]} level={v.level} size={orbSize} label={orbLabel} onPress={orbPress} disabled={!orbPress} />

          <View style={{ alignItems: 'center', gap: space.sm, alignSelf: 'stretch' }}>
            <Txt testID="voice-state" variant="title" center accessibilityRole="header" accessibilityLiveRegion="polite">{label[phase]}</Txt>
            {hint ? <Txt variant="small" color="textMuted" center style={{ maxWidth: 300 }}>{hint}</Txt> : null}
          </View>

          {phase === 'explain' ? (
            <Panel
              text="Pour qu'on se parle à voix haute, j'ai besoin d'entendre la tienne : le micro ne sert que sur cet écran."
              note="Ta voix est transformée en texte par le service de reconnaissance vocale de ton appareil ou de ton navigateur.">
              <Button label="Activer le micro" icon="mic" onPress={v.allow} />
              <Button label="Écrire à la place" kind="quiet" onPress={write} />
            </Panel>
          ) : null}

          {phase === 'denied' ? (
            <Panel
              text={Platform.OS === 'web'
                ? 'Ton navigateur bloque le micro pour Confie. Tu peux l\'autoriser depuis l\'icône à gauche de l\'adresse du site, puis réessayer.'
                : 'Sans micro, je ne peux pas t\'entendre. Tu peux l\'autoriser dans les réglages de ton téléphone, à la ligne Confie : active « Micro » et, sur iPhone, « Reconnaissance vocale ».'}>
              {Platform.OS !== 'web' ? <Button label="Ouvrir les réglages" kind="soft" onPress={() => { Linking.openSettings().catch(() => {}); }} /> : null}
              {Platform.OS === 'web' || v.canAskAgain ? <Button label="Réessayer" kind={Platform.OS === 'web' ? 'soft' : 'ghost'} onPress={v.allow} /> : null}
              <Button label="Écrire à la place" kind="quiet" onPress={write} />
            </Panel>
          ) : null}

          {phase === 'unavailable' ? (
            <Panel
              text={Platform.OS === 'web'
                ? 'Ce navigateur ne sait pas transcrire la voix. Chrome, Edge ou Safari le permettent. En attendant, on peut continuer par écrit.'
                : 'La reconnaissance vocale n\'est pas disponible sur cet appareil. On peut continuer par écrit, je suis là de la même façon.'}>
              <Button label="Écrire à la place" icon="edit" onPress={write} />
            </Panel>
          ) : null}

          {phase === 'error' ? (
            <Panel warn text={v.problem ?? v.aiError?.message ?? 'Je n\'arrive pas à te répondre pour l\'instant.'}>
              <Button label="Réessayer" kind="soft" onPress={v.retry} />
              <Button label="Écrire à la place" kind="quiet" onPress={write} />
            </Panel>
          ) : null}
        </View>

        {/* Transcription : discrète, facultative. La hauteur est réservée pour que le cercle ne saute pas. */}
        {live ? (
          <View style={{ height: showTranscript ? 124 : 0, paddingHorizontal: space.xl }}>
            {hasTranscript ? (
              <ScrollView ref={transcript} showsVerticalScrollIndicator={false} onContentSizeChange={() => transcript.current?.scrollToEnd({ animated: true })}
                contentContainerStyle={{ flexGrow: 1, justifyContent: 'flex-end', gap: space.sm, paddingBottom: space.md }}>
                {v.heard ? <Txt variant="small" color="textMuted" center accessibilityLabel={`Tu as dit : ${v.heard}`}>{v.heard}</Txt> : null}
                {v.reply ? <Txt variant="small" color="textSoft" center accessibilityLabel={`Confie : ${v.reply}`}>{v.reply}</Txt> : null}
              </ScrollView>
            ) : null}
          </View>
        ) : null}

        {/* Commandes : en bas, à portée de pouce. */}
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: Math.max(insets.bottom, space.lg) }}>
          <Control testID="voice-write" icon="edit" caption="Écrire" label="Écrire : revenir à la conversation écrite" onPress={write} />
          <Control testID="voice-mute" icon={muted ? 'micOff' : 'mic'} caption={muted ? 'Micro coupé' : 'Micro'} label={muted ? 'Réactiver le micro' : 'Couper le micro'}
            big active={muted} selected={muted} disabled={!live} onPress={v.toggleMute} />
          <Control testID="voice-interrupt" icon="stop" caption="Interrompre" label="Interrompre la réponse" big disabled={!canInterrupt} onPress={v.interrupt} />
          <Control testID="voice-quit" icon="close" caption="Quitter" label="Quitter le mode vocal" onPress={quit} />
        </View>
      </View>
    </View>
  );
}

function Panel({ text, note, warn, children }: { text: string; note?: string; warn?: boolean; children: React.ReactNode }) {
  const c = useColors();
  return (
    <Animated.View style={{ alignSelf: 'stretch', alignItems: 'center', gap: space.lg }} accessibilityLiveRegion="polite">
      <View style={{ gap: space.sm, maxWidth: 340 }}>
        <Txt center color="textSoft" style={warn ? { color: c.warn } : undefined}>{text}</Txt>
        {note ? <Txt variant="caption" color="textMuted" center>{note}</Txt> : null}
      </View>
      <View style={{ alignSelf: 'center', maxWidth: 340, width: '100%', alignItems: 'stretch', gap: space.sm }}>{children}</View>
    </Animated.View>
  );
}

function Control({ icon, caption, label, onPress, big, active, selected, disabled, testID }: {
  icon: IconName; caption: string; label: string; onPress: () => void;
  big?: boolean; active?: boolean; selected?: boolean; disabled?: boolean; testID: string;
}) {
  const c = useColors();
  const size = big ? 64 : 52;
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!disabled, selected }}
      disabled={disabled}
      hitSlop={4}
      onPress={() => { if (Platform.OS !== 'web') Haptics.selectionAsync().catch(() => {}); onPress(); }}
      style={({ pressed }) => [{ flex: 1, maxWidth: 96, minHeight: 64 + space.sm + 17, alignItems: 'center', justifyContent: 'flex-end', gap: space.sm }, disabled && { opacity: 0.35 }, pressed && { opacity: 0.7 }]}>
      <View style={{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center', backgroundColor: active ? c.primary : c.surface, borderWidth: active ? 0 : 1, borderColor: c.line }}>
        <Icon name={icon} size={big ? 26 : 22} color={active ? c.onPrimary : c.text} />
      </View>
      <Txt variant="caption" color={active ? 'text' : 'textSoft'} numberOfLines={1}>{caption}</Txt>
    </Pressable>
  );
}
