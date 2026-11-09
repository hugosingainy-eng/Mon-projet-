# Quantum Edge AI — trading quantitatif multi-agents (DÉMO uniquement)

Système de trading autonome : **10 agents spécialisés + 1 Master Agent**, un moteur de
**compétition de stratégies** (walk-forward, hors échantillon, Monte-Carlo), un
**risk manager à veto absolu** et un **tableau de bord web**.

- **100 % gratuit** : données Yahoo Finance, actualités RSS, SQLite, FastAPI. Aucun abonnement.
- **Budget virtuel du bot : 100 $**, suivi séparément du solde démo eToro.
- **Argent réel techniquement impossible** : couche de sécurité immuable (`quantum_edge/safety.py`).
- **Achat uniquement, sans levier.** Risque max **0,50 $/trade**, **1 $/jour**, **2,50 $/semaine**, **5 $ de drawdown**.

> ⚠️ Aucun rendement n'est garanti. Le bot refuse la plupart des opportunités : c'est voulu.
> Observe-le **8 à 12 semaines en démo** avant de tirer la moindre conclusion.
> Le rapport de livraison détaillé est dans [`docs/RAPPORT.md`](docs/RAPPORT.md).

---

## 1. Installation sous Windows

1. Installe **Python 3.11 ou plus** depuis https://www.python.org/downloads/
   (coche **« Add python.exe to PATH »** pendant l'installation).
2. Télécharge ce projet (bouton vert **Code → Download ZIP** sur GitHub), puis décompresse-le.
3. Ouvre le dossier, clic droit sur `scripts\install_windows.ps1` → **Exécuter avec PowerShell**.
   Si Windows bloque le script, ouvre PowerShell dans le dossier et tape :
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
   ```
   Le script crée un environnement Python, installe tout, crée le fichier `.env` et lance les tests.

## 2. Lancement (dans l'ordre)

| Étape | Double-clic | Commande équivalente | Ce que ça fait |
|---|---|---|---|
| 1 | `scripts\run_research.bat` | `python -m quantum_edge research` puis `backtest` | Télécharge 10 ans de données, fait concourir 6 familles de stratégies (48 configurations), ne garde que celles qui passent **tous** les tests |
| 2 | `scripts\start_dashboard.bat` | `python -m quantum_edge dashboard` | Tableau de bord sur **http://127.0.0.1:8000** |
| 3 | `scripts\start_bot.bat` | `python -m quantum_edge run` | Le bot tourne seul du lundi au vendredi (surveillance toutes les 5 min, scan 25 min avant la clôture de New York) |
| ⛔ | `scripts\emergency_stop.bat` | `python -m quantum_edge emergency-stop` | Arrêt d'urgence + fermeture des positions du bot |

Autres commandes :
```bash
python -m quantum_edge scan --now      # un scan immédiat pour voir les décisions des agents
python -m quantum_edge status          # état du compte, positions, ordres en attente
python -m quantum_edge resume          # reprise après coupe-circuit (phrase de confirmation exigée)
python -m quantum_edge etoro-check     # vérifie la connexion eToro (lecture seule, aucun ordre)
python -m quantum_edge audit           # audit final automatique (Partie 14)
python -m quantum_edge report          # rapports quotidien + hebdomadaire
python -m pytest -q                    # 70 tests unitaires, d'intégration et de sécurité
```

Le PC doit rester allumé pendant que le bot tourne. Si tu préfères Docker :
`docker compose -f docker/docker-compose.yml up -d --build`.

## 3. Modes de fonctionnement

| Mode | `.env` | Coût | Clés |
|---|---|---|---|
| **Simulé** (par défaut) | `EXECUTION_BACKEND=simulated` | gratuit | aucune |
| **Démo eToro** | `EXECUTION_BACKEND=etoro_demo` | gratuit | `ETORO_API_KEY` + `ETORO_USER_KEY` |

Commence en mode simulé avec les vraies données Yahoo. Passe au mode démo eToro quand
`etoro-check` est entièrement vert.

### Obtenir les clés eToro (démo)
1. Connecte-toi à eToro et passe sur le **portefeuille virtuel**.
2. **Paramètres → Trading → API Key Management → Create key**.
3. Choisis l'environnement **Virtual (démo)**, avec les droits lecture + trading.
4. Copie les deux clés dans `.env`, puis lance `python -m quantum_edge etoro-check`.

Les routes de l'API eToro n'ont pas pu être vérifiées depuis l'environnement de
développement. `etoro-check` dit précisément laquelle corriger si besoin, dans
`quantum_edge/execution/etoro_client.py` (dictionnaire `ENDPOINTS`).

## 4. Architecture

```
quantum_edge/
  safety.py            couche de sécurité immuable (DEMO, levier x1, pas de short, routes /demo/ seules)
  config.py            limites de risque, univers, coûts
  engine.py            cycle autonome, reprise après crash, coupe-circuit
  agents/              master.py + 10 agents (régime, technique, quant, macro, sentiment,
                       testeur, Monte-Carlo, risk manager, exécution, auditeur) + grok.py (optionnel)
  strategies/          6 familles en compétition (tendance, momentum, retour à la moyenne,
                       cassure de volatilité, multi-unités de temps, force relative)
  quantitative/        moteur de trades, métriques, walk-forward, compétition, bibliothèque versionnée
  simulations/         Monte-Carlo par trade (50 000 trajectoires) et par séquence (20 000 x 7 scénarios)
  risk/                comptabilité 100 $, risk manager, portefeuille (corrélation, VaR), coupe-circuit
  execution/           client eToro démo, brokers, ordres idempotents, rapprochement, horaires NYSE
  marketdata/          Yahoo / eToro / CSV / synthétique, qualité des données, RSS, calendrier
  database/            SQLite (WAL) + sauvegardes
  api/server.py        FastAPI + WebSocket
frontend/dashboard/    tableau de bord (HTML/JS sans dépendance)
config/macro_events.csv  calendrier macro vérifiable
scripts/               installation Windows, lanceurs, mise à jour du calendrier FOMC
tests/                 70 tests
```
