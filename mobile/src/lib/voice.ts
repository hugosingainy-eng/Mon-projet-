// Moteur vocal de Confie : écouter (expo-speech-recognition) et parler (expo-speech).
//
// Limites réelles, à connaître avant de toucher à ce fichier :
// - Sur iOS et Android, la reconnaissance vocale est un module natif absent d'Expo Go :
//   il faut un « development build ». Dans Expo Go, tout ce fichier répond « unavailable ».
// - Sur le web, tout dépend de l'API Web Speech du navigateur : Chrome, Edge et Safari
//   la proposent, Firefox non. La transcription y passe par les serveurs du navigateur.
// - Sur mobile aussi, la voix est transcrite par le service du système (Apple, Google),
//   le plus souvent en ligne : sans réseau, l'écoute peut échouer (« network »).
// - On n'écoute jamais pendant que l'app parle : le micro entendrait la voix de synthèse
//   et la prendrait pour la personne. L'interruption se fait donc au toucher, pas à la voix.
// - Android 12 et antérieur ne connaît pas l'écoute continue : on relance la reconnaissance
//   après chaque segment, ce qui peut faire entendre le « bip » du système sur certains appareils.

import * as Speech from 'expo-speech';
import { Platform } from 'react-native';

import { useSettings } from '@/store/settings';

const LANG = 'fr-FR';

type SpeechRecognitionPackage = typeof import('expo-speech-recognition');
type Recognizer = SpeechRecognitionPackage['ExpoSpeechRecognitionModule'];
type RecognitionOptions = import('expo-speech-recognition').ExpoSpeechRecognitionOptions;
type Timer = ReturnType<typeof setTimeout>;

// ——————————————————————————————————————————————————————————————
// Disponibilité
// ——————————————————————————————————————————————————————————————

let recognizer: Recognizer | null | undefined;

/** Le module de reconnaissance, ou null s'il n'existe pas ici (Expo Go, Firefox…). */
function getRecognizer(): Recognizer | null {
  if (recognizer !== undefined) return recognizer;
  try {
    // Chargement différé : importer le paquet en tête de fichier ferait planter l'écran
    // entier là où le module natif est absent (Expo Go).
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = (require('expo-speech-recognition') as SpeechRecognitionPackage).ExpoSpeechRecognitionModule;
    recognizer = mod.isRecognitionAvailable() ? mod : null;
  } catch {
    recognizer = null;
  }
  return recognizer;
}

/** Vrai si cet appareil ou ce navigateur sait transcrire la voix. */
export function isRecognitionAvailable(): boolean {
  return getRecognizer() !== null;
}

// ——————————————————————————————————————————————————————————————
// Permission du micro
// ——————————————————————————————————————————————————————————————

export type MicStatus = 'granted' | 'denied' | 'undetermined' | 'unavailable';
export type MicPermission = { status: MicStatus; canAskAgain: boolean };

// Le strict nécessaire de l'API du navigateur, sans dépendre des types DOM.
type WebNavigator = {
  permissions?: { query: (d: { name: string }) => Promise<{ state: 'granted' | 'denied' | 'prompt' }> };
  mediaDevices?: { getUserMedia: (c: { audio: boolean }) => Promise<{ getTracks: () => { stop: () => void }[] }> };
};
const webNavigator = () => (globalThis as { navigator?: WebNavigator }).navigator;

/** État actuel de la permission, sans rien demander à la personne. */
export async function getMicPermission(): Promise<MicPermission> {
  const mod = getRecognizer();
  if (!mod) return { status: 'unavailable', canAskAgain: false };
  if (Platform.OS === 'web') {
    // Sur le web le paquet répond toujours « granted » : on interroge le navigateur.
    // Safari et Firefox ne savent pas répondre pour le micro : on considère « à demander ».
    try {
      const res = await webNavigator()?.permissions?.query({ name: 'microphone' });
      if (res?.state === 'granted') return { status: 'granted', canAskAgain: true };
      if (res?.state === 'denied') return { status: 'denied', canAskAgain: false };
    } catch { /* navigateur qui ne connaît pas cette requête */ }
    return { status: 'undetermined', canAskAgain: true };
  }
  try {
    const res = await mod.getPermissionsAsync();
    if (res.granted) return { status: 'granted', canAskAgain: true };
    if (res.status === 'undetermined') return { status: 'undetermined', canAskAgain: true };
    return { status: 'denied', canAskAgain: res.canAskAgain };
  } catch {
    return { status: 'unavailable', canAskAgain: false };
  }
}

