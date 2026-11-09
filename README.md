# Bot de copy trading eToro (démo d'abord)

Ce bot copie automatiquement, via l'API officielle d'eToro, des traders
eToro sélectionnés avec prudence. Il tourne 24h/24, sur votre PC ou sur un
serveur.

> ## ⚠️ À lire avant tout
> - **Aucun bot ne garantit des gains.** Vous pouvez perdre de l'argent.
> - Les simulations et le backtest **rejouent le passé**. Ils ne prédisent pas l'avenir.
> - Commencez en **démo** (argent fictif) pendant **4 à 8 semaines** avant de penser à l'argent réel.
> - Le bot ne passe **jamais** d'ordre sur des actions. Il démarre, ajuste ou arrête des **copies de traders**, rien d'autre.

---

## Ce que fait le bot, en bref

Une équipe d'« agents » travaille ensemble :

| Agent | Quand | Rôle |
|---|---|---|
| Recruteur | chaque semaine | Lit 300 traders du classement et ne garde que les prudents (risque ≤ 4, chute ≤ 20 %, 60 % de mois gagnants…). |
| Inspecteur | chaque semaine | Regarde leur portefeuille en direct : pas trop concentré, peu de levier, peu de ventes à découvert. |
| Diversification | chaque semaine | Refuse deux traders qui possèdent plus de 40 % de choses en commun. |
| Marché | chaque jour + toutes les 5 min | Calcule le climat (calme, tendu, stress) avec le S&P 500 et le Nasdaq 100. |
| Analyste IA (optionnel) | à chaque sélection | Claude ou Grok lit tous les rapports. **Il peut seulement rendre le bot plus prudent.** |
| Sentinelle | toutes les 5 min + chaque jour | Coupe une copie qui perd 8 % ou dont le trader change de comportement. Le trader est banni 8 semaines. |
| Renseignement | chaque semaine / chaque jour | Grands investisseurs (13F), achats du Congrès américain, actualités, et veille X avec Grok. |
| Simulateur | avant chaque investissement | Examine **toutes les équipes possibles** à chaque mise (100 %, 75 %, 50 %), avec **au moins 10 000 futurs simulés pour chaque option** (Monte Carlo). Il donne le feu vert seulement si les chances sont bonnes, et choisit l'option la plus sûre. |
| Directeur | toujours | Orchestre tout et applique les règles de sécurité. |

### Les règles de sécurité (codées en dur)

- **Budget :** le bot n'engage jamais plus que `budget` (600 $ en démo, soit 3 traders × 200 $). Si une part tombe sous 200 $ (le minimum eToro), il copie moins de traders ou reste en cash.
- **Arrêt à −5 % :** si la perte totale (réalisée et latente) atteint 5 % du budget (30 $ sur 600 $), le bot ferme **ses** copies et s'arrête jusqu'à `--reset`.
- **Vos copies personnelles :** le bot n'y touche **jamais**, même pour un arrêt d'urgence.
- **Copie fermée à la main :** si vous fermez une copie du bot dans l'appli eToro, sa perte reste comptée.
- **Argent réel :** il faut **deux** verrous, `mode: real` dans `config.yaml` **et** `I_ACCEPT_REAL_MONEY_RISK=oui` dans `.env`.

---

## 1. Installation pas à pas

### a) Installer Python

- **Windows :** téléchargez Python 3.12 sur <https://www.python.org/downloads/>. Pendant l'installation, **cochez « Add Python to PATH »**.
- **Mac :** installez Python 3.12 depuis python.org, ou avec `brew install python`.
- **Linux :** `sudo apt install python3 python3-venv poppler-utils`

> `poppler-utils` (ou `brew install poppler` sur Mac) sert à lire les déclarations du Congrès. Sans lui, le bot continue simplement sans cette information.

### b) Récupérer le bot

Téléchargez ce dépôt (bouton vert « Code », puis « Download ZIP ») et décompressez-le. Ou bien, avec git :

```bash
git clone https://github.com/hugosingainy-eng/Mon-projet-.git
cd Mon-projet-
```

### c) Créer votre clé API eToro **Démo** (avec la permission Write)

