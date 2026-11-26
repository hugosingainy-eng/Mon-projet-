import { useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { useSharedValue, withTiming } from 'react-native-reanimated';

import { useChatSession } from '@/features/chat/session';
import { parseReply, speakable, splitSentences } from '@/lib/tags';
import {
  finishListening, getMicPermission, isRecognitionAvailable, requestMicPermission, setSpeechListener,
  speakSentence, speechQueueEmpty, startListening, stopListening, stopSpeaking, type ListenErrorCode,
} from '@/lib/voice';
import { useChats } from '@/store/chats';
import { useSettings } from '@/store/settings';

export type VoicePhase =
  | 'checking' // on regarde si le micro est disponible et autorisé
  | 'explain' // on explique pourquoi on a besoin du micro, avant de le demander
  | 'denied' // micro refusé
  | 'unavailable' // pas de reconnaissance vocale sur cet appareil ou ce navigateur
  | 'idle' // en pause : rien n'est écouté, rien n'est dit
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'error';

const LISTEN_PROBLEMS: Record<Exclude<ListenErrorCode, 'not-allowed' | 'unavailable'>, string> = {
  network: 'Je n\'arrive pas à t\'entendre : la reconnaissance vocale a besoin d\'une connexion. Vérifie ton réseau, puis réessaie.',
  'audio-capture': 'Le micro n\'est pas accessible pour le moment. Il est peut-être utilisé par un appel ou une autre app.',
  'language-not-supported': 'La reconnaissance vocale en français n\'est pas installée sur cet appareil. Tu peux l\'ajouter dans les réglages de ton téléphone, ou m\'écrire.',
  unknown: 'Je n\'arrive pas à t\'entendre pour l\'instant. On peut réessayer, ou tu peux m\'écrire.',
};

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * La conversation vocale, mains libres : écouter → réfléchir → répondre → écouter.
 *
 * Limite assumée : pendant que Confie parle, le micro est fermé (il entendrait la voix de
 * synthèse). On ne peut donc pas l'interrompre en parlant ; on l'interrompt en touchant l'écran.
 *
 * Toutes les fonctions ci-dessous ne lisent que des refs et des setters stables : les rappels
 * confiés au moteur vocal restent donc valables d'un rendu à l'autre.
 */
export function useVoiceConversation(chatId: string) {
  const session = useChatSession(chatId);
  const sessionRef = useRef(session);
  useEffect(() => { sessionRef.current = session; });

  const [phase, setPhaseState] = useState<VoicePhase>('checking');
  const [muted, setMutedState] = useState(false);
  const [heard, setHeard] = useState(''); // ce que la personne vient de dire
  const [reply, setReply] = useState(''); // ce que Confie répond (ou son mot d'accueil)
  const [greeting, setGreetingState] = useState(false);
  const [crisis, setCrisis] = useState(false);
  const [canAskAgain, setCanAskAgain] = useState(true);
  const [problem, setProblem] = useState<string | null>(null); // souci d'écoute (pas d'IA)
  const level = useSharedValue(0); // volume de la voix, pour le cercle

  const phaseRef = useRef<VoicePhase>('checking');
  const mutedRef = useRef(false);
  const greetingRef = useRef(false);
  const turn = useRef(0); // change à chaque interruption : les réponses en retard sont ignorées
  const spoken = useRef(0); // nombre de phrases de la réponse déjà confiées à la voix
  const replyDone = useRef(false);
  const fresh = useRef(true);

  const setPhase = (p: VoicePhase) => { phaseRef.current = p; setPhaseState(p); };
  const setGreeting = (g: boolean) => { greetingRef.current = g; setGreetingState(g); };

  function fail(code: ListenErrorCode) {
    stopListening();
    level.set(0);
    if (code === 'unavailable') return setPhase('unavailable');
    if (code === 'not-allowed') { setCanAskAgain(false); return setPhase('denied'); }
    setProblem(LISTEN_PROBLEMS[code]);
    setPhase('error');
  }

  function listen() {
    setGreeting(false);
    setProblem(null);
    setPhase('listening');
    level.set(0);
    fresh.current = true;
    if (mutedRef.current) return; // micro coupé : on n'enregistre rien
    startListening({
      onPartial: (text) => {
        // La réponse précédente reste affichée jusqu'à ce que la personne reprenne la parole.
        if (fresh.current && text) { fresh.current = false; setReply(''); }
        setHeard(text);
      },
      onVolume: (v) => level.set(withTiming(v, { duration: 200 })),
      onEndOfSpeech: (text) => { void respond(text); },
      onError: fail,
    });
  }

  /** Confie à la voix les phrases terminées qui ne l'ont pas encore été. */
  function feed(raw: string, final: boolean) {
    const parsed = parseReply(raw);
    if (parsed.crisis) setCrisis(true);
    setReply(parsed.text);
    const { ready, rest } = splitSentences(final ? `${parsed.text}\n` : parsed.text);
    const next = ready.slice(spoken.current);
    spoken.current = Math.max(spoken.current, ready.length);
    if (final && rest.trim()) next.push(rest);
    for (const sentence of next) {
      const text = speakable(sentence);
      if (!text) continue;
      if (phaseRef.current !== 'speaking') setPhase('speaking');
      speakSentence(text);
    }
  }

  async function respond(text: string) {
    const mine = ++turn.current;
    stopListening();
    level.set(0);
    setHeard(text);
    setReply('');
    setPhase('thinking');
    spoken.current = 0;
    replyDone.current = false;
    // Juste après une interruption, la réponse précédente peut finir de s'annuler.
    for (let i = 0; i < 20 && sessionRef.current.busy; i++) await wait(100);
    if (mine !== turn.current) return;
    const raw = await sessionRef.current.send(text, {
      voice: true,
      onChunk: (full) => { if (mine === turn.current) feed(full, false); },
    });
    if (mine !== turn.current) return; // interrompu entre-temps
    if (raw === null) return setPhase('error'); // le détail est dans session.error
    feed(raw, true);
    replyDone.current = true;
    if (speechQueueEmpty()) listen();
  }

  function begin() {
    const chat = useChats.getState().chats[chatId];
    if (!chat) return;
    if (chat.messages.length > 0) return listen();
    // Première fois dans cette conversation : un mot d'accueil, dit mais pas enregistré.
    const name = useSettings.getState().name.trim();
    const hello = name ? `Je suis là, ${name}. Prends ton temps, je t'écoute.` : 'Je suis là. Prends ton temps, je t\'écoute.';
    setGreeting(true);
    setReply(hello);
    setPhase('speaking');
    speakSentence(hello);
  }

  /** Arrête la voix et la génération, puis retourne à l'écoute. */
  function interrupt() {
    if (phaseRef.current !== 'thinking' && phaseRef.current !== 'speaking') return;
    turn.current++;
    stopSpeaking();
    sessionRef.current.stop();
    listen();
  }

  /** Arrête tout (micro, voix, génération) sans rien relancer. */
  function stopAll() {
    turn.current++;
    stopListening();
    stopSpeaking();
    sessionRef.current.stop();
    level.set(0);
  }

  function pause() {
    if (!['listening', 'thinking', 'speaking'].includes(phaseRef.current)) return;
    stopAll();
    setHeard('');
    setPhase('idle');
  }

  function resume() {
    if (phaseRef.current === 'idle') listen();
  }

  /** « J'ai fini » : envoie sans attendre le silence (utile quand il y a du bruit autour). */
  function finishNow() {
    if (phaseRef.current === 'listening') finishListening();
  }

  function toggleMute() {
    const next = !mutedRef.current;
    mutedRef.current = next;
    setMutedState(next);
    if (phaseRef.current !== 'listening') return;
    if (next) { stopListening(); setHeard(''); level.set(0); } else listen();
  }

  async function allow() {
    const res = await requestMicPermission();
    if (res.status === 'granted') return begin();
    if (res.status === 'unavailable') return setPhase('unavailable');
    setCanAskAgain(res.canAskAgain);
    setPhase('denied');
  }

  function retry() {
    const wasListening = problem !== null;
    setProblem(null);
    const chat = useChats.getState().chats[chatId];
    const last = chat?.messages.at(-1);
    if (!wasListening && last?.role === 'user') {
      // session.retry() relance sans le mode vocal ni la diffusion phrase par phrase :
      // on retire donc le message resté sans réponse et on le renvoie tel quel.
      useChats.getState().removeMessage(chatId, last.id);
      void respond(last.content);
    } else {
      listen();
    }
  }

  useEffect(() => {
    let alive = true;
    setSpeechListener({
      onEmpty: () => {
        if (phaseRef.current !== 'speaking') return;
        // Entre deux phrases, la voix peut rattraper la génération : on n'écoute à nouveau
        // que lorsque la réponse est complète.
        if (greetingRef.current || replyDone.current) listen();
      },
    });

    (async () => {
      if (!useChats.getState().chats[chatId]) return;
      if (!isRecognitionAvailable()) return setPhase('unavailable');
      const res = await getMicPermission();
      if (!alive) return;
      if (res.status === 'granted') begin();
      else if (res.status === 'unavailable') setPhase('unavailable');
      else if (res.status === 'denied' && !res.canAskAgain) { setCanAskAgain(false); setPhase('denied'); }
      else setPhase('explain'); // on explique d'abord, on demande ensuite
    })();

    // Si l'app passe en arrière-plan, on se tait et on ferme le micro. Au retour, on reste
    // en pause : rouvrir le micro sans que la personne le demande serait intrusif.
    const sub = AppState.addEventListener('change', (state) => { if (state === 'background') pause(); });

    return () => {
      alive = false;
      sub.remove();
      setSpeechListener(null);
      stopAll(); // en quittant l'écran : plus de micro, plus de voix, plus de génération
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId]);

  return {
    chat: session.chat,
    aiError: session.error,
    phase, muted, heard, reply, greeting, crisis, canAskAgain, problem, level,
    allow, interrupt, pause, resume, finishNow, toggleMute, retry, stopAll,
  };
}