/**
 * Demande le micro (et, sur iOS, la reconnaissance vocale).
 * Trois issues possibles : 'granted', 'denied' ou 'unavailable'.
 */
export async function requestMicPermission(): Promise<MicPermission> {
  const mod = getRecognizer();
  if (!mod) return { status: 'unavailable', canAskAgain: false };
  if (Platform.OS === 'web') {
    const media = webNavigator()?.mediaDevices;
    // Pas de mediaDevices : page non sécurisée (http) ou navigateur trop ancien.
    if (!media) return { status: 'unavailable', canAskAgain: false };
    try {
      const stream = await media.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop()); // on ne garde rien : c'était juste pour la permission
      return { status: 'granted', canAskAgain: true };
    } catch (e) {
      const kind = (e as { name?: string })?.name;
      if (kind === 'NotFoundError' || kind === 'OverconstrainedError') return { status: 'unavailable', canAskAgain: false };
      return { status: 'denied', canAskAgain: false };
    }
  }
  try {
    const res = await mod.requestPermissionsAsync();
    return res.granted ? { status: 'granted', canAskAgain: true } : { status: 'denied', canAskAgain: res.canAskAgain };
  } catch {
    return { status: 'unavailable', canAskAgain: false };
  }
}

// ——————————————————————————————————————————————————————————————
// Écoute
// ——————————————————————————————————————————————————————————————

export type ListenErrorCode =
  | 'unavailable' // pas de reconnaissance vocale ici
  | 'not-allowed' // micro ou reconnaissance refusés
  | 'network' // le service de transcription est injoignable
  | 'audio-capture' // micro inaccessible (pris par un appel, absent…)
  | 'language-not-supported' // le français n'est pas installé sur l'appareil
  | 'unknown';

export type ListenHandlers = {
  /** Le micro est ouvert. */
  onStart?: () => void;
  /** Ce qui est compris jusqu'ici, pendant que la personne parle. */
  onPartial?: (text: string) => void;
  /** Un segment vient d'être confirmé par le système ; `text` est tout ce qui est confirmé. */
  onFinal?: (text: string) => void;
  /** La personne a fini de parler : `text` est sa phrase entière. L'écoute est déjà arrêtée. */
  onEndOfSpeech: (text: string) => void;
  /** Erreur qui empêche d'écouter. L'écoute est déjà arrêtée. */
  onError?: (code: ListenErrorCode, message: string) => void;
  /** Niveau sonore entre 0 et 1 (iOS et Android seulement ; jamais émis sur le web). */
  onVolume?: (level: number) => void;
};

// Silence toléré avant de considérer que la personne a fini. Volontairement long :
// quand on se confie, on cherche ses mots. Plus court une fois que le système a
// lui-même confirmé un segment (il a déjà détecté une pause).
const SILENCE_MS = 2000;
const SILENCE_AFTER_FINAL_MS = 1300;
const MAX_FAILURES = 3;

type ListenSession = {
  id: number;
  handlers: ListenHandlers;
  finals: string[];
  interim: string;
  failures: number; // erreurs consécutives sans aucun résultat
  startedAt: number;
  silence: Timer | null;
  restart: Timer | null;
  subs: { remove: () => void }[];
};

let listenGen = 0;
let current: ListenSession | null = null;

const RECOGNITION_OPTIONS: RecognitionOptions = {
  lang: LANG,
  interimResults: true,
  continuous: true,
  maxAlternatives: 1,
  addsPunctuation: true,
  iosTaskHint: 'dictation',
  // Mode « default » plutôt que « measurement » (le défaut du paquet), qui baisse le volume
  // de la voix de synthèse jouée ensuite dans la même session audio.
  iosCategory: { category: 'playAndRecord', categoryOptions: ['defaultToSpeaker', 'allowBluetooth'], mode: 'default' },
  volumeChangeEventOptions: { enabled: true, intervalMillis: 150 },
};

