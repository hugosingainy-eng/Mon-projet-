import { useCallback, useEffect, useRef, useState } from 'react';

import { AiError, streamChat, type ChatContext } from '@/lib/ai';
import { parseReply } from '@/lib/tags';
import { useChats } from '@/store/chats';
import { useMemory } from '@/store/memory';
import { useSettings } from '@/store/settings';

export type SessionNote = { id: string; kind: 'retenu' | 'oublie' | 'memoire-off'; text: string; memoryId?: string };

/**
 * Le moteur d'une conversation : envoi, diffusion de la réponse, erreurs, et application
 * des balises de l'IA (mémoire). Partagé par le chat écrit et le mode vocal.
 */
export function useChatSession(chatId: string) {
  const chat = useChats((s) => s.chats[chatId]);
  const [streaming, setStreaming] = useState<string | null>(null); // texte brut en cours d'arrivée
  const [error, setError] = useState<AiError | null>(null);
  const [notes, setNotes] = useState<SessionNote[]>([]);
  const abort = useRef<AbortController | null>(null);
  const busy = streaming !== null;

  useEffect(() => () => abort.current?.abort(), []);

  const run = useCallback(
    async (opts: { voice?: boolean; journal?: string | null; onChunk?: (full: string) => void } = {}): Promise<string | null> => {
      const { chats, append } = useChats.getState();
      const current = chats[chatId];
      if (!current) return null;
      const settings = useSettings.getState();
      const useMemoryNow = settings.memory === 'on' && !current.temporary;
      const context: ChatContext = {
        name: settings.name,
        mode: current.mode,
        style: settings.style,
        frankness: settings.frankness,
        topic: current.topic,
        voice: !!opts.voice,
        memory: useMemoryNow ? useMemory.getState().items.map(({ id, text }) => ({ id, text })) : null,
        journal: opts.journal ?? null,
        localTime: new Date().toLocaleString('fr-FR', { weekday: 'long', hour: '2-digit', minute: '2-digit' }),
      };
      const controller = new AbortController();
      abort.current = controller;
      setError(null);
      setStreaming('');
      let raw = '';
      try {
        raw = await streamChat(
          current.messages.map(({ role, content }) => ({ role, content })),
          context,
          (full) => { raw = full; setStreaming(full); opts.onChunk?.(full); },
          controller.signal,
        );
      } catch (e) {
        const aborted = (e as Error)?.name === 'AbortError';
        if (!aborted) setError(e instanceof AiError ? e : new AiError('Je n\'arrive pas à te répondre pour l\'instant.', 'server'));
        if (!raw.trim()) { setStreaming(null); return null; }
        // Réponse interrompue en route : on garde ce qui est arrivé.
      }
      append(chatId, { role: 'assistant', content: raw, voice: opts.voice });
      setStreaming(null);

      // Mémoire : seulement si la personne l'a activée, et jamais en conversation temporaire.
      const parsed = parseReply(raw);
      const mem = useMemory.getState();
      const added: SessionNote[] = [];
      if (useMemoryNow) {
        for (const text of parsed.remember) {
          const id = mem.add(text, 'ia');
          if (id) added.push({ id: `n${id}`, kind: 'retenu', text, memoryId: id });
        }
      }
      for (const target of parsed.forget) {
        if (/^tout$/i.test(target)) { mem.clear(); added.push({ id: `f${Date.now()}`, kind: 'oublie', text: 'Tout ce que je retenais est effacé.' }); }
        else if (mem.items.some((i) => i.id === target)) { mem.remove(target); added.push({ id: `f${target}`, kind: 'oublie', text: 'C\'est oublié.' }); }
      }
      if (parsed.memoryOff) {
        settings.set({ memory: 'off' });
        added.push({ id: `m${Date.now()}`, kind: 'memoire-off', text: 'Mémoire désactivée.' });
      }
      if (added.length) setNotes((n) => [...n, ...added]);
      return raw;
    },
    [chatId],
  );

  const send = useCallback(
    async (text: string, opts: { voice?: boolean; journal?: string | null; onChunk?: (full: string) => void } = {}) => {
      const clean = text.trim();
      if (!clean || abort.current && streaming !== null) return null;
      useChats.getState().append(chatId, { role: 'user', content: clean, voice: opts.voice });
      return run(opts);
    },
    [chatId, run, streaming],
  );

  /** Relance la réponse au dernier message, après une erreur. */
  const retry = useCallback((opts: Parameters<typeof run>[0] = {}) => run(opts), [run]);
  const stop = useCallback(() => abort.current?.abort(), []);
  const undoNote = useCallback((note: SessionNote) => {
    if (note.memoryId) useMemory.getState().remove(note.memoryId);
    setNotes((n) => n.filter((x) => x.id !== note.id));
  }, []);

  const needsReply = !!chat && chat.messages.at(-1)?.role === 'user' && !busy;
  return { chat, streaming, busy, error, notes, send, retry, stop, undoNote, needsReply };
}
