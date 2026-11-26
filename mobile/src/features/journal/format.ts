// Questions guidées, facultatives. Volontairement ouvertes et sans injonction.
export const JOURNAL_PROMPTS = [
  'Qu\'est-ce qui a pris le plus de place dans ta tête aujourd\'hui ?',
  'Qu\'est-ce que tu n\'as dit à personne aujourd\'hui ?',
  'De quoi aurais-tu besoin, là, maintenant ?',
  'Qu\'est-ce qui t\'a fait du bien récemment, même un tout petit peu ?',
  'Qu\'est-ce que tu ressens dans ton corps en ce moment ?',
  'Si un ami vivait ce que tu vis, que lui dirais-tu ?',
  'Qu\'est-ce que tu aimerais laisser derrière toi ce soir ?',
  'Qu\'est-ce qui t\'inquiète, et qu\'est-ce qui dépend vraiment de toi ?',
  'De quoi es-tu un peu fier ou fière cette semaine ?',
  'Qu\'est-ce que tu aimerais que demain t\'apporte ?',
] as const;

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const sameDay = (a: Date, b: Date) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
const time = (d: Date) => d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

/** Date courte pour la liste : « Aujourd'hui, 21:40 », « Hier, 08:12 », « Mardi 3 novembre ». */
export function entryDate(at: number): string {
  const d = new Date(at);
  const now = new Date();
  if (sameDay(d, now)) return `Aujourd'hui, ${time(d)}`;
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  if (sameDay(d, yesterday)) return `Hier, ${time(d)}`;
  const sameYear = d.getFullYear() === now.getFullYear();
  return cap(d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', ...(sameYear ? {} : { year: 'numeric' }) }));
}

/** Date complète pour l'éditeur : « Jeudi 26 novembre 2026, 21:40 ». */
export function fullDate(at: number): string {
  const d = new Date(at);
  return `${cap(d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }))}, ${time(d)}`;
}
