// L'IA peut glisser dans sa réponse de petites balises que l'app interprète :
//   [[video: mots-clés]]      proposer des vidéos YouTube
//   [[retenir: information]]  mémoriser (uniquement si la mémoire est activée)
//   [[oublier: id | tout]]    retirer un souvenir
//   [[memoire: off]]          désactiver la mémoire à la demande de la personne
//   [[exercice: id]]          proposer un exercice de la bibliothèque
//   [[urgence]]               afficher les numéros d'aide

export type Parsed = {
  text: string;
  videos: string[];
  remember: string[];
  forget: string[];
  memoryOff: boolean;
  exercises: string[];
  crisis: boolean;
};

const TAG = /\[\[\s*(video|retenir|oublier|memoire|exercice|urgence)\s*(?::\s*([^\]\n]*?))?\s*\]\]/gi;

export function parseReply(raw: string): Parsed {
  const out: Parsed = { text: '', videos: [], remember: [], forget: [], memoryOff: false, exercises: [], crisis: false };
  let text = raw.replace(TAG, (_, kind: string, value = '') => {
    const v = String(value).trim();
    switch (kind.toLowerCase()) {
      case 'video': if (v) out.videos.push(v); break;
      case 'retenir': if (v) out.remember.push(v); break;
      case 'oublier': if (v) out.forget.push(v); break;
      case 'memoire': if (/^off$/i.test(v)) out.memoryOff = true; break;
      case 'exercice': if (v) out.exercises.push(v); break;
      case 'urgence': out.crisis = true; break;
    }
    return '';
  });
  // Balise encore en cours d'écriture pendant le streaming : on la masque.
  text = text.replace(/\[\[[^\]]*$/, '').replace(/\[$/, '');
  out.text = text.replace(/\n{3,}/g, '\n\n').trim();
  return out;
}

// Découpe un texte en phrases prêtes à être lues à voix haute.
export function splitSentences(buffer: string): { ready: string[]; rest: string } {
  const ready: string[] = [];
  let rest = buffer;
  for (;;) {
    const m = rest.match(/^([\s\S]*?[.!?…:]["»)]?)(\s+|\n+)/);
    if (!m || m[1].trim().length < 2) break;
    ready.push(m[1].trim());
    rest = rest.slice(m[0].length);
  }
  return { ready, rest };
}

export const speakable = (text: string) => text.replace(/\*\*?|__?|^#+\s*|^[-•]\s+/gm, '').replace(/\s+/g, ' ').trim();
