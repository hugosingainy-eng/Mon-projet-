# Confie — règles de travail

Application mobile (Expo, dans `mobile/`) + serveur IA (`server.js`, `prompt.js`). Lire `docs/ARCHITECTURE.md` et `TASKS.md` avant de modifier quoi que ce soit ; lire `mobile/AGENTS.md` avant de toucher à une API Expo.

Le propriétaire du projet n'est pas développeur et écrit en français. Répondre en français simple.

## Ne rien oublier de ce qu'il demande

1. **Avant de commencer**, relire tous ses messages et découper chaque demande, même un seul mot (« Positif », « Répond »). Ne rien regrouper, ne rien interpréter à la baisse.
2. **Chaque demande nouvelle** s'ajoute à la liste `EXIGENCES` de `verif/verifier.mjs`, avec ses mots exacts et un test qui prouve qu'elle est faite dans l'application réelle.
3. **Ne jamais retirer ou remplacer** quelque chose qu'il a demandé pour faire place à une demande plus récente : les demandes s'additionnent, sauf s'il dit explicitement de remplacer.
4. **Avant de dire que c'est terminé**, lancer `npm run build`, `npm test`, `npm run typecheck` `npm run preview:build` puis `npm run verif` (qui rejoue aussi le parcours réel `verif/parcours.mjs` : aperçu publié, écran d'iPhone, au doigt) et recopier le résultat dans la réponse, y compris les lignes 🟡 (partiel) et ❌ (pas fait), avec la raison. Ne jamais présenter du partiel comme du fait.
5. Un crochet (`.claude/settings.json`) relance cette vérification à la fin de chaque réponse et bloque s'il reste un ❌.
6. Mettre à jour `TASKS.md` et `CHANGELOG.md` à chaque étape. Ne jamais confondre maquette et fonctionnalité testée.
7. Un test qui passe sur la version de développement ne prouve rien pour le propriétaire : il utilise l'aperçu publié sur son téléphone. Toute correction se vérifie avec `npm run parcours`, et toute nouvelle fonction y ajoute une étape.
8. Jamais de `confirm()`/`alert()` du navigateur, d'ouverture de lien par script, ni d'animation d'apparition qui laisse le contenu invisible si elle ne démarre pas : ces trois choses sont bloquées ou fragiles dans l'aperçu.
