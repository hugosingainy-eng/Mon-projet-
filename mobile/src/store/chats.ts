import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { ModeId, TopicId } from '@/content/modes';
import { deviceStorage, uid } from '@/lib/storage';

export type Message = { id: string; role: 'user' | 'assistant'; content: string; at: number; voice?: boolean };
export type Chat = {
  id: string;
  title: string;
  topic: TopicId | null;
  mode: ModeId;
  temporary: boolean; // conversation temporaire : jamais enregistrée, jamais mémorisée
  createdAt: number;
  updatedAt: number;
  messages: Message[];
};

type Chats = {
  chats: Record<string, Chat>;
  create: (init: { mode: ModeId; topic?: TopicId | null; temporary?: boolean }) => string;
  append: (chatId: string, msg: Omit<Message, 'id' | 'at'>) => string;
  patchMessage: (chatId: string, msgId: string, content: string) => void;
  removeMessage: (chatId: string, msgId: string) => void;
  setMode: (chatId: string, mode: ModeId) => void;
  rename: (chatId: string, title: string) => void;
  remove: (chatId: string) => void;
  clear: () => void;
};

const titleFrom = (text: string) => {
  const t = text.replace(/\s+/g, ' ').trim();
  return t.length > 42 ? t.slice(0, 40).trimEnd() + '…' : t;
};

export const useChats = create<Chats>()(
  persist(
    (set) => ({
      chats: {},
      create: ({ mode, topic = null, temporary = false }) => {
        const id = uid();
        const now = Date.now();
        set((s) => ({
          chats: { ...s.chats, [id]: { id, title: 'Nouvelle conversation', topic, mode, temporary, createdAt: now, updatedAt: now, messages: [] } },
        }));
        return id;
      },
      append: (chatId, msg) => {
        const id = uid();
        set((s) => {
          const chat = s.chats[chatId];
          if (!chat) return s;
          const isFirstUser = msg.role === 'user' && !chat.messages.some((m) => m.role === 'user');
          return {
            chats: {
              ...s.chats,
              [chatId]: {
                ...chat,
                title: isFirstUser ? titleFrom(msg.content) : chat.title,
                updatedAt: Date.now(),
                messages: [...chat.messages, { ...msg, id, at: Date.now() }],
              },
            },
          };
        });
        return id;
      },
      patchMessage: (chatId, msgId, content) =>
        set((s) => {
          const chat = s.chats[chatId];
          if (!chat) return s;
          return { chats: { ...s.chats, [chatId]: { ...chat, messages: chat.messages.map((m) => (m.id === msgId ? { ...m, content } : m)) } } };
        }),
      removeMessage: (chatId, msgId) =>
        set((s) => {
          const chat = s.chats[chatId];
          if (!chat) return s;
          return { chats: { ...s.chats, [chatId]: { ...chat, messages: chat.messages.filter((m) => m.id !== msgId) } } };
        }),
      setMode: (chatId, mode) =>
        set((s) => (s.chats[chatId] ? { chats: { ...s.chats, [chatId]: { ...s.chats[chatId], mode } } } : s)),
      rename: (chatId, title) =>
        set((s) => (s.chats[chatId] ? { chats: { ...s.chats, [chatId]: { ...s.chats[chatId], title: title.trim() || s.chats[chatId].title } } } : s)),
      remove: (chatId) =>
        set((s) => {
          const { [chatId]: _, ...rest } = s.chats;
          return { chats: rest };
        }),
      clear: () => set({ chats: {} }),
    }),
    {
      name: 'confie.chats',
      storage: deviceStorage,
      version: 1,
      // Les conversations temporaires ne sont jamais écrites sur l'appareil.
      partialize: (s) => ({ chats: Object.fromEntries(Object.entries(s.chats).filter(([, c]) => !c.temporary)) }),
    },
  ),
);

export const sortedChats = (chats: Record<string, Chat>) =>
  Object.values(chats).filter((c) => c.messages.length > 0).sort((a, b) => b.updatedAt - a.updatedAt);