// Au moins deux lettres : écarte les finals vides et les bruits transcrits en « h », « . », « ! ».
// « oui », « non », « ok » passent.
const meaningful = (text: string) => (text.match(/\p{L}/gu)?.length ?? 0) >= 2;
const heardSoFar = (s: ListenSession) => [...s.finals, s.interim].map((t) => t.trim()).filter(Boolean).join(' ');

function teardown(s: ListenSession) {
  if (s.silence) clearTimeout(s.silence);
  if (s.restart) clearTimeout(s.restart);
  s.silence = s.restart = null;
  s.subs.forEach((sub) => { try { sub.remove(); } catch { /* déjà retiré */ } });
  s.subs = [];
  if (current === s) current = null;
  listenGen++;
  try { getRecognizer()?.abort(); } catch { /* rien n'était en cours */ }
}

function fatal(s: ListenSession, code: ListenErrorCode, message: string) {
  if (current !== s) return;
  teardown(s);
  s.handlers.onError?.(code, message);
}

function finish(s: ListenSession) {
  if (current !== s) return;
  const text = heardSoFar(s);
  if (!meaningful(text)) {
    // Du bruit, pas une phrase : on efface et on continue d'écouter.
    s.finals = [];
    s.interim = '';
    s.handlers.onPartial?.('');
    return;
  }
  teardown(s);
  s.handlers.onEndOfSpeech(text);
}

function armSilence(s: ListenSession) {
  if (s.silence) clearTimeout(s.silence);
  s.silence = null;
  if (!heardSoFar(s)) return;
  s.silence = setTimeout(() => finish(s), s.interim.trim() ? SILENCE_MS : SILENCE_AFTER_FINAL_MS);
}

function begin(s: ListenSession) {
  const mod = getRecognizer();
  if (current !== s || !mod) return;
  s.startedAt = Date.now();
  try {
    mod.start(RECOGNITION_OPTIONS);
  } catch (e) {
    fail(s, e instanceof Error ? e.message : 'start');
  }
}

function scheduleRestart(s: ListenSession, delay: number) {
  if (current !== s || s.restart) return;
  s.restart = setTimeout(() => { s.restart = null; begin(s); }, delay);
}

// Erreur passagère (service occupé, session audio interrompue…) : on réessaie quelques fois
// en espaçant, puis on renonce calmement.
function fail(s: ListenSession, message: string) {
  if (current !== s) return;
  s.failures++;
  if (s.failures > MAX_FAILURES) fatal(s, 'unknown', message);
  else scheduleRestart(s, 350 * s.failures);
}

/**
 * Ouvre le micro et écoute, mains libres, jusqu'à ce que la personne ait fini de parler.
 * Une seule écoute à la fois : en démarrer une nouvelle arrête la précédente.
 */
export function startListening(handlers: ListenHandlers): void {
  stopListening();
  const mod = getRecognizer();
  if (!mod) { handlers.onError?.('unavailable', 'Reconnaissance vocale indisponible.'); return; }

  const s: ListenSession = { id: ++listenGen, handlers, finals: [], interim: '', failures: 0, startedAt: 0, silence: null, restart: null, subs: [] };
  current = s;
  // Sur le web, un écouteur retiré peut encore recevoir les derniers évènements de
  // l'ancienne reconnaissance : chaque rappel vérifie donc qu'il parle bien de l'écoute en cours.
  const live = () => current === s;

  s.subs = [
    mod.addListener('start', () => { if (live()) handlers.onStart?.(); }),
    mod.addListener('result', (ev) => {
      if (!live()) return;
      const text = (ev.results[0]?.transcript ?? '').trim();
      const before = heardSoFar(s);
      if (ev.isFinal) {
        s.interim = '';
        if (meaningful(text)) { s.finals.push(text); handlers.onFinal?.(s.finals.join(' ')); }
      } else {
        s.interim = text;
      }
      if (text) s.failures = 0;
      const now = heardSoFar(s);
      // Le minuteur de silence ne repart que si le texte a vraiment changé : un fond sonore
      // qui renvoie sans cesse le même résultat ne retient pas la conversation.
      if (now !== before) { handlers.onPartial?.(now); armSilence(s); } else if (ev.isFinal) armSilence(s);
    }),
    mod.addListener('volumechange', (ev) => {
      // Le paquet annonce une valeur entre -2 et 10.
      if (live()) handlers.onVolume?.(Math.min(1, Math.max(0, (ev.value + 2) / 12)));
    }),
    mod.addListener('error', (ev) => {
      if (!live()) return;
      switch (ev.error) {
        case 'aborted': // c'est nous
          break;
        case 'no-speech':
        case 'speech-timeout':
          // Personne n'a parlé : ce n'est pas une erreur, on reste à l'écoute.
          scheduleRestart(s, 250);
          break;
        case 'not-allowed':
        case 'service-not-allowed':
          fatal(s, 'not-allowed', ev.message);
          break;
        case 'network':
        case 'audio-capture':
        case 'language-not-supported':
          fatal(s, ev.error, ev.message);
          break;
        default:
          fail(s, ev.message);
      }
    }),
    mod.addListener('end', () => {
      if (!live() || s.restart) return; // une relance est déjà prévue (suite à une erreur)
      // La reconnaissance s'arrête d'elle-même (silence, limite de durée du navigateur ou du
      // système, absence d'écoute continue). Tant que la personne n'a pas fini, on la relance.
      // Garde-fou : des arrêts immédiats à répétition comptent comme des échecs.
      if (Date.now() - s.startedAt < 400) fail(s, 'La reconnaissance s\'arrête aussitôt lancée.');
      else scheduleRestart(s, 120);
    }),
  ];
  begin(s);
}

