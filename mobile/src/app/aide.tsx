import { router } from 'expo-router';
import { Linking, View } from 'react-native';

import { space } from '@/theme';
import { Button, Card, Row, Screen, Txt } from '@/ui';

// Numéros officiels français. Ne jamais en ajouter sans vérification.
const LINES = [
  { num: '3114', title: 'Prévention du suicide', hint: 'Gratuit, 24h/24, 7j/7' },
  { num: '15', title: 'SAMU', hint: 'Urgence médicale' },
  { num: '112', title: 'Urgences', hint: 'Partout en Europe' },
  { num: '3919', title: 'Violences Femmes Info', hint: 'Gratuit, 24h/24' },
  { num: '119', title: 'Enfance en danger', hint: 'Gratuit, 24h/24' },
  { num: '114', title: 'Urgences par SMS', hint: 'Si tu ne peux pas parler' },
];

export default function Help() {
  return (
    <Screen testID="help" footer={<Button label="Fermer" kind="soft" onPress={() => router.back()} />}>
      <View style={{ gap: space.md, marginTop: space.xxl }}>
        <Txt variant="title">Tu n'es pas seul·e.</Txt>
        <Txt color="textSoft">Si tu vas très mal ou si tu es en danger, des personnes formées répondent tout de suite. Tu peux aussi prévenir quelqu'un de confiance près de toi.</Txt>
      </View>
      <Card flat style={{ marginTop: space.xl, paddingVertical: space.sm }}>
        {LINES.map((l) => (
          <Row key={l.num} title={`${l.num} · ${l.title}`} hint={l.hint} icon="phone" onPress={() => Linking.openURL(`tel:${l.num}`)} />
        ))}
      </Card>
      <Txt variant="caption" color="textMuted" style={{ marginTop: space.lg }}>
        Numéros valables en France. Ailleurs, contacte les services d'urgence de ton pays. Confie ne peut pas appeler les secours à ta place.
      </Txt>
    </Screen>
  );
}
