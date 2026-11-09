# Rapport de livraison — Quantum Edge AI

*Date : 9 novembre 2026. Ce rapport distingue ce qui est implémenté, testé, partiel,
en attente de clés, ou bloqué. Aucun résultat n'est inventé.*

## 0. Contrainte majeure de l'environnement de développement

Le code a été écrit et testé dans un conteneur cloud dont l'accès réseau sortant est
**bloqué** vers : `builders.etoro.com`, `api-portal.etoro.com`, `public-api.etoro.com`,
Yahoo Finance, Google News, federalreserve.gov, api.telegram.org et api.x.ai.

Conséquences :
- la **documentation officielle eToro n'a pas pu être lue directement** (seulement via des
  résumés de moteur de recherche) ;
- **aucune donnée de marché réelle** n'a pu être téléchargée : tous les résultats
  chiffrés ci-dessous viennent d'un **marché SYNTHÉTIQUE** et ne disent **rien** de la
  rentabilité réelle ;
- l'intégration eToro est testée avec des **réponses simulées**, jamais contre le vrai serveur.

Sur ton PC Windows, rien de tout cela n'est bloqué : lance `research`, puis `etoro-check`.

## 1. Statut des composants

| Composant | Statut |
|---|---|
| Couche de sécurité DÉMO (immuable, testée) | ✅ Implémenté et testé |
| 10 agents + Master Agent, 12 contrôles avant trade | ✅ Implémenté et testé |
| 6 familles de stratégies, 48 configurations | ✅ Implémenté et testé |
| Compétition : train / validation / test, walk-forward, coûts x2, retard d'1 barre, stabilité des paramètres, biais du futur, régimes, classement | ✅ Implémenté et testé (données synthétiques) |
| Monte-Carlo trade (50 000 trajectoires) et séquences (20 000 x 7 scénarios) | ✅ Implémenté et testé |
| Risk manager (veto absolu), risque de portefeuille, coupe-circuit avec autorisation humaine | ✅ Implémenté et testé |
| Comptabilité séparée du budget de 100 $ | ✅ Implémenté et testé |
| Ordres idempotents, blocage si statut incertain, rapprochement, reprise après crash | ✅ Implémenté et testé (courtier simulé + faux client eToro) |
| SQLite, sauvegardes, journaux JSON, alertes Telegram (optionnel) | ✅ Implémenté ; Telegram non testé en réel (réseau bloqué) |
| Tableau de bord (7 sections, WebSocket, arrêt d'urgence, reprise) | ✅ Implémenté et testé (navigateur headless, mobile 390 px) |
| Rapports quotidien / hebdomadaire / recherche, auditeur | ✅ Implémenté et testé |
| Données Yahoo, RSS, résultats d'entreprises via yfinance | 🟡 Implémenté, **non testé en réel** (réseau bloqué) |
| Client API eToro démo (recherche, bougies, prix, ordres, portefeuille) | 🟡 Implémenté, **routes non vérifiées** contre la doc officielle |
| Authentification et ordres démo eToro | ⏳ **En attente de tes clés API** |
| Statistiques d'investisseurs eToro (Popular Investors) | 🔴 Non branché : routes non vérifiables. La fonction de notation `evaluate_investor` existe et est testée |
| Calendrier CPI / emploi | 🟡 Fichier manuel `config/macro_events.csv` ; script automatique seulement pour le FOMC |
| Frontend React/Next.js | ↪️ Remplacé par HTML/JS servi par FastAPI : rien à compiler sous Windows, et aucun Node.js nécessaire |
| PostgreSQL | ↪️ Remplacé par SQLite : gratuit, aucun serveur à installer |

## 2. Rapport sur les agents

| Agent | Fichier | Données utilisées | Pouvoir |
|---|---|---|---|
| Master (directeur) | `agents/master.py` | rapports des 10 agents | décide BUY / HOLD / NO TRADE ; ne peut pas passer outre un veto |
| 1. Régime | `agents/regime.py` | SMA 50/200 du SPY et de l'actif, percentile d'ATR, volume en $, ADX | s'oppose si le régime n'est pas validé pour la stratégie, ou si la liquidité est faible |
| 2. Technique | `agents/technical.py` | RSI, MACD, EMA 9/21/50/200, SMA, VWAP, ATR, Bollinger, ADX, supports et résistances, chandeliers, volume, en 5m / 15m / 1h / 4h / 1j | exige 3 preuves sur 5, aucune tendance baissière en 1h ou 4h, et des données intraday disponibles |
| 3. Quant | `agents/quant.py` | métriques walk-forward, historique conditionnel du setup | exige un intervalle de confiance > 0 et au moins 20 occurrences |
| 4. Macro | `agents/macro.py` | calendrier vérifiable, RSS de la Fed, dates de résultats | **veto** : événement majeur sous 48 h, résultats pendant le trade, date de résultats inconnue |
| 5. Sentiment | `agents/sentiment.py` | RSS Yahoo / Google News, volume, Grok (optionnel) | **veto** seulement si l'actualité est très négative |
| 6. Testeur | `agents/specialists.py` + `quantitative/` | moteur de compétition | s'oppose si la validation date de plus de 120 jours |
| 7. Monte-Carlo | `simulations/` | trajectoires conditionnelles, sans edge, chocs | s'oppose si l'espérance < 0,05R, P(perte > 1,5R) > 15 %, ou si les sous-échantillons ne sont pas unanimes |
| 8. Risk manager | `risk/manager.py` | compte, positions, corrélations | **veto absolu** |
| 9. Exécution | `execution/` | instrument, heures NYSE, ordres en attente, horloge | **veto** si marché fermé, ordre incertain ou horloge décalée |
| 10. Auditeur | `agents/specialists.py`, `reports.py` | trades clos, décisions | propose des améliorations, n'applique **jamais** rien automatiquement |

## 3. Validation des stratégies (DONNÉES SYNTHÉTIQUES — sans valeur réelle)

Exécution du 9 novembre 2026 : 20 actifs fictifs, 10 ans, 7 plis walk-forward, 7,7 s.
- 27 548 trades simulés, dont 10 169 réalisables avec 100 $.
- Un trade n'est pas réalisable si son stop est trop large : avec 0,50 $ de risque max et un ordre minimum de 10 $, le stop doit rester sous ~5 %.

| Rang | Famille | Statut | n WF | E[R] | IC90 bas | PF | Sharpe | Raison du rejet |
|---|---|---|---|---|---|---|---|---|
| 1 | volatility_breakout | validée **sur données simulées → non éligible** | 149 | +0,316 | +0,122 | 1,67 | 1,04 | — |
| 2 | momentum | rejetée | 440 | +0,111 | +0,010 | 1,21 | 0,71 | test final négatif |
| 3 | relative_strength | rejetée | 56 | +0,128 | −0,094 | 1,32 | 0,39 | IC, test final |
| 4 | trend_following | rejetée | 145 | +0,083 | −0,070 | 1,19 | 0,35 | IC |
| 5 | mean_reversion | rejetée | 324 | +0,046 | −0,063 | 1,09 | 0,26 | 5 critères |
| 6 | multi_timeframe | rejetée | 174 | +0,017 | −0,127 | 1,03 | 0,07 | 6 critères |

Le marché synthétique contient volontairement des tendances. Que les stratégies de
tendance y gagnent ne prouve donc rien. **Seul `research` lancé sur les vraies données
Yahoo dira quelles stratégies sont éligibles. Il est possible qu'aucune ne le soit :
dans ce cas, le bot ne tradera pas, et c'est le comportement correct.**

## 4. Backtest portefeuille hors échantillon (SYNTHÉTIQUE)

Les stratégies ont été choisies sur les données d'avant le 4 décembre 2024, puis testées
sur la période 2024-12-04 → 2026-11-09, jamais vue. Résultat avec les vraies règles de risque :
- capital : 100,00 $ → 103,84 $, soit **+3,84 %** ;
- drawdown max : 3,80 % ;
- 72 trades, 42 % de gagnants, profit factor 1,22, +0,13R en moyenne ;
- coupe-circuit jamais déclenché.

## 5. Monte-Carlo (SYNTHÉTIQUE, meilleure stratégie, horizon 100 trades)

- **Scénario de base** (20 000 séquences ré-échantillonnées sur 149 trades réels) :
  - rendement : 5e centile +3,9 %, médiane +16,8 %, 95e centile +31,4 % ;
  - drawdown au 95e centile : 6,6 % ;
  - **P(toucher le coupe-circuit de −5 %) = 17 %** ;
  - série perdante au 95e centile : 10 trades.
- **Pire cas combiné** (−15 % de gains, gains −20 %, coûts doublés, 3 % de chocs) :
  - médiane −7,1 % ;
  - **P(coupe-circuit) = 94 %**.

**Leçon importante** : avec 0,50 $ de risque par trade, le plafond de drawdown de 5 $
correspond à seulement 10 pertes complètes. Si les conditions réelles sont moins
bonnes que l'historique, le coupe-circuit se déclenchera presque sûrement. C'est
voulu : il protège le capital et demande ton autorisation pour reprendre.

## 6. Audit de la gestion du risque

Résultats vérifiés par `python -m quantum_edge audit` et par les tests :
- **Vérifié** :
  - un trade conforme risque 0,4999 $, coûts inclus ;
  - 8 types de violations sont refusés ;
  - le risque cumulé jusqu'aux stops ne peut jamais dépasser la perte journalière restante.
- **Vérifié** : le coupe-circuit se déclenche à −1 $ / jour, −2,50 $ / semaine et −5 $ de drawdown. Aucune reprise n'est automatique : il faut la phrase « JE CONFIRME LA REPRISE EN DEMO » et un nom d'opérateur.
- **Vérifié** : l'arrêt d'urgence ferme les positions et bloque les entrées.
- **Vérifié** : le risque ne remonte jamais après une perte (il ne peut que baisser).

## 7. Intégration API eToro

- **Sources** : docs officielles résumées par moteur de recherche.
  - Authentification par `x-api-key`, `x-user-key` et `x-request-id`.
  - Ordres démo via `/api/v1/trading/execution/demo/market-open-orders/by-amount` (marquée « deprecated », la remplaçante annoncée est `POST /api/v2/trading/execution/demo/orders`).
  - Portefeuille via `/api/v1/trading/info/demo/portfolio`.
- **Implémenté** :
  - limitation de débit à 4 requêtes/s ;
  - 4 tentatives avec attente exponentielle sur les erreurs 429 / 5xx / réseau ;
  - un ordre n'est confirmé que quand la position est visible dans le portefeuille ;
  - si le statut est incertain, tout est bloqué jusqu'au rapprochement ;
  - les positions fermées par eToro (stop ou objectif) sont comptabilisées ;
  - mesure de l'horloge via l'en-tête `Date`.
- **Non vérifié** : le nom exact des routes, leurs paramètres et le format des réponses. Le parseur tolère les variations de casse, mais **`etoro-check` doit passer avant le premier ordre**.
- **Limite connue** : le prix de sortie d'une position fermée par eToro est *estimé* (stop ou objectif). Le vrai prix est visible dans l'historique eToro.

## 8. Tests

`python -m pytest -q` → **70 réussis, 0 échec** :
- sécurité : 14 ;
- risque : 13 ;
- quantitatif et stratégies : 17 ;
- exécution : 5 ;
- agents : 13 ;
- intégration (moteur, coupe-circuit, reprise après crash, tableau de bord, WebSocket, jeton) : 8.

`python -m quantum_edge audit` → 9 PASS, 2 « AWAITING CREDENTIALS » (authentification et ordres eToro).

## 9. Limites connues

1. **Biais du survivant** : l'univers est fait d'actions qui existent aujourd'hui. Les performances historiques sont probablement surestimées.
2. **Agents non rejouables dans le backtest** : technique intraday, macro et sentiment ne peuvent pas être rejoués sur le passé avec des données gratuites. Le backtest valide la couche statistique, le risque et l'exécution.
3. **Intraday Yahoo limité** : 60 jours en 5m et 15m, 730 jours en 1h. La confirmation multi-unités est un filtre en direct, pas une stratégie validée sur des années (la famille `multi_timeframe`, elle, utilise les données hebdomadaires et journalières et est validée).
4. **Sentiment basique** : un lexique de mots-clés. Grok (payant) peut l'enrichir.
5. **Calendrier macro** : CPI et emploi sont à saisir à la main. Si le fichier est vide, l'agent macro reste neutre et l'indique.
6. **Jours fériés NYSE** : codés pour 2026-2027. À mettre à jour ensuite.
7. **Minimum d'ordre de 10 $** : supposé, à confirmer par instrument chez eToro. Il limite les stops à ~5 %.
8. **Statistiques des Popular Investors eToro** : non intégrées.

## 10. Démarrer l'exploitation démo autonome

1. `scripts\install_windows.ps1`
2. `python scripts\update_macro_calendar.py`, puis ajoute les dates CPI et emploi dans `config\macro_events.csv`.
3. `scripts\run_research.bat`. Lis `reports\research\*.md` : si aucune stratégie n'est validée, **ne force rien**.
4. Mode simulé sur données réelles pendant 1 à 2 semaines : `scripts\start_bot.bat` et `scripts\start_dashboard.bat`.
5. Crée tes clés eToro démo, mets-les dans `.env`, puis lance `python -m quantum_edge etoro-check` jusqu'à ce que tout soit vert.
6. Mets `EXECUTION_BACKEND=etoro_demo` dans `.env` et relance le bot.
7. Observe 8 à 12 semaines : lis le rapport hebdomadaire (`reports\weekly\`) et relance `research` chaque mois.
8. Le passage en argent réel reste **désactivé** dans ce projet. Il faudrait une refonte séparée et explicitement approuvée.
