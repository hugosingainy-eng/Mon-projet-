import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { MODES, STYLES } from '@/content/modes';
import { ModeSheet, Sheet } from '@/features/chat/ModeSheet';
import { signOutLocally, useAccountEmail } from '@/features/profile/useAccount';
import { listFrenchVoices, VOICE_RATES, type FrenchVoice } from '@/features/profile/voices';
import { hasSupabase } from '@/lib/config';
import { useSettings } from '@/store/settings';
import { space, useColors } from '@/theme';
import { Chip, ChipGroup, Divider, Field, Icon, Row, Screen, SectionTitle, Toggle, Txt } from '@/ui';
import { Hero, PlantArt } from '@/ui/Illustrations';

const FRANKNESS = [
  { value: 1, label: 'Tout en douceur' },
  { value: 2, label: 'Équilibrée' },
  { value: 3, label: 'Sans filtre' },
] as const;

const APPEARANCES = [
  { value: 'system', label: 'Système' },
  { value: 'light', label: 'Clair' },
  { value: 'dark', label: 'Sombre' },
] as const;

function Choice({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: space.md, paddingVertical: space.lg }}>
      <Txt variant="bodyMedium">{label}</Txt>
      <ChipGroup>{children}</ChipGroup>
    </View>
  );
}

export default function Profile() {
  const c = useColors();
  const s = useSettings();
  const email = useAccountEmail();
  const [voices, setVoices] = useState<FrenchVoice[] | null>(null);
  const [sheet, setSheet] = useState<'style' | 'mode' | 'voice' | null>(null);

  useEffect(() => {
    let alive = true;
    listFrenchVoices().then((v) => { if (alive) setVoices(v); });
    return () => { alive = false; };
  }, []);

  const style = STYLES.find((x) => x.id === s.style) ?? STYLES[0];
  const mode = MODES.find((x) => x.id === s.defaultMode) ?? MODES[0];
  const voice = voices?.find((v) => v.id === s.voiceId);
  const voiceHint = voices === null ? 'Recherche des voix…' : voices.length === 0 ? 'Aucune voix française trouvée sur cet appareil' : voice?.label ?? 'Voix par défaut de l\'appareil';
  const rate = VOICE_RATES.reduce((best, r) => (Math.abs(r.value - s.voiceRate) < Math.abs(best.value - s.voiceRate) ? r : best)).value;
  const tick = (on: boolean) => (on ? <Icon name="check" size={20} color={c.primary} /> : <View style={{ width: 20 }} />);

  return (
    <Screen edges={['top']} testID="profile">
      <Animated.View entering={FadeInDown.duration(400)}>
        <Hero caption="Ton espace" title="Profil" text="Règle Confie à ta façon. Tu peux tout changer quand tu veux." art={<PlantArt size={104} />} />
      </Animated.View>

      <View style={{ marginTop: space.xl }}>
        <Field label="Ton prénom" value={s.name} onChangeText={(name) => s.set({ name })} onBlur={() => s.set({ name: s.name.trim() })} placeholder="Facultatif" maxLength={30} autoCapitalize="words" autoCorrect={false} testID="profile-name" />
      </View>

      <SectionTitle>Ma façon d'échanger</SectionTitle>
      <Row icon="sliders" title="Style" hint={style.label} onPress={() => setSheet('style')} />
      <Divider />
      <Row icon="leaf" title="Mode par défaut" hint={mode.label} onPress={() => setSheet('mode')} />
      <Divider />
      <Choice label="Franchise">
        {FRANKNESS.map((f) => <Chip key={f.value} label={f.label} selected={s.frankness === f.value} onPress={() => s.set({ frankness: f.value })} />)}
      </Choice>

      <SectionTitle>Mémoire</SectionTitle>
      <Row icon="brain" title="Mémoire" hint={s.memory === 'on' ? 'Activée' : 'Désactivée'} right={<Toggle label="Mémoire" value={s.memory === 'on'} onChange={(v) => s.set({ memory: v ? 'on' : 'off' })} />} />
      <Divider />
      <Row icon="text" title="Ce que mon IA retient" hint="Voir, modifier ou effacer" onPress={() => router.push('/memoire')} />

      <SectionTitle>Voix</SectionTitle>
      <Row icon="wave" title="Voix" hint={voiceHint} onPress={voices && voices.length > 0 ? () => setSheet('voice') : undefined} />
      <Divider />
      <Choice label="Vitesse de lecture">
        {VOICE_RATES.map((r) => <Chip key={r.value} label={r.label} selected={rate === r.value} onPress={() => s.set({ voiceRate: r.value })} />)}
      </Choice>
      <Divider />
      <Row icon="text" title="Transcription" hint="Afficher le texte pendant une conversation vocale" right={<Toggle label="Transcription" value={s.showTranscript} onChange={(showTranscript) => s.set({ showTranscript })} />} />

      <SectionTitle>Application</SectionTitle>
      {/* On enregistre seulement la préférence. Programmer de vrais rappels demande d'installer et de
          configurer expo-notifications (autorisation système, canal Android, planification locale). */}
      <Row icon="bell" title="Rappels" hint="Ton choix est enregistré. Les rappels arriveront dans une prochaine version." right={<Toggle label="Rappels" value={s.notifications} onChange={(notifications) => s.set({ notifications })} />} />
      <Divider />
      <Choice label="Apparence">
        {APPEARANCES.map((a) => <Chip key={a.value} label={a.label} selected={s.appearance === a.value} onPress={() => s.set({ appearance: a.value })} />)}
      </Choice>
      <Divider />
      <Row icon="text" title="Langue" hint="Français. C'est la seule langue disponible pour l'instant." />

      <SectionTitle>Confidentialité et compte</SectionTitle>
      <Row icon="shield" title="Confidentialité et données" hint="Ce qui reste sur ton téléphone, export, suppression" onPress={() => router.push('/confidentialite')} />
      <Divider />
      {!hasSupabase ? (
        <Row icon="profile" title="Compte et synchronisation : bientôt" hint="Pour l'instant, tout reste sur ce téléphone, sans compte." />
      ) : email ? (
        <>
          <Row icon="profile" title="Compte" hint={email} />
          <Divider />
          <Row icon="lock" title="Me déconnecter" onPress={signOutLocally} />
        </>
      ) : (
        <Row icon="profile" title="Me connecter" hint="Ou créer un compte" onPress={() => router.push('/connexion')} />
      )}
      <Divider />
      <Row icon="heart" title="Abonnement" hint="Confie est gratuit pour le moment. Rien à payer, rien à débloquer." />

      <SectionTitle>En cas de besoin</SectionTitle>
      <Row icon="phone" title="Aide urgente" hint="Les numéros à appeler tout de suite" onPress={() => router.push('/aide')} />

      <Txt variant="caption" color="textMuted" style={{ marginTop: space.xl }}>
        Confie est une IA. Elle ne remplace pas un professionnel de santé.
      </Txt>

      <Sheet visible={sheet === 'style'} onClose={() => setSheet(null)} title="Quel style te convient ?">
        {STYLES.map((x) => (
          <Row key={x.id} title={x.label} hint={x.hint} onPress={() => { s.set({ style: x.id }); setSheet(null); }} right={tick(s.style === x.id)} />
        ))}
      </Sheet>
      <ModeSheet visible={sheet === 'mode'} value={s.defaultMode} onPick={(defaultMode) => s.set({ defaultMode })} onClose={() => setSheet(null)} />
      <Sheet visible={sheet === 'voice'} onClose={() => setSheet(null)} title="Choisir une voix">
        <ScrollView showsVerticalScrollIndicator={false}>
          <Row title="Voix par défaut de l'appareil" onPress={() => { s.set({ voiceId: null }); setSheet(null); }} right={tick(!voice)} />
          {(voices ?? []).map((v) => (
            <Row key={v.id} title={v.label} onPress={() => { s.set({ voiceId: v.id }); setSheet(null); }} right={tick(s.voiceId === v.id)} />
          ))}
        </ScrollView>
      </Sheet>
    </Screen>
  );
}
