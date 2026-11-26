import { fetch as streamingFetch } from 'expo/fetch';
import { Platform } from 'react-native';

import type { ModeId, StyleId, TopicId } from '@/content/modes';
import { API_URL } from '@/lib/config';
import { getAccessToken } from '@/lib/supabase';

export type ChatTurn = { role: 'user' | 'assistant'; content: string };
export type ChatContext = {
  name: string;
  mode: ModeId;
  style: StyleId;
  frankness: number;
  topic: TopicId | null;
  voice: boolean;
  memory: { id: string; text: string }[] | null; // null = mémoire désactivée ou conversation temporaire
  journal?: string | null; // entrée de journal partagée volontairement
  localTime: string;
};

export class AiError extends Error {
  constructor(message: string, public kind: 'offline' | 'config' | 'limit' | 'server') { super(message); }
}

const MESSAGES = {
  offline: 'Pas de connexion pour le moment. Ton message est gardé, réessaie quand le réseau revient.',
  server: 'Je n\'arrive pas à te répondre pour l\'instant. Réessaie dans un moment.',
};

// Pont optionnel : lorsqu'elle est ouverte dans un environnement qui fournit Claude directement
// (aperçu en ligne), l'app passe par lui au lieu du serveur.
type Bridge = (body: unknown, onText: (full: string) => void, signal?: AbortSignal) => Promise<string>;
const bridge = (): Bridge | null =>
  Platform.OS === 'web' ? ((globalThis as unknown as { confieBridge?: Bridge }).confieBridge ?? null) : null;

/** Envoie la conversation et diffuse la réponse au fil de l'eau. Renvoie le texte complet. */
export async function streamChat(messages: ChatTurn[], context: ChatContext, onText: (full: string) => void, signal?: AbortSignal): Promise<string> {
  const body = { messages: messages.slice(-40), context };
  const viaBridge = bridge();
  if (viaBridge) {
    try { return await viaBridge(body, onText, signal); } catch (e) {
      if ((e as Error)?.name === 'AbortError') throw e;
      throw new AiError(MESSAGES.server, 'server');
    }
  }

  let res: Response;
  try {
    const token = await getAccessToken();
    res = (await streamingFetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
      signal,
    })) as unknown as Response;
  } catch (e) {
    if ((e as Error)?.name === 'AbortError') throw e;
    throw new AiError(MESSAGES.offline, 'offline');
  }

  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { error?: string };
    const kind = res.status === 429 ? 'limit' : res.status === 503 ? 'config' : 'server';
    throw new AiError(data.error || MESSAGES.server, kind);
  }

  let full = '';
  const reader = res.body?.getReader();
  if (!reader) {
    full = await res.text();
    onText(full);
  } else {
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      full += decoder.decode(value, { stream: true });
      onText(full);
    }
  }
  if (!full.trim()) throw new AiError(MESSAGES.server, 'server');
  return full;
}

export type Video = { id: string; title: string; channel: string; url: string; thumbnail: string | null };

/** Vidéos YouTube vérifiées par le serveur. `verified: false` = le serveur n'a pas de clé YouTube. */
export async function searchVideos(query: string): Promise<{ verified: boolean; videos: Video[]; searchUrl: string }> {
  const searchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
  if (bridge()) return { verified: false, videos: [], searchUrl };
  try {
    const res = await fetch(`${API_URL}/api/videos?q=${encodeURIComponent(query)}`);
    if (!res.ok) return { verified: false, videos: [], searchUrl };
    const data = (await res.json()) as { verified: boolean; videos: Video[] };
    return { ...data, searchUrl };
  } catch {
    return { verified: false, videos: [], searchUrl };
  }
}
