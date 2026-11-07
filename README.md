# QG des Agents : agence web pilotée par IA

Application privée (un seul utilisateur, protégée par mot de passe) où **5 agents IA** travaillent pour vous.
Un **Boss** supervise 4 sous-agents. Rien ne part chez un prospect sans sa validation.

```
                               👔 BOSS
                 assistants : 📏 Contrôleur qualité · 🧐 Relecteur critique
     ┌────────────────┬───────────────────┬────────────────────┬──────────────────┐
 🧭 Prospecteur    🔎 Auditeur         🎨 Créateur de site   ✉️ Rédacteur
  🔭 Éclaireur      🛠️ Technicien       📷 Photographe        🧩 Analyste prospect
  🎯 Qualificateur  📈 Analyste SEO     🖋️ Rédacteur web      ✍️ Plume
  🌐 Vérificateur   🕵️ Enquêteur contact 💻 Intégrateur        🔤 Correcteur
     de site                                                  🪪 Designer carte
  📧 Détective email
```

**Trois niveaux de contrôle :**
1. Chaque **sous-agent** fait une tâche précise.
2. Son **chef d'équipe** vérifie le résultat et le lui renvoie à corriger si besoin (✏️ « correction »), avant de livrer au Boss. Par exemple, l'Intégrateur reprend son site tant qu'il ne passe pas les contrôles du Boss, et la Plume réécrit l'email tant que le Correcteur y trouve des défauts.
3. Le **Boss**, aidé de ses deux assistants, valide ou renvoie le livrable au chef (↩️ « rejet »).

| Sous-agent | Rôle |
|---|---|
| 🔭 Éclaireur | Élargit la recherche Google Maps avec des variantes du métier (ex. « boulangerie » → « artisan boulanger »). |
| 🎯 Qualificateur | Note chaque prospect de 0 à 100 : pas de site, bonne note, beaucoup d'avis. Les meilleurs sont traités en premier. |
| 🌐 Vérificateur de site | Quand Google Maps n'indique pas de site, il cherche sur Google (nom + ville, téléphone…). Il ne retient une page que si elle mentionne le même téléphone, la même adresse ou le même nom. Les annuaires et réseaux sociaux ne comptent pas comme un site, mais les pages Facebook/Instagram trouvées sont notées. S'il trouve un site, le prospect part à l'Auditeur. |
| 📧 Détective email | Cherche l'email sur tout le web : extraits Google, site officiel, pages contact et mentions légales, annuaires, Facebook. Il comprend les adresses masquées (« contact [at] … »), écarte les emails des plateformes et les no-reply, et donne à chaque email un score de confiance. |
| 🛠️ Technicien | Vérifie que le site est accessible, en HTTPS, adapté au mobile et rapide, et repère les technologies obsolètes. |
| 📈 Analyste SEO | Contrôle les balises title/description, l'Open Graph, les textes alternatifs des images et les scores PageSpeed. |
| 🕵️ Enquêteur contact | Cherche l'email sur l'accueil, puis sur les pages contact et mentions légales. |
| 📷 Photographe | Télécharge les photos Google Maps et choisit la meilleure photo d'accueil. |
| 🖋️ Rédacteur web | Écrit les textes du site à partir des vrais avis, sans prix ni chiffres inventés. |
| 💻 Intégrateur | Assemble le site (design, mobile, SEO). |
| 🧩 Analyste prospect | Choisit le meilleur avis client et les faits qui rendent l'email personnel. |
| ✍️ Plume | Écrit l'objet et le message. |
| 🔤 Correcteur | Vérifie la longueur, le lien, le vouvoiement, la personnalisation et l'absence de mots « spam ». |
| 🪪 Designer carte | Met en forme la carte numérique aux couleurs du métier : bleu pour un plombier, brun pour une boulangerie, etc. |

Sur le tableau de bord, l'organigramme montre en direct quel sous-agent travaille. Le **Fil des agents** affiche toutes les consignes et corrections ; une case à cocher permet de ne garder que les échanges avec le Boss.

## Le circuit

1. **Vous lancez une mission** : « plombier » + « Lyon 3e ».
2. **Prospecteur** : interroge Google Maps (Places API) et rapporte les établissements.
3. **Boss** : écarte les établissements fermés, les franchises, ceux qui sont injoignables ou ont moins de 3 avis.
4. **Vérificateur de site** : si Google Maps n'indique aucun site, une recherche Google approfondie confirme qu'il n'y en a vraiment pas. Le **Boss** valide ; si un site caché est trouvé, il part à l'Auditeur.
5. **Auditeur** (seulement si l'établissement a un site) : il mesure HTTPS, l'adaptation au mobile, la vitesse, le SEO, le copyright daté, la technologie obsolète, PageSpeed, etc., et relève les emails présents sur le site.
   **Boss** : vérifie que le verdict est cohérent. Un bon site est écarté, un mauvais site devient une opportunité.
6. **Détective email** : si l'email n'est pas sur le site de l'entreprise, il le cherche sur tout le web. Le **Boss** vérifie l'email : son format, que le domaine reçoit bien des emails (serveur MX), qu'il ne s'agit pas de l'email d'un annuaire, et le score de confiance. S'il le refuse, le Détective cherche une autre adresse. La source est enregistrée dans la fiche (traçabilité RGPD).
7. **Créateur de site** : télécharge les photos Google Maps et génère un site one-page (avis réels, horaires, appel téléphonique, itinéraire).
   **Boss** : contrôles stricts (mobile, nom, téléphone, photos, pas de texte bidon, pas d'info inventée), puis relecture critique par l'IA. **S'il refuse, le Créateur reçoit la liste des corrections et recommence.**
8. **Rédacteur** : écrit l'email personnalisé et la **carte numérique**, compatible Gmail et Outlook, qui contient l'aperçu du site, le bouton « Voir mon futur site » et votre signature.
   **Boss** : vérifie la longueur, la personnalisation, la présence du lien, le vouvoiement et l'absence de mots « spam ». Il renvoie l'email s'il n'est pas au niveau.
9. **Le dossier est prêt** : vous cliquez sur « Envoyer », ou vous activez l'envoi automatique.

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
| `SERPER_API_KEY` | Recherche Google « normale » pour les sites cachés et les emails (sinon c'est Claude qui cherche sur le web) | serper.dev (2 500 recherches offertes) |
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
- Google Maps ne fournit pas les emails. L'Enquêteur contact les cherche d'abord sur le site de l'entreprise, puis le Détective email cherche sur tout le web. Seuls les emails **publiés** par l'entreprise sont retenus, jamais une adresse devinée, et chaque fiche garde la page source. Si rien n'est trouvé, le dossier passe en « Email à renseigner ». Le bouton « Rechercher l'email sur le web » relance la recherche.

## Structure

```
server/
  index.js            serveur, connexion privée, API
  orchestrator.js     circuit des agents + boucle « livrer → Boss → corriger »
  team.js             organigramme, activité en direct, délégation chef → sous-agent
  agents/
    supervisor.js     👔 le Boss
    prospector.js     🧭 Prospecteur
    auditor.js        🔎 Auditeur
    webbuilder.js     🎨 Créateur de site
    copywriter.js     ✉️ Rédacteur (email + carte numérique)
  services/           Google Places, audit de site, recherche web (sites cachés + emails), SMTP
  llm.js              accès à Claude (sorties JSON structurées)
public/               tableau de bord
test/                 tests du Boss et des sous-agents (npm test)
```
