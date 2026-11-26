# Architecture

```
┌──────────────────────────────┐        ┌───────────────────────────┐        ┌──────────────┐
│  App Confie (mobile/)        │  HTTPS │  Serveur Confie           │  HTTPS │  Anthropic   │
│  Expo 58 · React Native      │───────▶│  server.js (Node)         │───────▶│  (Claude)    │
│  iOS · Android · Web         │  flux  │  consignes + clés secrètes│        └──────────────┘
│                              │◀───────│  limites d'usage          │───────▶ YouTube Data API
│  Données sur l'appareil      │        └───────────────────────────┘
│  (AsyncStorage)              │
│                              │  (facultatif, quand configuré)
│                              │───────▶ Supabase : comptes + base PostgreSQL protégée par RLS
└──────────────────────────────┘
```

## Les trois morceaux

| Dossier | Rôle | État |
|---|---|---|
| `mobile/` | L'application (Expo Router, TypeScript). Un seul code pour iOS, Android et le web. | Fonctionnelle, testée sur le web |
| `server.js`, `prompt.js` | Passerelle vers l'IA : garde les clés, applique les consignes, limite les abus, cherche les vidéos. | Fonctionnelle, testée sans clé (réponses simulées) |
| `supabase/` | Schéma de base de données et règles de sécurité pour les comptes et la synchronisation. | Écrit, **non déployé** (aucun projet Supabase relié) |

## Dans l'application

```
mobile/src/
  app/            écrans (un fichier = une adresse)
    bienvenue, onboarding, connexion
    (tabs)/       Accueil · Journal · Exercices · Progrès · Profil
    chat/[id]     conversation écrite        voix        conversation vocale
    conversations humeur  ecrire  exercice/[id]  videos  memoire  confidentialite  aide
  features/       logique par domaine (chat, voix, journal, exercices, progrès, profil)
  store/          données de la personne (zustand, enregistrées sur l'appareil)
  content/        modes, sujets, émotions, bibliothèque d'exercices
  lib/            IA (flux), balises, voix, stockage, Supabase, configuration
  theme/ ui/      design system
```

### Le moteur de conversation (`features/chat/session.ts`)
Un seul moteur sert le chat écrit et le mode vocal : il envoie l'historique et le contexte (mode, style, franchise, sujet, mémoire si activée), reçoit la réponse au fil de l'eau, gère l'arrêt, les erreurs et la reprise, puis applique les **balises** que l'IA peut glisser en fin de message (`lib/tags.ts`) :

| Balise | Effet dans l'app |
|---|---|
| `[[video: mots-clés]]` | carte de vidéos YouTube vérifiées (ou lien de recherche sans clé YouTube) |
| `[[exercice: id]]` | carte ouvrant un exercice de la bibliothèque |
| `[[retenir: …]]` | ajoute un souvenir, seulement si la mémoire est activée ; annulable d'un geste |
| `[[oublier: id\|tout]]`, `[[memoire: off]]` | l'IA exécute « oublie ça », « supprime tout », « désactive ta mémoire » |
| `[[urgence]]` | carte des numéros d'aide |

### Mémoire
Jamais automatique : désactivée par défaut, activée par choix explicite. Elle ne contient pas les conversations, seulement une liste courte de faits utiles, visible et modifiable dans « Ce que mon IA retient ». Les conversations temporaires ne sont ni enregistrées ni mémorisées.

### Voix
`lib/voice.ts` s'appuie sur la reconnaissance et la synthèse vocales du téléphone (expo-speech-recognition, expo-speech) : gratuit, sans envoi d'audio à un tiers autre que le service vocal du système. Les phrases sont lues dès qu'elles arrivent. Limites connues et pistes premium : `docs/RECHERCHE-VOIX-COUTS.md`.

## Le serveur
- `POST /api/chat` : reçoit `{ messages, context }`, nettoie le contexte (`cleanContext`), appelle Claude en streaming et renvoie le texte brut au fil de l'eau.
- `GET /api/videos?q=` : interroge l'API officielle YouTube si `YOUTUBE_API_KEY` est définie ; sinon répond `verified: false` et l'app propose un lien de recherche. Aucune vidéo n'est jamais inventée.
- `GET /api/status` : indique si l'IA et les vidéos sont branchées.
- Sert aussi la version web de l'app (`mobile/dist`).
- Le modèle est interchangeable (`CONFIE_MODEL`).

## Ce qui n'est pas encore branché
Voir `TASKS.md` : synchronisation Supabase, vérification du jeton côté serveur, limites par compte, abonnements, publication sur les stores.
