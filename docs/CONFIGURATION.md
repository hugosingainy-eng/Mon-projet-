# Guide : obtenir vos clés et lancer le QG des Agents en vrai

Comptez environ **30 à 45 minutes** pour tout configurer.
Toutes les clés se collent dans un seul fichier : `.env`, à la racine du projet. Copiez-le depuis le modèle :

```bash
cp .env.example .env
```

> 🔒 Ne partagez jamais ce fichier et ne l'envoyez pas sur GitHub (il est déjà exclu par `.gitignore`).

| Ordre | Clé | Indispensable ? | Sert à |
|---|---|---|---|
| 1 | `ANTHROPIC_API_KEY` | Oui | Le cerveau des agents (sites, emails, Boss) |
| 2 | `GOOGLE_MAPS_API_KEY` | Oui | Trouver les commerces sur Google Maps + leurs photos |
| 3 | `SERPER_API_KEY` | Fortement conseillé | Recherche Google normale : sites cachés et emails |
| 4 | `SMTP_*` | Pour envoyer | Envoyer les emails depuis votre adresse |

---

## 1. Claude (Anthropic) : `ANTHROPIC_API_KEY`

1. Créez un compte sur la console Anthropic : <https://platform.claude.com>
2. Ajoutez un moyen de paiement et quelques crédits (10 à 20 € pour commencer) : <https://platform.claude.com/settings/billing>
3. Conseillé : fixez une **limite de dépense mensuelle** sur la même page. Vous ne serez jamais surpris.
4. Créez une clé : <https://platform.claude.com/settings/keys> → **Create Key** → nommez-la « QG des Agents ».
5. Copiez la clé (elle commence par `sk-ant-…`). Elle ne s'affiche qu'une fois.
6. Dans `.env` :
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
   ```

Tarifs : <https://claude.com/pricing#api>

---

## 2. Google Maps (Places API) : `GOOGLE_MAPS_API_KEY`

1. Ouvrez la console Google Cloud et connectez-vous avec votre compte Google : <https://console.cloud.google.com>
2. Créez un projet, par exemple « QG Agents » : <https://console.cloud.google.com/projectcreate>
3. Activez la facturation (carte bancaire obligatoire, Google offre un quota gratuit chaque mois) : <https://console.cloud.google.com/billing>
4. Activez **Places API (New)**, la nouvelle version (pas « Places API » tout court) : <https://console.cloud.google.com/apis/library/places.googleapis.com> → **Activer**.
5. Facultatif, mais utile à l'Auditeur pour noter la vitesse des sites : activez **PageSpeed Insights API** : <https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com> → **Activer**.
6. Créez la clé : <https://console.cloud.google.com/apis/credentials> → **+ Créer des identifiants** → **Clé API**.
7. **Sécurisez la clé** : cliquez sur la clé → **Restrictions relatives aux API** → **Restreindre la clé** → cochez *Places API (New)* et *PageSpeed Insights API* → **Enregistrer**.
8. Conseillé : créez une **alerte de budget**, par exemple à 20 €. Vous recevrez un email avant de dépasser : <https://console.cloud.google.com/billing/budgets>
9. Dans `.env` :
   ```
   GOOGLE_MAPS_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxx
   ```

Tarifs et quotas gratuits : <https://developers.google.com/maps/billing-and-pricing/pricing>.
L'application demande les avis, les photos et les horaires de chaque commerce. Ce sont des données de niveau « Enterprise », dont le quota gratuit mensuel est plus petit que celui des recherches simples. Surveillez votre consommation la première semaine : <https://console.cloud.google.com/apis/dashboard>

---

## 3. Recherche Google (Serper) : `SERPER_API_KEY`

C'est elle qui permet aux agents de chercher sur **Google normal** :
- si un commerce a vraiment aucun site (Vérificateur de site) ;
- quel est son email (Détective email).

1. Créez un compte : <https://serper.dev> → **Sign up**. Un compte Google suffit, sans carte bancaire.
2. Vous recevez **2 500 recherches gratuites**.
3. Votre clé s'affiche dans le tableau de bord, menu **API Key** : <https://serper.dev/api-key>
4. Dans `.env` :
   ```
   SERPER_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
5. Quand les recherches gratuites sont épuisées, achetez des crédits : environ 1 $ pour 1 000 recherches (<https://serper.dev/pricing>).

**Consommation :** jusqu'à 6 recherches par prospect (3 pour le site, 3 pour l'email). Les recherches s'arrêtent dès que le résultat est sûr, donc souvent moins. 2 500 recherches correspondent à environ 400 à 800 prospects.

> Sans `SERPER_API_KEY`, c'est Claude qui fait les recherches web. Ça marche aussi, mais chaque recherche coûte plus cher (10 $ pour 1 000 recherches, plus la lecture des pages).
> Avec les deux clés, Google passe en premier et Claude prend le relais seulement quand Google ne trouve rien de fiable.

---

