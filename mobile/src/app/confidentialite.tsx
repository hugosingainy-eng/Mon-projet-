import { router } from 'expo-router';
import { useState } from 'react';
import { Platform, Share, View } from 'react-native';

import { confirmAction } from '@/features/profile/confirm';
import { signOutLocally, useAccountEmail } from '@/features/profile/useAccount';
import { dayKey, wipeDevice } from '@/lib/storage';
import { useChats } from '@/store/chats';
import { useMemory } from '@/store/memory';
import { useSettings } from '@/store/settings';
import { useWellbeing } from '@/store/wellbeing';
import { space, useColors } from '@/theme';
import { Divider, Header, Icon, Row, Screen, SectionTitle, Txt, type IconName } from '@/ui';
import { restart } from '@/lib/nav';

const SENT = [
  'Les messages de la conversation en cours, au moment où tu en envoies un.',
  'Ton prénom, si tu l\'as indiqué, et tes préférences d\'échange (style, mode, franchise).',
  'Ce que ton IA retient, seulement si la mémoire est activée.',
  'Une page de ton journal, seulement si tu choisis de la partager.',
];

/** Copie lisible de tout ce que l'app garde, sans les fonctions ni les drapeaux internes. */
function buildExport() {
  const { set: _set, reset: _reset, onboarded: _onboarded, ...settings } = useSettings.getState();
  const { moods, journal, exerciseLogs, goals, videos } = useWellbeing.getState();
  return JSON.stringify(
    {
      app: 'Confie',
      exportedAt: new Date().toISOString(),
      settings,
      chats: Object.values(useChats.getState().chats).filter((c) => !c.temporary),
      memory: useMemory.getState().items,
      wellbeing: { moods, journal, exerciseLogs, goals, videos },
    },
    null,
    2,
  );
}

function Point({ icon, children }: { icon: IconName; children: string }) {
  const c = useColors();
  return (
    <View style={{ flexDirection: 'row', gap: space.md, alignItems: 'flex-start' }}>
      <View style={{ marginTop: 3 }}><Icon name={icon} size={18} color={c.sage} /></View>
      <Txt variant="small" color="textSoft" style={{ flex: 1 }}>{children}</Txt>
    </View>
  );
}

export default function Privacy() {
  const email = useAccountEmail();
  const [note, setNote] = useState<string | null>(null);

  const exportData = async () => {
    const json = buildExport();
    try {
      if (Platform.OS === 'web') {
        const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
        const a = document.createElement('a');
        a.href = url;
        a.download = `confie-donnees-${dayKey()}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        // Certains environnements bloquent les téléchargements : on copie aussi les données, pour ne jamais échouer en silence.
        let copied = false;
        try { await navigator.clipboard.writeText(json); copied = true; } catch { /* presse-papiers refusé */ }
        setNote(copied ? 'Tes données sont prêtes. Si aucun fichier ne s\'est téléchargé, elles ont aussi été copiées : colle-les dans une note.' : 'Le téléchargement a été lancé. S\'il ne démarre pas, ouvre l\'app dans un navigateur.');
      } else {
        await Share.share({ message: json, title: 'Mes données Confie' });
        setNote(null);
      }
    } catch {
      setNote('L\'export n\'a pas abouti. Réessaie dans un instant.');
    }
  };

  const deleteAll = () =>
    confirmAction({
      title: 'Supprimer toutes mes données ?',
      message: 'Tes conversations, ton journal, ton humeur, tes exercices, ta mémoire et tes réglages seront effacés de ce téléphone. C\'est définitif.',
      confirmLabel: 'Tout supprimer',
      onConfirm: async () => {
        try {
          await signOutLocally();
          useChats.getState().clear();
          useMemory.getState().clear();
          useWellbeing.getState().clear();
          useSettings.getState().reset();
          await wipeDevice();
          restart();
        } catch {
          setNote('La suppression n\'a pas abouti. Réessaie dans un instant.');
        }
      },
    });

  const deleteAccount = () =>
    confirmAction({
      title: 'Supprimer mon compte ?',
      message: 'La suppression du compte côté serveur n\'est pas encore disponible dans l\'app. Si tu continues, tu seras seulement déconnecté·e de ce téléphone : ton compte existera toujours.',
      confirmLabel: 'Me déconnecter',
      onConfirm: async () => {
        await signOutLocally();
        setNote('Tu es déconnecté·e de ce téléphone. Ton compte n\'a pas été supprimé.');
      },
    });

  return (
    <Screen testID="privacy">
      <Header title="Confidentialité" />
      <View style={{ gap: space.md, marginTop: space.lg }}>
        <Txt variant="title">Tes données, en clair</Txt>
        <Txt color="textSoft">Voici ce que Confie garde, où, et ce qui quitte ton téléphone.</Txt>
      </View>

      <SectionTitle>Ce qui reste sur ton téléphone</SectionTitle>
      <View style={{ gap: space.md }}>
        <Txt variant="small" color="textSoft">Tout est enregistré dans le stockage local de l'app, sur cet appareil :</Txt>
        <Point icon="journal">Ton journal.</Point>
        <Point icon="heart">Tes points d'humeur.</Point>
        <Point icon="breathe">Tes exercices, tes objectifs et tes vidéos gardées.</Point>
        <Point icon="history">Tes conversations. Les conversations temporaires, elles, ne sont jamais enregistrées.</Point>
        <Point icon="brain">Ce que ton IA retient.</Point>
      </View>

      <SectionTitle>Ce qui est envoyé à l'IA</SectionTitle>
      <View style={{ gap: space.md }}>
        <Txt variant="small" color="textSoft">
          Pour te répondre, Confie doit transmettre certaines choses. Elles passent par le serveur de Confie, puis par Anthropic, l'entreprise qui fournit l'IA, uniquement pour générer la réponse.
        </Txt>
        {SENT.map((t) => <Point key={t} icon="send">{t}</Point>)}
        <Txt variant="small" color="textSoft">Ton journal, ton humeur et tes exercices ne sont pas envoyés tant que tu ne le décides pas.</Txt>
      </View>

      <SectionTitle>Ce que Confie n'est pas</SectionTitle>
      <Txt variant="small" color="textSoft">
        Confie est une IA. Ce n'est ni un médecin, ni un psychologue, ni un service d'urgence. Elle peut t'écouter et t'aider à y voir plus clair, mais elle ne pose pas de diagnostic et ne remplace pas un professionnel de santé.
      </Txt>

      <SectionTitle>Tes données t'appartiennent</SectionTitle>
      <Row testID="export" icon="download" title="Exporter mes données" hint={Platform.OS === 'web' ? 'Télécharge un fichier lisible (JSON)' : 'Partage une copie lisible (JSON)'} onPress={exportData} />
      <Divider />
      <Row testID="delete-all" icon="trash" title="Supprimer toutes mes données" hint="Efface tout ce qui est sur ce téléphone" danger onPress={deleteAll} />
      {email ? (
        <>
          <Divider />
          <Row icon="profile" title="Supprimer mon compte" hint={`Connecté·e avec ${email}. La suppression côté serveur n'est pas encore disponible : pour l'instant, tu peux seulement te déconnecter.`} danger onPress={deleteAccount} />
        </>
      ) : null}
      {note ? <Txt variant="small" color="textSoft" style={{ marginTop: space.md }}>{note}</Txt> : null}
    </Screen>
  );
}
