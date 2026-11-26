# Configuration

Aucune clé secrète ne va dans l'application mobile. Les secrets vivent uniquement sur le serveur.

## Serveur (`server.js`)

| Variable | Obligatoire | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | oui pour que l'IA réponde | Clé de l'API Anthropic (console.anthropic.com) |
| `YOUTUBE_API_KEY` | non | Clé « YouTube Data API v3 » (Google Cloud). Sans elle, l'app propose un lien de recherche YouTube |
| `CONFIE_MODEL` | non | Modèle utilisé. Défaut : `claude-opus-5-5` |
| `CONFIE_ALLOWED_ORIGINS` | non | Adresses web autorisées à appeler l'API depuis un autre domaine, séparées par des virgules |
| `PORT` | non | Port d'écoute. Défaut : 3000 |

## Application (`mobile/.env`, valeurs publiques)

| Variable | Rôle |
|---|---|
| `EXPO_PUBLIC_API_URL` | Adresse du serveur Confie, par exemple `https://api.mon-domaine.fr`. Vide = même adresse que la page (version web servie par le serveur) |
| `EXPO_PUBLIC_SUPABASE_URL` | Adresse du projet Supabase (active les comptes) |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Clé publique Supabase. Sans risque : l'accès aux données est verrouillé par les règles RLS |

## Lancer en local

```bash
npm install && (cd mobile && npm install)
npm run build          # construit la version web de l'app
ANTHROPIC_API_KEY=... npm start     # http://localhost:3000
```

Sur téléphone pendant le développement : `cd mobile && npx expo start`. La voix sur iOS/Android demande un « development build » (`eas build --profile development`), pas Expo Go.

## Base de données
`supabase/migrations/0001_init.sql` se déploie avec `supabase db push` une fois un projet Supabase créé et relié.