## 4. Envoi des emails (SMTP) : `SMTP_*`

### Option A : votre adresse Gmail (simple, pour démarrer)

1. Activez la **validation en deux étapes** sur votre compte Google : <https://myaccount.google.com/signinoptions/twosv>
2. Créez un **mot de passe d'application** : <https://myaccount.google.com/apppasswords> → nommez-le « QG Agents » → copiez les 16 lettres.
3. Dans `.env` :
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_SECURE=false
   SMTP_USER=votre.adresse@gmail.com
   SMTP_PASS=abcdefghijklmnop
   MAIL_FROM="Votre Nom <votre.adresse@gmail.com>"
   ```

### Option B : une adresse à votre nom de domaine (recommandé pour prospecter)

Une adresse du type `contact@votre-agence.fr` inspire plus confiance et protège votre Gmail personnel.
Chez votre hébergeur email (OVH, Google Workspace, Zoho…), cherchez « paramètres SMTP ». Exemples :

| Fournisseur | `SMTP_HOST` | `SMTP_PORT` | Aide |
|---|---|---|---|
| OVHcloud (MX Plan / Email Pro) | `ssl0.ovh.net` (MX Plan) | 465 + `SMTP_SECURE=true` | <https://help.ovhcloud.com/csm/fr-email-general-settings?id=kb_article_view&sysparm_article=KB0051688> |
| Google Workspace | `smtp.gmail.com` | 587 | mot de passe d'application comme l'option A |
| Zoho Mail | `smtp.zoho.eu` | 465 + `SMTP_SECURE=true` | <https://www.zoho.com/fr/mail/help/zoho-smtp.html> |

Pour un domaine à vous, vérifiez aussi que **SPF, DKIM et DMARC** sont configurés. Sans eux, les emails finissent en spam.
Pour tester la note de délivrabilité de votre adresse : <https://www.mail-tester.com>

> Commencez petit : 20 à 30 emails par jour (réglable dans **Réglages → Règles d'envoi**), puis augmentez progressivement.

---

## 5. Votre identité et votre accès

Toujours dans `.env` :

```
ADMIN_PASSWORD=un-mot-de-passe-long-et-unique
SESSION_SECRET=une-longue-suite-de-caracteres-au-hasard
SENDER_NAME=Hugo Singainy
SENDER_COMPANY=Le nom de votre agence
SENDER_PHONE=06 xx xx xx xx
SENDER_EMAIL=contact@votre-agence.fr
SENDER_WEBSITE=https://votre-agence.fr
SENDER_OFFER=Création de site vitrine professionnel, livré en 7 jours
PUBLIC_URL=https://votre-domaine.fr
```

- `PUBLIC_URL` est l'adresse où l'application est en ligne. C'est elle qui sert dans les liens « Voir mon futur site » des emails. En local, laissez `http://localhost:3000`, mais ces liens ne marcheront pas chez vos prospects.
- Pour générer un `SESSION_SECRET` : <https://www.random.org/strings/?num=1&len=32&digits=on&upperalpha=on&loweralpha=on&unique=on&format=html&rnd=new>

---

## 6. Vérifier que tout marche

1. Démarrez l'application :
   - en local : `npm install && npm start` ;
   - sur un serveur : `docker compose up -d`.
2. Ouvrez-la et connectez-vous.
3. Allez dans **Réglages** : chaque ligne doit afficher **Actif** en vert. En bas à gauche, les 4 voyants doivent être verts.
4. Lancez une **petite mission test** : un métier, une ville, **Max = 3**.
5. Suivez le travail dans **Fil des agents**, puis ouvrez les prospects pour vérifier :
   - le site créé ;
   - l'email trouvé et sa source ;
   - l'email préparé.
6. Envoyez le premier email **à vous-même** : dans la fiche, remplacez l'adresse par la vôtre, puis cliquez sur « Envoyer ».
7. Si tout est bon, créez votre programme dans **Pilote auto**. Pour la première semaine, mettez une limite de 20 à 30 prospects par jour.

## En cas de problème

| Symptôme | Cause probable |
|---|---|
| « Google Places (403) » | Places API (New) non activée, facturation désactivée, ou clé restreinte sans *Places API (New)* |
| « Recherche Google (401/403) » | `SERPER_API_KEY` incorrecte, ou crédits Serper épuisés |
| Erreur 401 côté Claude | `ANTHROPIC_API_KEY` incorrecte |
| Erreur de crédits côté Claude | Rechargez sur <https://platform.claude.com/settings/billing> |
| « Invalid login » à l'envoi | Mot de passe d'application Gmail manquant ou mal copié (pas votre mot de passe normal) |
| Les liens des emails ne s'ouvrent pas | `PUBLIC_URL` pointe vers `localhost` : mettez l'adresse publique du serveur |

Après chaque modification de `.env`, redémarrez l'application : `npm start`, ou `docker compose up -d --force-recreate` sur un serveur.
