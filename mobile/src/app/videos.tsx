import { useRef, useState } from 'react';
import { Image, Pressable, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { searchVideos, type Video } from '@/lib/ai';
import { useWellbeing } from '@/store/wellbeing';
import { radius, space, useColors } from '@/theme';
import { Chip, ChipGroup, Divider, Empty, Header, Icon, IconButton, Screen, SectionTitle, Txt } from '@/ui';
import { linkProps } from '@/ui/ExternalLink';

// Les requêtes orientent la recherche vers des explications données par des professionnels,
// sans jamais affirmer nous-mêmes la qualification d'une chaîne.
const CATEGORIES = [
  { label: 'Anxiété', query: 'gérer l\'anxiété explications psychologue' },
  { label: 'Stress', query: 'gérer le stress au quotidien conseils psychologue' },
  { label: 'Amour', query: 'relation amoureuse saine explications psychologue' },
  { label: 'Relations', query: 'relations avec les autres poser ses limites psychologue' },
  { label: 'Ruptures', query: 'surmonter une rupture amoureuse conseils psychologue' },
  { label: 'Confiance en soi', query: 'confiance en soi estime de soi explications psychologue' },
  { label: 'Motivation', query: 'retrouver la motivation explications psychologue' },
  { label: 'Sommeil', query: 'mieux dormir insomnie conseils médecin du sommeil' },
  { label: 'Gestion des émotions', query: 'réguler ses émotions explications psychologue' },
  { label: 'Pensées négatives', query: 'pensées négatives ruminations explications psychologue TCC' },
  { label: 'Communication', query: 'communication non violente explications psychologue' },
  { label: 'Solitude', query: 'sentiment de solitude comprendre et agir psychologue' },
] as const;

type Category = (typeof CATEGORIES)[number];
type Result = { verified: boolean; videos: Video[]; searchUrl: string };


export default function Videos() {
  const c = useColors();
  const saved = useWellbeing((s) => s.videos);
  const { saveVideo, removeVideo } = useWellbeing.getState();
  const [category, setCategory] = useState<Category | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const request = useRef(0);

  const pick = async (cat: Category) => {
    const n = ++request.current;
    setCategory(cat);
    setResult(null);
    const r = await searchVideos(cat.query);
    if (n === request.current) setResult(r); // ignore une réponse arrivée après un autre choix
  };

  const tile = { flexDirection: 'row', alignItems: 'center', gap: space.md, borderRadius: radius.md, backgroundColor: c.surfaceAlt } as const;

  return (
    <Screen testID="videos">
      <Header title="Vidéos" />
      <View style={{ gap: space.md, marginTop: space.lg }}>
        <Txt variant="title">Vidéos pour aller plus loin</Txt>
        <Txt color="textSoft">Choisis un thème. Les vidéos s'ouvrent sur YouTube.</Txt>
      </View>

      <ChipGroup style={{ marginTop: space.xl }}>
        {CATEGORIES.map((cat) => <Chip key={cat.label} label={cat.label} selected={category?.label === cat.label} onPress={() => pick(cat)} />)}
      </ChipGroup>

      {category ? (
        <View style={{ marginTop: space.xl, gap: space.sm, minHeight: 72 }}>
          {!result ? (
            <Txt variant="small" color="textMuted">Recherche en cours…</Txt>
          ) : result.verified && result.videos.length > 0 ? (
            <Animated.View style={{ gap: space.sm }}>
              {result.videos.map((v) => {
                const isSaved = saved.some((s) => s.id === v.id);
                return (
                  <Pressable key={v.id} accessibilityRole="link" accessibilityLabel={`Ouvrir la vidéo ${v.title}, chaîne ${v.channel}`} {...linkProps(v.url)} style={({ pressed }) => [tile, { padding: space.sm }, pressed && { opacity: 0.7 }]}>
                    {v.thumbnail ? <Image source={{ uri: v.thumbnail }} style={{ width: 112, height: 63, borderRadius: radius.sm, backgroundColor: c.line }} accessibilityIgnoresInvertColors /> : null}
                    <View style={{ flex: 1 }}>
                      <Txt variant="smallMedium" numberOfLines={2}>{v.title}</Txt>
                      <Txt variant="caption" color="textMuted" numberOfLines={1}>{v.channel}</Txt>
                    </View>
                    <IconButton name="bookmark" label={isSaved ? 'Retirer des vidéos gardées' : 'Garder cette vidéo'} color={isSaved ? c.primary : c.textMuted} onPress={() => (isSaved ? removeVideo(v.id) : saveVideo({ id: v.id, title: v.title, channel: v.channel, url: v.url, why: category.query, category: category.label }))} />
                  </Pressable>
                );
              })}
              <Txt variant="caption" color="textMuted" style={{ marginTop: space.xs }}>
                Ces vidéos existent bien sur YouTube, mais Confie ne vérifie pas les diplômes de leurs auteurs. Garde ton esprit critique.
              </Txt>
            </Animated.View>
          ) : (
            <Animated.View style={{ gap: space.md }}>
              <Pressable accessibilityRole="link" accessibilityLabel={`Chercher sur YouTube : ${category.label}`} {...linkProps(result.searchUrl)} style={({ pressed }) => [tile, { padding: space.md }, pressed && { opacity: 0.7 }]}>
                <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: c.sage, alignItems: 'center', justifyContent: 'center' }}><Icon name="play" size={16} color={c.surface} /></View>
                <View style={{ flex: 1 }}>
                  <Txt variant="smallMedium">{category.label}</Txt>
                  <Txt variant="caption" color="textMuted">Chercher des vidéos sur YouTube</Txt>
                </View>
                <Icon name="chevron" size={18} color={c.textMuted} />
              </Pressable>
              <Txt variant="small" color="textSoft">
                {result.verified
                  ? 'Aucune vidéo vérifiée pour ce thème pour l\'instant. Tu peux lancer la recherche toi-même.'
                  : 'Les recommandations vérifiées demandent que le service vidéo soit configuré, ce qui n\'est pas encore le cas. En attendant, ce lien ouvre simplement la recherche YouTube.'}
              </Txt>
            </Animated.View>
          )}
        </View>
      ) : null}

      <SectionTitle>Mes vidéos gardées</SectionTitle>
      {saved.length === 0 ? (
        <Empty title="Aucune vidéo gardée" text="Quand une vidéo te parle, garde-la d'un geste pour la retrouver ici." />
      ) : (
        saved.map((v, i) => (
          <View key={v.id}>
            {i > 0 ? <Divider /> : null}
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.xs }}>
              <Pressable accessibilityRole="link" accessibilityLabel={`Ouvrir la vidéo ${v.title}, chaîne ${v.channel}`} {...linkProps(v.url)} style={({ pressed }) => [{ flex: 1, minHeight: 60, paddingVertical: space.md, justifyContent: 'center' }, pressed && { opacity: 0.6 }]}>
                <Txt variant="bodyMedium" numberOfLines={2}>{v.title}</Txt>
                <Txt variant="small" color="textMuted" numberOfLines={1}>{v.channel} · {v.category}</Txt>
              </Pressable>
              <IconButton name="trash" size={20} label={`Retirer la vidéo ${v.title}`} onPress={() => removeVideo(v.id)} />
            </View>
          </View>
        ))
      )}
    </Screen>
  );
}