1. Connectez-vous à eToro et passez en **portefeuille virtuel (Demo)**.
2. Allez dans **Paramètres, puis Trading, puis API Key Management** (ou sur <https://api-portal.etoro.com>).
3. Créez une clé :
   - **Environnement : Demo.** Une clé démo ne marche pas en réel, et inversement.
   - **Permissions : Read + Write.** Write est nécessaire pour démarrer et arrêter des copies.
4. Notez les **deux** valeurs : la clé publique (*API key*) et la clé utilisateur (*User key*).

> Les noms exacts des menus peuvent changer. Suivez la documentation officielle : <https://api-portal.etoro.com>.

### d) Remplir le fichier `.env`

Copiez `.env.example` et nommez la copie `.env`, puis ouvrez-la avec un éditeur de texte :

```
ETORO_API_KEY=votre-clé-api
ETORO_USER_KEY=votre-clé-utilisateur
SEC_USER_AGENT="Prénom Nom vous@exemple.com"
I_ACCEPT_REAL_MONEY_RISK=non
```

En option, ajoutez une clé IA (`ANTHROPIC_API_KEY` pour Claude ou `XAI_API_KEY` pour Grok) et Telegram (voir plus bas).

**Ne partagez jamais votre fichier `.env`.** Il est exclu de git.

### e) Lancer le bot

- **Windows :** double-cliquez sur `lancer_windows.bat`.
- **Mac / Linux :** dans un terminal, tapez `./lancer_mac_linux.sh`.

La première fois, le script installe tout ce qu'il faut. Ensuite, il **relance le bot automatiquement** s'il plante.

**Conseil :** commencez par une simulation, qui ne passe aucun ordre :

```bash
./lancer_mac_linux.sh --dry-run          # Mac / Linux
lancer_windows.bat --dry-run             # Windows
```

---

## 2. Les commandes

Toutes s'écrivent `python -m bot.main ...` (ou `.venv/bin/python -m bot.main ...` après l'installation par le script).

| Commande | Effet |
|---|---|
| `python -m bot.main` | Lance la boucle 24h/24. |
| `--dry-run` | Simule sans passer d'ordre. L'état est gardé dans un fichier séparé (`data/etat_dry_run.json`). |
| `--once` | Fait un seul cycle complet, puis s'arrête. |
| `--status` | Affiche l'état : copies, gains et pertes, climat, arrêt. |
| `--stop` | Ferme **les copies du bot** (jamais les vôtres) et arrête le bot. |
| `--reset` | Réarme le bot après un arrêt. La limite de −5 % repart de zéro. |
| `--backtest` | Rejeu historique et Monte Carlo, **sans aucun ordre**. Le rapport va dans `data/backtest.md`. |
| `--chat` | Discuter avec le bot dans le terminal. |
| `--test-api` | Vérifie vos clés eToro (lecture seule, aucun ordre). À lancer en premier. |

**Rythme de la boucle :**
- toutes les 5 minutes : sécurité, Sentinelle et contrôle rapide du marché ;
- chaque jour : analyse du marché et du comportement des traders, veille actualités ;
- chaque semaine, ou dès que le climat change : nouvelle sélection.

**Premier essai recommandé :**

```bash
python -m bot.main --dry-run --once     # un cycle simulé, regardez data/rapport.md
python -m bot.main --backtest           # regardez data/backtest.md
```

### Les fichiers produits (dans `data/`)

- `bot.log` : le journal, en français. Il tourne automatiquement (5 fichiers de 5 Mo au plus).
- `etat.json` : la mémoire du bot. **Ne le modifiez pas à la main.**
- `rapport.md` : le rapport après chaque sélection. Il contient le climat, le simulateur, l'avis de l'IA, les traders copiés, les grands investisseurs, le Congrès, les alertes et la raison de chaque rejet.
- `backtest.md` : le résultat de `--backtest`.

---

## 3. Discuter avec le bot

### Dans le terminal

```bash
python -m bot.main --chat
```

Exemples : « comment vont mes copies ? », « climat », « pourquoi trader123 ? », « pause », « arrête tout ».

### Sur Telegram (depuis votre téléphone)

1. Sur Telegram, parlez à **@BotFather**, tapez `/newbot` et récupérez le **token**.
2. Envoyez un message à votre nouveau bot, puis ouvrez `https://api.telegram.org/bot<TOKEN>/getUpdates` dans un navigateur pour lire votre **chat id**.
3. Dans `.env`, ajoutez `TELEGRAM_BOT_TOKEN=...` et `TELEGRAM_CHAT_ID=...`.
4. Relancez le bot. Il ne répond **qu'à vous**.

