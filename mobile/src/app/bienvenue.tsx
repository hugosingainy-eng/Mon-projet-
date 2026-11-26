import { router } from 'expo-router';
import { View } from 'react-native';

import { hasSupabase } from '@/lib/config';
import { radius, space, useColors } from '@/theme';
import { Button, Icon, Screen, Txt } from '@/ui';
import { Botanical } from '@/ui/Botanical';

export default function Welcome() {
  const c = useColors();
  return (
    <Screen
      scroll={false}
      testID="welcome"
      footer={
        <View style={{ gap: space.sm }}>
          <Button label="Commencer" onPress={() => router.push('/onboarding')} />
          {hasSupabase ? <Button label="Se connecter" kind="quiet" onPress={() => router.push('/connexion')} /> : null}
          <Txt variant="caption" color="textMuted" center style={{ marginTop: space.sm }}>
            Confie est une intelligence artificielle. Elle ne remplace ni un psychologue ni un médecin.
          </Txt>
        </View>
      }>
      <View style={{ flex: 1, justifyContent: 'center', gap: space.xl }}>
        <View style={{ backgroundColor: c.surfaceAlt, borderRadius: radius.lg + 6, alignItems: 'center', paddingVertical: space.lg }}><Botanical size={190} /></View>
        <Txt variant="display">Tu peux tout dire.{'\n'}Ici, tu n'as pas à faire semblant.</Txt>
        <Txt color="textSoft" style={{ maxWidth: 340 }}>
          Un espace pour toi, à n'importe quelle heure. Parler librement, être écouté, comprendre, avancer.
        </Txt>
        <View style={{ gap: space.md, marginTop: space.md }}>
          <Point icon="heart" text="Une écoute attentive, sans jugement, par écrit ou à voix haute." />
          <Point icon="lock" text="Ton journal et ton suivi restent sur ton téléphone. La mémoire est facultative." />
        </View>
      </View>
    </Screen>
  );
}

function Point({ icon, text }: { icon: 'heart' | 'lock'; text: string }) {
  return (
    <View style={{ flexDirection: 'row', gap: space.md, alignItems: 'flex-start' }}>
      <View style={{ marginTop: 3 }}><Icon name={icon} size={18} /></View>
      <Txt variant="small" color="textSoft" style={{ flex: 1 }}>{text}</Txt>
    </View>
  );
}
