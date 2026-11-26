# Journal des versions

## 0.5.0 — Choix multiples et corrections trouvées en conditions réelles
- « Comment préfères-tu qu'on te parle ? » : plusieurs choix peuvent être cochés (onboarding et profil), tous transmis à l'IA.
- Onboarding : chaque étape repart du haut (elle s'affichait défilée, titre coupé).
- Confirmations de suppression intégrées à l'app (celles du navigateur sont bloquées dans l'aperçu : les boutons ne faisaient rien).
- Liens YouTube en vrais liens (les ouvertures par script sont bloquées dans l'aperçu).
- Stockage bloqué : l'app fonctionne en mémoire au lieu de rester blanche ; polices et relecture des données ne peuvent plus bloquer l'ouverture.
- Écran d'erreur lisible avec « Réessayer » à la place d'une page vide.
- Navigation : plus d'écrans empilés en double après le mode vocal, une suppression ou la fin de l'onboarding.
- Animations d'apparition retirées (si elles ne démarraient pas, le contenu restait invisible).
- Export : copie de secours dans le presse-papiers.
- Nouveau test `npm run parcours` : 23 étapes rejouées au doigt sur écran d'iPhone, dans l'aperçu publié, cadre normal et stockage bloqué.

## 0.4.0 — Polices et accueil retravaillés
- Polices : titres en Fraunces demi-gras, texte en Figtree ; textes secondaires en vert forêt adouci au lieu de gris.
- Accueil : un seul grand bloc pour parler, humeur en cinq tuiles colorées, sujets en cases pleines avec icône, cartes « Pour toi » pleines et plus grandes.
- Puces pleines dans toute l'app (blanches, vert forêt quand elles sont choisies).
- Choix appuyés sur une étude des apps de bien-être primées (Headspace, Finch, How We Feel, Gentler Streak).

## 0.3.0 — Accueil illustré
- Accueil refait d'après les références fournies : carte verte « Comment tu te sens aujourd'hui ? » avec saisie directe, visages d'humeur, raccourcis, cartes illustrées « Pour toi ».
- Illustrations vectorielles (plante, respiration, carnet, vidéo) et visages d'humeur dessinés dans la palette.
- Même carte verte illustrée sur Journal, Exercices, Progrès et Profil ; pastilles d'icône sur chaque exercice ; plante sur l'écran de conversation vide.
- Barre d'onglets avec pastille sur l'onglet actif ; écran de bienvenue plus vert.

## 0.2.0 — Application mobile complète
- Nouvelle application Expo (iOS, Android, web) : bienvenue, onboarding, accueil, conversation, mode vocal, humeur, journal, exercices, vidéos, progrès, profil, mémoire, confidentialité, aide urgente.
- Nouvelle palette (sauge, crème, forêt) et design system, thème sombre.
- Sept modes d'aide, cinq styles, trois niveaux de franchise ; accompagnement sur tous les sujets.
- Mémoire facultative pilotable par la conversation ; conversations temporaires.
- Serveur : contexte nettoyé, recherche de vidéos via l'API YouTube, en-têtes de sécurité, CORS restreint.
- Schéma Supabase avec sécurité au niveau des lignes.
- Tests automatiques, vérification des demandes, documentation.
- Aperçu en ligne publiable (`npm run preview:build`), où l'IA répond sans clé.
- La première interface web (0.1) est retirée, remplacée par la version web de l'app.

## 0.1.0 — Première version web
- Conversation avec l'IA, modes d'aide, mémoire locale, boutons de recherche YouTube, aide urgente.
