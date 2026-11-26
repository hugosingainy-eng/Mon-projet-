// Les façons d'être aidé, choisies par la personne pour une conversation.
export const MODES = [
  { id: 'ecoute', label: 'Écoute-moi', hint: 'Je te laisse parler, sans conseil.' },
  { id: 'comprendre', label: 'Aide-moi à comprendre', hint: 'On démêle ce qui se passe.' },
  { id: 'honnete', label: 'Sois honnête', hint: 'Je te dis ce que je vois.' },
  { id: 'rassure', label: 'Rassure-moi', hint: 'On fait redescendre la pression.' },
  { id: 'solutions', label: 'Trouve des solutions', hint: 'Du concret, étape par étape.' },
  { id: 'challenge', label: 'Challenge-moi', hint: 'Je te bouscule pour avancer.' },
  { id: 'motive', label: 'Motive-moi', hint: 'De l\'élan, et un premier pas.' },
] as const;
export type ModeId = (typeof MODES)[number]['id'];

// Le style général de l'IA (réglage durable).
export const STYLES = [
  { id: 'douce', label: 'Douce et bienveillante', hint: 'Empathique, calme, patiente.' },
  { id: 'franche', label: 'Franche et directe', hint: 'Honnête, sans détour, jamais agressive.' },
  { id: 'positive', label: 'Positive et motivante', hint: 'Encouragements réalistes, actions concrètes.' },
  { id: 'ecoute', label: 'Écoute d\'abord', hint: 'Reformule, questionne, ne précipite rien.' },
  { id: 'analyse', label: 'Analyse et solutions', hint: 'Sépare faits et interprétations, construit un plan.' },
] as const;
export type StyleId = (typeof STYLES)[number]['id'];

export const TOPICS = [
  { id: 'amour', label: 'Amour et relations', starter: 'J\'aimerais parler de ma vie amoureuse.' },
  { id: 'moral', label: 'Moral et émotions', starter: 'Je ne me sens pas très bien en ce moment.' },
  { id: 'stress', label: 'Stress et anxiété', starter: 'Je suis stressé·e et j\'ai du mal à me calmer.' },
  { id: 'confiance', label: 'Confiance en soi', starter: 'Je manque de confiance en moi.' },
  { id: 'motivation', label: 'Motivation', starter: 'Je n\'arrive plus à me motiver.' },
  { id: 'solitude', label: 'Solitude', starter: 'Je me sens seul·e.' },
  { id: 'autre', label: 'Autre sujet', starter: '' },
] as const;
export type TopicId = (typeof TOPICS)[number]['id'];

export const EMOTIONS = [
  'Calme', 'Joie', 'Gratitude', 'Espoir', 'Fierté', 'Fatigue', 'Tristesse', 'Anxiété',
  'Colère', 'Solitude', 'Honte', 'Jalousie', 'Culpabilité', 'Confusion', 'Manque', 'Vide',
] as const;

export const MOOD_LABELS = ['Très difficile', 'Difficile', 'Moyen', 'Plutôt bien', 'Très bien'] as const;
