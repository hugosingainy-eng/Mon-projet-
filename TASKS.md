# Tâches

Légende : ✅ fait et vérifié · 🟡 partiel · ⛔ bloqué (dépend du propriétaire) · ⬜ à faire

## Fait

| | Tâche | Preuve |
|---|---|---|
| ✅ | Projet Expo 58 (TypeScript, Expo Router), design system, thème clair et sombre | `npm run typecheck`, `npm run build`, lint sans erreur |
| ✅ | Bienvenue, onboarding en 6 étapes passables, consentement explicite | `npm run verif` |
| ✅ | Accueil personnalisé, cases de sujets (amour, moral, stress, confiance, motivation, solitude, autre) | `npm run verif` |
| ✅ | Conversation : réponses au fil de l'eau, indicateur, historique, nouveau, renommer, supprimer, reprendre, suggestions, erreurs et reprise hors connexion | `npm run verif` |
| ✅ | Sept modes d'aide (question posée à chaque conversation), cinq styles, trois niveaux de franchise | `npm run verif` |
| ✅ | Mémoire facultative, page « Ce que mon IA retient », commandes « oublie », « supprime tout », « désactive » | `npm run verif` |
| ✅ | Conversations temporaires, ni enregistrées ni mémorisées | `npm run verif` |
| ✅ | Suivi d'humeur, graphique sur 14 jours, tendances en mots, sans diagnostic | `npm run verif` |
| ✅ | Journal privé, questions guidées, non partagé avec l'IA par défaut | `npm run verif` |
| ✅ | 13 exercices sourcés, respiration guidée animée, retour « ça t'a aidé ? » | `npm run verif`, `npm test` |
| ✅ | Progrès : humeur, émotions, exercices, journal, objectifs | `npm run verif` |
| ✅ | Profil et réglages, export et suppression de toutes les données | `npm run verif` |
| ✅ | Aide urgente (3114, 15, 112, 3919, 119, 114), carte de crise dans le chat | `npm run verif` |
| ✅ | Serveur IA : consignes, contexte nettoyé, streaming, limites, en-têtes de sécurité | `npm test` |
| ✅ | Consignes de l'IA : personnalité, moteur de conversation, solutions réelles, sécurité | `npm test` |
| ✅ | Schéma Supabase avec RLS sur toutes les tables | relecture + test statique |
| ✅ | Étude des options vocales, des coûts et du modèle freemium | `docs/RECHERCHE-VOIX-COUTS.md` |
| ✅ | Vérification automatique des demandes à chaque fin de réponse | `verif/verifier.mjs`, `.claude/settings.json` |
| ✅ | Documentation complète et brouillons juridiques | `docs/` |

| ✅ | Accueil illustré d'après les références du propriétaire (carte verte, visages d'humeur, cartes illustrées) | `npm run verif` |
| ✅ | Aperçu en ligne avec IA branchée (lien dans le README) | testé localement avec une IA simulée ; non vérifié dans la page publiée |

## Partiel

| | Tâche | Ce qui manque |
|---|---|---|
| 🟡 | Mode vocal | Écran, machine d'états et moteur écrits ; jamais essayé avec un vrai micro. Interruption au toucher, pas à la voix. Sur téléphone il faut un build de développement |
| 🟡 | Vidéos YouTube | Le chemin « vidéos vérifiées » existe mais n'a pas été exercé faute de clé ; sans clé, lien de recherche |
| 🟡 | Comptes | Écran de connexion et client Supabase prêts ; aucune synchronisation des données |
| 🟡 | iOS / Android | Code commun qui compile ; testé uniquement en version web |
| 🟡 | Notifications | La préférence est enregistrée ; aucun rappel n'est réellement programmé |
| 🟡 | Images | Illustration vectorielle maison, référence générée avec Canva ; pas de photos (connecteurs à connecter par le propriétaire) |
| 🟡 | Qualité du design | Écrans cohérents et calmes ; auto-évaluation autour de 8/10, pas encore le 9/10 visé. Seuls l'accueil, la bienvenue et le point d'humeur suivent les nouvelles références ; journal, exercices, progrès et profil restent à illustrer dans le même style |

## Bloqué — dépend du propriétaire

| | Tâche | Ce qu'il faut |
|---|---|---|
| ⛔ | Vraies réponses de l'IA | Une clé API Anthropic |
| ⛔ | Disponibilité 24h/24 et lien public | Un hébergement pour le serveur |
| ⛔ | Vidéos vérifiées | Une clé YouTube Data API |
| ⛔ | Comptes et synchronisation | Un projet Supabase |
| ⛔ | Publication | Comptes développeur Apple (99 $/an) et Google (25 $) |
| ⛔ | Textes juridiques définitifs | Un·e juriste (données sensibles, âge minimum, hébergement) |

## À faire ensuite

| | Tâche |
|---|---|
| ⬜ | Relire de vraies conversations avec l'IA sur les 14 scénarios de `docs/TESTING.md` et ajuster les consignes |
| ⬜ | Tester et corriger le mode vocal sur iPhone et Android |
| ⬜ | Vérifier le jeton Supabase sur le serveur, limites par compte, suppression de compte |
| ⬜ | Synchronisation facultative des données |
| ⬜ | Programmer les rappels (expo-notifications) |
| ⬜ | Verrouillage de l'app par code ou biométrie |
| ⬜ | Abonnement freemium, sans jamais bloquer l'aide urgente |
| ⬜ | Relecture des exercices et des consignes de crise par un·e psychologue |
| ⬜ | Empêcher l'écran de s'éteindre en mode vocal, mouvement réduit sur le cercle de respiration |
| ⬜ | Remplacer les confirmations du navigateur par une feuille intégrée (elles sont bloquées dans l'aperçu en ligne) |
| ⬜ | Fiches App Store / Google Play, captures, builds signés |
