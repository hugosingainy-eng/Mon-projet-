// Données de démonstration : l'application fonctionne sans aucune clé API,
// pour tester l'interface et le circuit des agents. Ajoutez vos clés dans .env
// pour passer en mode réel.

const NAMES = [
  ['Le Fournil de', 'Boulangerie'],
  ['Atelier', 'Artisan'],
  ['Chez', 'Restaurant'],
  ['Garage', 'Garage automobile'],
  ['Salon', 'Coiffeur'],
  ['Les Jardins de', 'Paysagiste'],
  ['Plomberie', 'Plombier'],
  ['Institut', 'Institut de beauté'],
];
const FIRST = ['Marie', 'Lucas', 'Sophie', 'Antoine', 'Camille', 'Hugo', 'Léa', 'Paul', 'Inès', 'Julien'];

const REVIEWS = [
  'Accueil chaleureux et travail impeccable, je recommande les yeux fermés.',
  'Très professionnel, ponctuel et des prix honnêtes.',
  'Une adresse de confiance, on y revient toujours avec plaisir.',
  'Qualité au rendez-vous, service rapide. Merci !',
];

// Quelques sites volontairement "mauvais" ou "bons" pour tester l'auditeur.
const DEMO_SITES = [
  '', '', 'http://example.com', '', 'https://example.org', '', 'http://neverssl.com', '',
];

export function demoPlaces(query, city) {
  const q = query.trim() || 'commerce';
  return Array.from({ length: 12 }, (_, i) => {
    const [prefix, cat] = NAMES[i % NAMES.length];
    const who = FIRST[(i * 3) % FIRST.length];
    const name = `${prefix} ${who}`;
    return {
      place_id: `demo-${q}-${city}-${i}`.toLowerCase().replace(/\s+/g, '-'),
      name,
      category: i % 2 ? cat : q.charAt(0).toUpperCase() + q.slice(1),
      address: `${10 + i} rue de la République, ${city}`,
      phone: `06 ${String(10 + i).padStart(2, '0')} 45 67 ${String(80 + i).slice(-2)}`,
      website: DEMO_SITES[i % DEMO_SITES.length],
      maps_url: `https://www.google.com/maps/search/${encodeURIComponent(name + ' ' + city)}`,
      rating: Math.round((3.8 + ((i * 7) % 12) / 10) * 10) / 10,
      reviews_count: 12 + i * 9,
      business_status: i === 11 ? 'CLOSED_PERMANENTLY' : 'OPERATIONAL',
      hours: [
        'lundi: 08:00–19:00', 'mardi: 08:00–19:00', 'mercredi: 08:00–19:00',
        'jeudi: 08:00–19:00', 'vendredi: 08:00–19:00', 'samedi: 09:00–13:00', 'dimanche: Fermé',
      ],
      summary: '',
      reviews: REVIEWS.map((text, k) => ({ author: FIRST[(i + k) % FIRST.length], rating: 5 - (k % 2), text })),
      photos: Array.from({ length: 5 }, (_, k) => ({
        name: `demo-${i}-${k}`,
        demoUrl: `https://picsum.photos/seed/${encodeURIComponent(cat)}-${i}-${k}/1200/800`,
        attributions: ['Démo'],
      })),
      location: null,
    };
  });
}
