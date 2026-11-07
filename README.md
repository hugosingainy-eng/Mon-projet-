# QG des Agents : agence web pilotée par IA

Application privée (un seul utilisateur, protégée par mot de passe) où **5 agents IA** travaillent pour vous.
Un **Boss** supervise 4 sous-agents. Rien ne part chez un prospect sans sa validation.

```
                         👔 BOSS (superviseur)
        vérifie chaque livrable, valide ou renvoie avec un retour précis
     ┌───────────────┬──────────────────┬───────────────────┬──────────────┐
 🧭 Prospecteur   🔎 Auditeur       🎨 Créateur de site   ✉️ Rédacteur
 Google Maps :    Analyse les       Crée un site vitrine   Email personnalisé
 qui n'a pas      sites existants,  avec les photos, avis  + carte numérique
 de site ?        repère les        et horaires Google     (aperçu du site +
                  mauvais           Maps                   vos coordonnées)
```

## Le circuit

1. **Vous lancez une mission** : « plombier » + « Lyon 3e ».
2. **Prospecteur** : interroge Google Maps (Places API) et rapporte les établissements.
3. **Boss** : écarte les établissements fermés, les franchises, ceux qui sont injoignables ou ont moins de 3 avis.
4. **Auditeur** (seulement si l'établissement a un site) : il mesure HTTPS, l'adaptation au mobile, la vitesse, le SEO, le copyright daté, la technologie obsolète, PageSpeed, etc., et relève les emails présents sur le site.
   **Boss** : vérifie que le verdict est cohérent. Un bon site est écarté, un mauvais site devient une opportunité.
5. **Créateur de site** : télécharge les photos Google Maps et génère un site one-page (avis réels, horaires, appel téléphonique, itinéraire).
   **Boss** : contrôles stricts (mobile, nom, téléphone, photos, pas de texte bidon, pas d'info inventée), puis relecture critique par l'IA. **S'il refuse, le Créateur reçoit la liste des corrections et recommence.**
6. **Rédacteur** : écrit l'email personnalisé et la **carte numérique**, compatible Gmail et Outlook, qui contient l'aperçu du site, le bouton « Voir mon futur site » et votre signature.
   **Boss** : vérifie la longueur, la personnalisation, la présence du lien, le vouvoiement et l'absence de mots « spam ». Il renvoie l'email s'il n'est pas au niveau.
7. **Le dossier est prêt** : vous cliquez sur « Envoyer », ou vous activez l'envoi automatique.

Après `MAX_REVISIONS` refus (3 par défaut), le dossier est marqué **« Bloqué par le Boss »** et vous décidez.
Tout l'historique des échanges entre le Boss et ses agents se trouve dans **Fil des agents** et dans l'onglet **Échanges Boss** de chaque prospect.

## Démarrer

```bash
cp .env.example .env     # puis remplissez au minimum ADMIN_PASSWORD
npm install
npm start                # http://localhost:3000
```

Sans clé API, l'application tourne en **mode démo** : prospects fictifs, sites créés à partir d'un gabarit et contrôles automatiques du Boss.
Cela permet de tout tester avant d'ajouter vos clés.

| Variable | À quoi ça sert | Où l'obtenir |
|---|---|---|
| `ADMIN_PASSWORD` | Votre accès privé | à choisir |
| `ANTHROPIC_API_KEY` | Le cerveau des agents (Claude) | console.anthropic.com |
| `GOOGLE_MAPS_API_KEY` | Recherche Google Maps et photos (activez **Places API (New)**, et **PageSpeed Insights API** en option) | console.cloud.google.com |
| `SMTP_*` | Envoi des emails | votre fournisseur email (Gmail : mot de passe d'application) |
| `PUBLIC_URL` | Adresse publique des sites d'aperçu (liens dans les emails) | votre domaine |
| `SENDER_*` | Votre signature et votre offre | à remplir |

Le modèle par défaut est `claude-opus-5-5`. Le repli automatique côté serveur (`fallbacks: "default"`) est activé : si une requête est refusée, elle est relancée sur un autre modèle.

## Mettre en ligne

Les liens des emails doivent pointer vers une adresse publique. Le plus simple est un petit serveur (VPS, Railway, Render, Fly.io) avec le `Dockerfile` fourni :

```bash
docker build -t qg-agents .
docker run -d -p 3000:3000 --env-file .env -v qg-data:/app/data qg-agents
```

Seuls les sites d'aperçu (`/sites/...`) sont publics, et ils sont marqués `noindex`. Le tableau de bord et l'API exigent votre mot de passe.

## Bon à savoir (légal)

- **Prospection B2B par email (France)** : elle est autorisée vers une adresse professionnelle si le message concerne l'activité du destinataire. Il faut toujours permettre de refuser. Chaque email contient une mention de désinscription et l'en-tête `List-Unsubscribe`.
- **Photos Google Maps** : elles appartiennent à leurs auteurs. Le site d'aperçu affiche leur crédit. Pour un site définitif mis en ligne pour le client, utilisez **ses propres photos**.
- Google Maps ne fournit pas les emails. L'Auditeur les récupère sur le site quand il y en a un. Sinon le dossier passe en « Email à renseigner » et vous ajoutez l'adresse dans la fiche.

## Structure

```
server/
  index.js            serveur, connexion privée, API
  orchestrator.js     circuit des agents + boucle « livrer → Boss → corriger »
  agents/
    supervisor.js     👔 le Boss
    prospector.js     🧭 Prospecteur
    auditor.js        🔎 Auditeur
    webbuilder.js     🎨 Créateur de site
    copywriter.js     ✉️ Rédacteur (email + carte numérique)
  services/           Google Places, audit de site, SMTP
  llm.js              accès à Claude (sorties JSON structurées)
public/               tableau de bord
test/                 tests des contrôles du Boss (npm test)
```
