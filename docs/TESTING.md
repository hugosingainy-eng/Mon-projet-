# Tests

| Commande | Ce qui est vérifié |
|---|---|
| `npm test` | Consignes de l'IA (sécurité, modes, mémoire, voix), nettoyage du contexte, balises, serveur (sans clé, sortie de dossier, CORS, vidéos non inventées) |
| `npm run typecheck` | Types TypeScript de toute l'app |
| `npm run build` | L'app compile réellement (export web Expo) |
| `npm run parcours` | Toute l'app rejouée au doigt sur écran d'iPhone, dans l'aperçu publié et dans un cadre isolé (y compris stockage bloqué, confirmations et ouvertures de lien bloquées) |
| `npm run verif` | Chaque demande du propriétaire, testée dans l'app réelle sur un téléphone simulé |

## Ce que les tests ne couvrent pas
- **Les vraies réponses de l'IA** : les tests utilisent une réponse simulée, faute de clé API dans cet environnement.
- **Safari sur iPhone** : le parcours tourne sur Chromium en émulation d'iPhone, pas sur le vrai navigateur d'Apple.
- **iOS et Android** : l'app est testée dans un navigateur mobile simulé. Aucun test sur simulateur ou appareil réel.
- **Le micro et la voix** : la machine d'états est écrite, mais la parole réelle n'a pas pu être essayée.
- **Supabase** : schéma écrit, jamais exécuté sur une vraie base.
- **Vidéos vérifiées** : le chemin avec clé YouTube n'a pas été exercé.

## Scénarios à rejouer à la main avant un lancement
Personne triste · stressée · après une rupture · qui veut une réponse franche · qui veut seulement être écoutée · qui veut une solution · en vocal · qui revient après plusieurs jours · qui désactive la mémoire · qui supprime ses données · sans Internet · petit écran · environnement bruyant · situation de crise.
