import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Pressable, View } from 'react-native';

import { exerciseById } from '@/content/exercises';
import { searchVideos, type Video } from '@/lib/ai';
import { useWellbeing } from '@/store/wellbeing';
import { radius, space, useColors } from '@/theme';
import { Icon, IconButton, Txt } from '@/ui';
import { linkProps } from '@/ui/ExternalLink';

/** Vidéos proposées par l'IA pour un sujet. N'affiche que des vidéos vérifiées par le serveur ; sinon, un lien de recherche. */
export function VideoSuggestion({ query }: { query: string }) {
  const c = useColors();
  const [state, setState] = useState<{ verified: boolean; videos: Video[]; searchUrl: string } | null>(null);
  const saved = useWellbeing((s) => s.videos);
  const { saveVideo, removeVideo } = useWellbeing.getState();

  useEffect(() => {
    let alive = true;
    searchVideos(query).then((r) => alive && setState(r));
    return () => { alive = false; };
  }, [query]);

  if (!state) return null;
  if (!state.verified || state.videos.length === 0) {
    return (
      <Pressable accessibilityRole="link" accessibilityLabel={`Chercher sur YouTube : ${query}`} {...linkProps(state.searchUrl)} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.md, padding: space.md, borderRadius: radius.md, backgroundColor: c.surfaceAlt }, pressed && { opacity: 0.7 }]}>
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: c.sage, alignItems: 'center', justifyContent: 'center' }}><Icon name="play" size={16} color={c.surface} /></View>
        <View style={{ flex: 1 }}>
          <Txt variant="smallMedium">{query}</Txt>
          <Txt variant="caption" color="textMuted">Chercher des vidéos sur YouTube</Txt>
        </View>
      </Pressable>
    );
  }
  return (
    <View style={{ gap: space.sm }}>
      {state.videos.slice(0, 2).map((v) => {
        const isSaved = saved.some((s) => s.id === v.id);
        return (
          <Pressable key={v.id} accessibilityRole="link" accessibilityLabel={`Ouvrir la vidéo ${v.title}`} {...linkProps(v.url)} style={({ pressed }) => [{ flexDirection: 'row', gap: space.md, padding: space.sm, borderRadius: radius.md, backgroundColor: c.surfaceAlt, alignItems: 'center' }, pressed && { opacity: 0.7 }]}>
            {v.thumbnail ? <Image source={{ uri: v.thumbnail }} style={{ width: 96, height: 54, borderRadius: radius.sm, backgroundColor: c.line }} accessibilityIgnoresInvertColors /> : null}
            <View style={{ flex: 1 }}>
              <Txt variant="smallMedium" numberOfLines={2}>{v.title}</Txt>
              <Txt variant="caption" color="textMuted" numberOfLines={1}>{v.channel}</Txt>
            </View>
            <IconButton name="bookmark" label={isSaved ? 'Retirer des vidéos gardées' : 'Garder cette vidéo'} color={isSaved ? c.primary : c.textMuted} onPress={() => (isSaved ? removeVideo(v.id) : saveVideo({ id: v.id, title: v.title, channel: v.channel, url: v.url, why: query, category: 'Conversation' }))} />
          </Pressable>
        );
      })}
    </View>
  );
}

export function ExerciseSuggestion({ id }: { id: string }) {
  const c = useColors();
  const ex = exerciseById(id);
  if (!ex) return null;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Ouvrir l'exercice ${ex.title}`} onPress={() => router.push({ pathname: '/exercice/[id]', params: { id } })} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.md, padding: space.md, borderRadius: radius.md, backgroundColor: c.surfaceAlt }, pressed && { opacity: 0.7 }]}>
      <Icon name="breathe" size={24} />
      <View style={{ flex: 1 }}>
        <Txt variant="smallMedium">{ex.title}</Txt>
        <Txt variant="caption" color="textMuted">Exercice · {ex.minutes} min</Txt>
      </View>
      <Icon name="chevron" size={18} color={c.textMuted} />
    </Pressable>
  );
}

export function CrisisCard() {
  const c = useColors();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel="Voir les numéros d'aide" onPress={() => router.push('/aide')} style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: space.md, padding: space.md, borderRadius: radius.md, borderWidth: 1, borderColor: c.sage }, pressed && { opacity: 0.7 }]}>
      <Icon name="phone" size={22} color={c.primary} />
      <View style={{ flex: 1 }}>
        <Txt variant="smallMedium">Parler à quelqu'un maintenant</Txt>
        <Txt variant="caption" color="textSoft">3114 · gratuit, 24h/24. Voir tous les numéros.</Txt>
      </View>
    </Pressable>
  );
}
