# Confie

Un espace d'écoute par IA pour l'amour et les relations : se confier sans honte, à toute heure, et repartir avec des pistes concrètes.

## Ce que fait l'application

- **Six façons d'être aidé·e** : Écoute-moi · Aide-moi à comprendre · Sois honnête · Trouve des solutions · Rassure-moi · Challenge-moi (modifiable à tout moment dans les réglages).
- **Mémoire au choix** : activée, la conversation est gardée sur l'appareil de la personne et reprise à la visite suivante ; désactivée, rien n'est conservé. Un bouton « Tout effacer » supprime tout.
- **Vidéos YouTube** : l'IA propose des recherches YouTube ciblées (jamais de liens inventés).
- **Sécurité** : bouton « Aide urgente » (3114, 3919, 119, 112) toujours visible, et consignes strictes données à l'IA pour les situations de détresse ou de violence.
- Installable sur l'écran d'accueil du téléphone.

## Lancer l'application

Il faut [Node.js](https://nodejs.org) 20 ou plus et une clé API Anthropic (à créer sur https://console.anthropic.com).

```bash
npm install
export ANTHROPIC_API_KEY="ta-clé"
npm start
```

Puis ouvrir http://localhost:3000. Sans clé, l'interface s'affiche mais l'IA ne répond pas.

Variables facultatives : `PORT` (3000 par défaut), `CONFIE_MODEL` (`claude-opus-5-5` par défaut).

## Organisation

| Fichier | Rôle |
|---|---|
| `prompt.js` | La personnalité de Confie, ses règles et les six modes |
| `server.js` | Le serveur : sert l'interface et relaie les messages à l'IA |
| `public/` | L'interface (HTML, CSS, JavaScript) |

## À savoir

Confie est une IA : elle ne remplace ni un psychologue ni un médecin, et l'application le dit clairement. Les conversations transitent par l'API d'Anthropic pour obtenir les réponses ; le serveur de Confie ne les enregistre pas.
