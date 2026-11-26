# Confie

Une application d'accompagnement émotionnel par intelligence artificielle. Un espace personnel et confidentiel, ouvert à toute heure, pour parler librement — par écrit ou à voix haute — de ce qu'on n'ose parfois dire à personne.

> « Tu peux tout dire. Ici, tu n'as pas à faire semblant. »

Confie est une IA. Elle ne remplace ni un psychologue ni un médecin, et le dit clairement.

## Ce que contient l'application

- **Conversation** écrite avec réponses au fil de l'eau, historique, renommage, suppression, conversations temporaires.
- **Sept façons d'être aidé** (Écoute-moi, Aide-moi à comprendre, Sois honnête, Rassure-moi, Trouve des solutions, Challenge-moi, Motive-moi), cinq styles de communication et trois niveaux de franchise.
- **Mode vocal** mains libres : je t'écoute, je réfléchis, je te réponds, avec interruption, micro coupé et transcription.
- **Mémoire facultative**, visible et modifiable (« Ce que mon IA retient »).
- **Suivi d'humeur**, **journal** privé, **bibliothèque de 13 exercices** issus de techniques reconnues, **progrès** et objectifs.
- **Vidéos YouTube** recommandées selon le sujet, jamais inventées.
- **Aide urgente** toujours accessible (3114, 15, 112, 3919, 119, 114).
- Thème clair et sombre, export et suppression de toutes ses données.

## État réel du projet

L'app compile et fonctionne ; elle a été testée dans un navigateur mobile simulé avec des réponses d'IA simulées. Elle n'est pas encore publiée. Pour qu'elle réponde vraiment et soit disponible 24h/24, il faut les éléments ci-dessous, que seul le propriétaire peut fournir.

| À fournir | Pour quoi faire |
|---|---|
| Clé API Anthropic | Que l'IA réponde |
| Hébergement du serveur | Que l'app soit joignable 24h/24 |
| Clé YouTube Data API | Des vidéos vérifiées plutôt qu'un lien de recherche |
| Projet Supabase | Comptes et synchronisation entre appareils |
| Comptes développeur Apple et Google | Publier sur l'App Store et Google Play |

Le détail de ce qui est fait, partiel ou à faire est dans [`TASKS.md`](TASKS.md).

## Démarrer

```bash
npm install && (cd mobile && npm install)
npm run build                       # construit la version web de l'app
ANTHROPIC_API_KEY=... npm start     # ouvre http://localhost:3000
```

Vérifications : `npm test` · `npm run typecheck` · `npm run verif`.

## Documentation

| Document | Contenu |
|---|---|
| [`TASKS.md`](TASKS.md) | Tâches faites, en cours, bloquées, à venir |
| [`ROADMAP.md`](ROADMAP.md) | Étapes jusqu'au lancement |
| [`CHANGELOG.md`](CHANGELOG.md) | Historique des versions |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Comment l'ensemble est construit |
| [`docs/DESIGN-SYSTEM.md`](docs/DESIGN-SYSTEM.md) | Couleurs, typographie, composants |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Sécurité, confidentialité, limites connues |
| [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md) | Clés et configuration |
| [`docs/TESTING.md`](docs/TESTING.md) | Tests et ce qu'ils ne couvrent pas |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Décisions produit et techniques |
| [`docs/RECHERCHE-VOIX-COUTS.md`](docs/RECHERCHE-VOIX-COUTS.md) | Options vocales, coûts, prix, points juridiques |
| [`docs/legal/`](docs/legal) | Brouillons : politique de confidentialité et conditions d'utilisation |
