# Sécurité et confidentialité

Les données dont parle Confie sont parmi les plus sensibles qui soient. Les choix ci-dessous sont faits pour en exposer le moins possible.

## Principes appliqués
- **Local d'abord.** Journal, humeur, exercices, conversations et mémoire sont stockés sur l'appareil. Rien n'est envoyé à un serveur de stockage tant que la synchronisation n'est pas activée.
- **Le minimum part vers l'IA.** Pour répondre, le serveur transmet à Anthropic : les messages de la conversation en cours (40 derniers), le prénom s'il est renseigné, les souvenirs **seulement si la mémoire est activée**, une page de journal **seulement si la personne la partage**.
- **Aucun secret dans l'app.** Clés Anthropic et YouTube uniquement sur le serveur.
- **Le serveur n'enregistre aucune conversation.** Les journaux d'erreur ne contiennent que le code et le message technique, jamais le contenu.
- **Entrées bornées et nettoyées** (`cleanContext`, `cleanMessages`) : tailles limitées, valeurs inconnues rejetées, retours à la ligne retirés des champs courts. Les souvenirs et le journal sont présentés à l'IA comme des informations, pas comme des instructions.
- **Limitation de débit** par adresse (12 messages par minute) et taille de requête plafonnée.
- **Fichiers** : le serveur ne sert que le dossier de l'application ; les tentatives de sortie de dossier sont testées.
- **Base de données** : RLS activée sur toutes les tables, une politique « uniquement ses propres lignes », aucun accès anonyme, compteur d'usage en écriture réservée au serveur.
- **Consentement** explicite à l'onboarding, mémoire et partage du journal désactivés par défaut, export et suppression des données depuis l'app.

## Sécurité psychologique
Consignes dans `prompt.js` (testées dans `test/prompt.test.mjs`) : l'IA se présente comme une IA, ne diagnostique pas, donne le 3114 / 15 / 112 / 3919 / 119 dans les situations de risque, n'invente pas de numéro, ne prétend pas prévenir les secours, n'encourage ni l'isolement ni la dépendance, ne simule pas d'attachement. L'écran d'aide urgente est accessible depuis l'accueil, le chat et le profil, sans jamais de paywall.

## Limites connues (à traiter avant un lancement public)
1. **Pas d'authentification sur `/api/chat`.** N'importe qui connaissant l'adresse peut l'appeler ; la seule protection est la limitation par adresse IP. À faire : vérifier le jeton Supabase et compter l'usage par compte.
2. **Limitation de débit en mémoire** : remise à zéro au redémarrage, non partagée entre plusieurs serveurs.
3. **Données locales non chiffrées par l'app** : elles reposent sur le chiffrement du téléphone. Un verrouillage par code ou biométrie est à envisager.
4. **Reconnaissance vocale** : assurée par le service du système (Apple, Google ou le navigateur), qui peut traiter l'audio sur ses serveurs. À indiquer dans la politique de confidentialité.
5. **Suppression de compte** : la fonction serveur n'est pas déployée.
6. **Aucun audit externe** ni analyse d'impact (AIPD) réalisés. Les textes juridiques sont des brouillons à faire valider.
7. `npm audit` : à relancer avant chaque publication.

## Signaler un problème
Écrire au propriétaire du projet. Ne pas ouvrir de ticket public pour une faille.