/** Ferme le micro tout de suite. Ce qui était en cours de transcription est abandonné. */
export function stopListening(): void {
  if (current) teardown(current);
}

/**
 * « J'ai fini » : envoie tout de suite ce qui a été compris, sans attendre le silence.
 * Utile dans un endroit bruyant, où le silence n'arrive jamais. Renvoie false s'il n'y avait rien.
 */
export function finishListening(): boolean {
  const s = current;
  if (!s || !meaningful(heardSoFar(s))) return false;
  finish(s);
  return true;
}

export const isListening = () => current !== null;

// ——————————————————————————————————————————————————————————————
// Voix françaises
// ——————————————————————————————————————————————————————————————

export type FrenchVoice = { id: string; name: string };
type KnownVoice = FrenchVoice & { language: string; enhanced: boolean };

let voicesCache: KnownVoice[] | null = null;

const timeout = <T,>(ms: number, value: T) => new Promise<T>((resolve) => setTimeout(() => resolve(value), ms));
const REGIONS: Record<string, string> = { fr: 'France', ca: 'Canada', be: 'Belgique', ch: 'Suisse' };

async function loadFrenchVoices(): Promise<KnownVoice[]> {
  if (voicesCache) return voicesCache;
  let all: Speech.Voice[] = [];
  try {
    // Sur le web, la liste peut ne jamais arriver (aucune voix installée) : on n'attend pas indéfiniment.
    all = await Promise.race([Speech.getAvailableVoicesAsync(), timeout<Speech.Voice[]>(1500, [])]);
  } catch { /* synthèse vocale absente */ }

  const seen = new Set<string>();
  const french = all
    .filter((v) => /^fr([-_]|$)/i.test(v.language) && !seen.has(v.identifier) && !!seen.add(v.identifier))
    .map((v) => ({ v, region: v.language.split(/[-_]/)[1]?.toLowerCase() ?? 'fr', enhanced: v.quality === Speech.VoiceQuality.Enhanced }))
    // France d'abord, puis les voix de meilleure qualité.
    .sort((a, b) => Number(b.region === 'fr') - Number(a.region === 'fr') || Number(b.enhanced) - Number(a.enhanced));

  let anonymous = 0;
  const voices = french.map(({ v, region, enhanced }): KnownVoice => {
    // Android nomme ses voix par un code (« fr-fr-x-vlf-local ») : on leur donne un nom lisible.
    const coded = /^[a-z]{2,3}[-_]/i.test(v.name) || v.name === v.identifier && /[-_#.]/.test(v.name);
    const base = coded ? `Voix ${++anonymous}` : v.name.replace(/\s*\(.*\)\s*$/, '');
    const details = [region !== 'fr' ? REGIONS[region] : null, enhanced ? 'haute qualité' : null].filter(Boolean);
    return { id: v.identifier, name: details.length ? `${base} (${details.join(', ')})` : base, language: v.language.replace('_', '-'), enhanced };
  });
  if (voices.length) voicesCache = voices; // une liste vide peut être un chargement trop précoce : on redemandera
  return voices;
}

/** Les voix françaises installées sur l'appareil, pour l'écran de réglages. Peut être vide. */
export async function listFrenchVoices(): Promise<FrenchVoice[]> {
  return (await loadFrenchVoices()).map(({ id, name }) => ({ id, name }));
}

// ——————————————————————————————————————————————————————————————
// Parole : file de phrases
// ——————————————————————————————————————————————————————————————

export type SpeechListener = {
  /** Une phrase commence à être dite. */
  onStart?: () => void;
  /** Tout ce qui était en file a été dit. N'est pas appelé après `stopSpeaking()`. */
  onEmpty?: () => void;
};

let speakGen = 0;
let waiting = 0; // phrases confiées à la synthèse et pas encore terminées
let waitingChars = 0;
let chain: Promise<void> = Promise.resolve();
let watchdog: Timer | null = null;
let listener: SpeechListener | null = null;

/** Un seul écouteur à la fois (l'écran vocal). Passer null pour se désabonner. */
export function setSpeechListener(next: SpeechListener | null): void {
  listener = next;
}

/** Vrai quand il ne reste plus rien à dire. */
export const speechQueueEmpty = () => waiting === 0;

const currentRate = () => {
  const rate = useSettings.getState().voiceRate;
  return Number.isFinite(rate) ? Math.min(1.5, Math.max(0.5, rate)) : 1;
};

// Si la synthèse ne signale jamais la fin (moteur absent, navigateur qui bloque le son),
// on ne laisse pas la conversation figée sur « Je te réponds ».
function armWatchdog() {
  if (watchdog) clearTimeout(watchdog);
  watchdog = null;
  if (waiting === 0) return;
  const gen = speakGen;
  watchdog = setTimeout(() => {
    if (gen !== speakGen) return;
    stopSpeaking();
    listener?.onEmpty?.();
  }, 8000 + (waitingChars * 130) / currentRate());
}

async function pickVoice(): Promise<{ id?: string; language: string }> {
  const voices = await loadFrenchVoices();
  const wanted = useSettings.getState().voiceId;
  // On ne transmet un identifiant que s'il existe vraiment : sur le web, un identifiant
  // inconnu ferait parler la première voix venue, pas forcément française.
  const chosen = voices.find((v) => v.id === wanted) ?? voices.find((v) => v.enhanced && v.language.toLowerCase() === 'fr-fr');
  return chosen ? { id: chosen.id, language: chosen.language } : { language: LANG };
}

/**
 * Ajoute une phrase à dire. Les phrases sont lues dans l'ordre, à la suite ;
 * on peut en ajouter pendant que les précédentes sont dites.
 */
export function speakSentence(sentence: string): void {
  const text = sentence.trim().slice(0, Speech.maxSpeechInputLength);
  if (!text) return;
  const gen = speakGen;
  waiting++;
  waitingChars += text.length;
  armWatchdog();

  let settled = false;
  const done = () => {
    if (settled || gen !== speakGen) return;
    settled = true;
    waiting = Math.max(0, waiting - 1);
    waitingChars = Math.max(0, waitingChars - text.length);
    armWatchdog();
    if (waiting === 0) listener?.onEmpty?.();
  };

  chain = chain.then(async () => {
    const voice = await pickVoice();
    if (gen !== speakGen) return; // interrompu pendant le choix de la voix
    try {
      Speech.speak(text, {
        language: voice.language,
        voice: voice.id,
        rate: currentRate(),
        pitch: 1,
        onStart: () => { if (gen === speakGen) listener?.onStart?.(); },
        onDone: done,
        onStopped: done,
        onError: done,
      });
    } catch {
      done();
    }
  });
}

/** Se tait immédiatement et vide la file. */
export function stopSpeaking(): void {
  speakGen++;
  waiting = 0;
  waitingChars = 0;
  chain = Promise.resolve();
  if (watchdog) clearTimeout(watchdog);
  watchdog = null;
  Speech.stop().catch(() => {});
}
