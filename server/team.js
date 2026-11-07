// Organigramme de l'agence : le Boss, ses 4 chefs d'équipe, et les sous-agents de chacun.
// + suivi en direct de qui travaille + délégation chef → sous-agent avec contrôle.
import { logMessage } from './db.js';

export const TEAM = [
  {
    name: 'Boss', ico: '👔', role: 'Supervise, vérifie et valide tout. Renvoie le travail s’il n’est pas au niveau.',
    helpers: [
      { name: 'Contrôleur qualité', ico: '📏', role: 'Applique les contrôles automatiques non négociables.' },
      { name: 'Relecteur critique', ico: '🧐', role: 'Relit chaque livrable avec un œil exigeant et note sur 10.' },
    ],
  },
  {
    name: 'Prospecteur', ico: '🧭', role: 'Cherche les entreprises sur Google Maps et repère celles sans site.',
    helpers: [
      { name: 'Éclaireur', ico: '🔭', role: 'Élargit la recherche avec des variantes du métier.' },
      { name: 'Qualificateur', ico: '🎯', role: 'Classe les prospects par priorité commerciale.' },
      { name: 'Vérificateur de site', ico: '🌐', role: 'Cherche sur Google si le commerce a vraiment aucun site.' },
      { name: 'Détective email', ico: '📧', role: 'Trouve l’email sur tout le web : Google, annuaires, Facebook…' },
    ],
  },
  {
    name: 'Auditeur', ico: '🔎', role: 'Analyse les sites existants et détecte ceux de mauvaise qualité.',
    helpers: [
      { name: 'Technicien', ico: '🛠️', role: 'HTTPS, mobile, vitesse, technologies obsolètes.' },
      { name: 'Analyste SEO', ico: '📈', role: 'Référencement, balises, scores PageSpeed.' },
      { name: 'Enquêteur contact', ico: '🕵️', role: 'Fouille les pages contact pour trouver l’email.' },
    ],
  },
  {
    name: 'Créateur de site', ico: '🎨', role: 'Crée un site vitrine à partir des photos et avis Google Maps.',
    helpers: [
      { name: 'Photographe', ico: '📷', role: 'Récupère les photos et choisit la meilleure pour l’accueil.' },
      { name: 'Rédacteur web', ico: '🖋️', role: 'Écrit les textes du site à partir des vrais avis.' },
      { name: 'Intégrateur', ico: '💻', role: 'Assemble le site : design, mise en page, mobile.' },
    ],
  },
  {
    name: 'Rédacteur', ico: '✉️', role: 'Rédige l’email personnalisé et la carte numérique.',
    helpers: [
      { name: 'Analyste prospect', ico: '🧩', role: 'Trouve les détails qui rendent l’email personnel.' },
      { name: 'Plume', ico: '✍️', role: 'Écrit l’objet et le message.' },
      { name: 'Correcteur', ico: '🔤', role: 'Vérifie ton, longueur, lien et anti-spam avant le Boss.' },
      { name: 'Designer carte', ico: '🪪', role: 'Met en forme la carte numérique aux couleurs du métier.' },
    ],
  },
];

// ---------- Activité en direct ----------
const active = new Map();

export async function track(name, fn) {
  active.set(name, (active.get(name) || 0) + 1);
  try {
    return await fn();
  } finally {
    const n = (active.get(name) || 1) - 1;
    if (n <= 0) active.delete(name);
    else active.set(name, n);
  }
}

export function activity() {
  return Object.fromEntries(active);
}

// ---------- Délégation à un sous-agent ----------
/**
 * Le chef confie une tâche à un sous-agent, contrôle le résultat et le lui
 * renvoie à corriger si besoin, avant de s'en servir.
 * @param {object} p
 * @param {object|null} p.ctx      { missionId, leadId } (null = pas de journal, ex. tests)
 * @param {string} p.chef
 * @param {string} p.helper
 * @param {string} p.task          consigne lisible
 * @param {(feedback: string) => Promise<any>} p.run
 * @param {(result: any) => string|null} [p.check]   renvoie un problème, ou null si OK
 * @param {(result: any) => string} [p.summary]
 * @param {number} [p.maxTries]
 */
export async function delegate({ ctx, chef, helper, task, run, check, summary, maxTries = 2 }) {
  const log = (from, to, kind, content) =>
    ctx && logMessage({ ...ctx, from, to, kind, content, level: 1 });

  log(chef, helper, 'consigne', task);
  let feedback = '';
  let result;
  for (let attempt = 1; attempt <= maxTries; attempt++) {
    result = await track(helper, () => run(feedback));
    const problem = check ? check(result) : null;
    if (!problem) {
      log(helper, chef, 'sous-livraison', summary ? summary(result) : 'Terminé.');
      return result;
    }
    if (attempt < maxTries) log(chef, helper, 'correction', `À reprendre : ${problem}`);
    feedback = problem;
  }
  // Le chef accepte le dernier essai mais le signale : le Boss tranchera.
  log(chef, helper, 'correction', `Toujours imparfait (${feedback}) : je transmets quand même au Boss.`);
  return result;
}