**Ce que le chat peut faire :** lire et expliquer, et agir uniquement dans le sens prudent (stop avec confirmation, pause, bannir un trader).

**Ce qu'il ne peut jamais faire :** augmenter le budget, passer en argent réel, lever l'arrêt à −5 % ou toucher à vos copies personnelles.

### L'IA : Claude ou Grok

Dans `config.yaml`, choisissez `ia.fournisseur: claude` (clé `ANTHROPIC_API_KEY`) ou `grok` (clé `XAI_API_KEY`).

- Grok permet en plus la **veille sur X (Twitter)**.
- Sans clé, le bot fonctionne normalement, sans IA.
- L'IA peut seulement réduire l'exposition ou opposer un veto. Si elle répond n'importe quoi ou plante, son avis est ignoré (avis neutre).

---

## 4. Héberger sur un serveur (Docker)

Sur un serveur Linux avec Docker installé :

```bash
cp .env.example .env        # puis remplissez vos clés
mkdir -p data
docker compose up -d --build            # démarre ; relance automatique (restart: always)
docker compose logs -f                  # voir le journal
docker compose run --rm bot --status    # statut
docker compose run --rm bot --stop      # fermer les copies du bot
```

Pour simuler sur le serveur, mettez `command: ["--dry-run"]` dans `docker-compose.yml`.

L'image Docker contient `poppler-utils`, nécessaire pour lire les déclarations du Congrès.

---

## 5. Passer à l'argent réel (plus tard, et seulement si vous le décidez)

**Ne le faites qu'après plusieurs semaines de démo** (4 à 8 semaines), et seulement si les résultats et le comportement du bot vous conviennent.

1. Créez une **nouvelle clé API eToro pour l'environnement Real**. La clé démo ne marche pas en réel.
2. Dans `.env`, remplacez les deux clés, puis écrivez `I_ACCEPT_REAL_MONEY_RISK=oui`.
3. Dans `config.yaml`, écrivez `mode: real` et choisissez un `budget` que vous pouvez **perdre sans problème**.
4. Faites d'abord `--dry-run --once` en réel pour vérifier.

Sans les **deux** verrous, le bot refuse de démarrer en réel.

---

## 6. Limites à connaître

- **Le simulateur Monte Carlo** remélange les rendements passés des traders. Une crise d'un genre nouveau n'y figure pas.
- **Le backtest** souffre du **biais du survivant** : les traders qui ont disparu (comptes fermés après de grosses pertes) ne sont pas dans les données, donc le passé paraît plus beau qu'il ne l'était.
- Le backtest avance mois par mois. Il ne voit ni les chutes en cours de mois, ni les frais, ni le climat de marché passé.
- **Les unités de l'API** (gains en % ou en décimal, sens de `peakToValley`) ne sont pas toujours claires dans la documentation. Elles se règlent dans la section `unites` de `config.yaml`. Le bot écrit un avertissement dans le log si une unité semble fausse.
- **Les actualités, le Congrès et les 13F** sont des pistes, pas des certitudes. Les 13F ont plusieurs semaines de retard.
- **Le copy trading** comporte des risques : un trader peut changer de stratégie du jour au lendemain. La Sentinelle limite ce risque mais ne l'élimine pas.

---

## Pour les curieux : structure du code

```
bot/
  main.py            commandes et boucle 24h/24
  config.py          config.yaml + .env (double verrou argent réel)
  etoro_client.py    API eToro (en-têtes, limites, 429, Retry-After)
  securite.py        règles dures (budget, -5 %, copies personnelles)
  etat.py            mémoire du bot (écriture atomique)
  ia.py              Claude (SDK anthropic) ou Grok (API xAI)
  chat.py            terminal + Telegram
  backtest.py        rejeu mensuel + Monte Carlo
  agents/            recruteur, inspecteur, diversification, marche, analyste_ia,
                     sentinelle, renseignement, veille_x, simulateur, directeur
vendor/trader-skill  pack open source (licence MIT) utilisé par le Renseignement
tests/               tests avec une fausse API eToro, sans réseau
```

Lancer les tests : `python -m pytest -q`

Crédits : le Renseignement utilise [trader-skill](https://github.com/Jakeschincariol/trader-skill) de Jake Schincariol (licence MIT, voir `vendor/trader-skill/LICENSE`).
