# Bot de trading multi-agents pour eToro (mode démo)

Bot qui trade du **lundi au vendredi** sur un **compte démo eToro**, avec un budget
virtuel de **100 $**. Avant chaque trade, une équipe de sous-agents analyse le setup et
le rejoue **des dizaines de milliers de fois** (Monte-Carlo). Le trade n'est pris que
si l'espérance reste positive même dans les scénarios pessimistes.

> ⚠️ **Avertissement.** Aucun bot ne garantit des gains. Les meilleurs traders perdent
> souvent, mais ils coupent leurs pertes vite et laissent courir leurs gains. Ce bot
> applique ce principe, mais les résultats passés ou simulés ne préjugent pas des
> résultats futurs. Reste en **démo** au moins 2 à 3 mois avant d'envisager autre chose.
> Le code refuse volontairement les routes de trading réel.

## La philosophie : penser comme un trader professionnel

| Principe | Trader | Dans le bot |
|---|---|---|
| Suivre la tendance, couper les pertes | Richard Dennis (Turtles) | Stratégies `turtle_breakout` / `turtle_breakdown_short`, stop à 2 ATR |
| Acheter des leaders en tendance saine après une contraction | Mark Minervini (SEPA/VCP) | `minervini_vcp` : stop ≤ 8 %, objectif 3R |
| Acheter la panique dans une tendance haussière | Larry Connors (RSI-2) | `connors_rsi2` |
| Momentum : reprise après une consolidation | Kristjan Kullamägi | `momentum_pullback` |
| « Defense first », ne jamais risquer gros | Paul Tudor Jones | 1 % de risque par trade (2 % max), coupe-circuit à -20 % |
| Augmenter la taille seulement quand tout est aligné | Stanley Druckenmiller | La taille dépend de la conviction du comité |
| Ne pas nager contre le courant | Ed Seykota | L'agent régime bloque les achats en marché baissier |

## Les sous-agents

```
 Agents stratégies (5)  ──► setups détectés sur la dernière bougie
          │
          ▼
 Agent historien  ── toutes les fois où ce setup est apparu (sur l'actif ET sur
          │           tout l'univers) : win rate, profit factor, t-stat
          ▼
 Agent régime     ── tendance de l'actif + du marché (SPY), volatilité extrême ?
          │
          ▼
 Agent Monte-Carlo ── 50 000 trajectoires par trade :
          │            • trajectoires réelles qui ont suivi ce setup (remises à l'échelle)
          │            • 40 % de trajectoires « sans edge » (garde-fou anti-illusion)
          │            • 2 % de chocs extrêmes (gaps, krach)
          │            → espérance en R, P(gain), P(grosse perte), CVaR 5 %, Kelly
          ▼
 Comité           ── vote : UN seul critère rouge suffit à rejeter
          │
          ▼
 Risk manager     ── taille de position (1 à 2 % de risque, ¼ Kelly, 30 % max/ligne,
                      5 positions max, -6 %/semaine → pause, -20 % → arrêt total)
```

Les candidats sont évalués **en parallèle** (un processus par cœur CPU). Un scan typique
lance plusieurs centaines de milliers de simulations, et un backtest sur 3 ans plus de
**12 millions**.

Chaque trade a un stop-loss et un take-profit envoyés directement à eToro. S'il n'a
rien donné au bout de 15 jours de bourse, le bot le ferme.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # puis remplis tes clés
```

### Obtenir les clés API eToro (démo)
1. Connecte-toi à eToro et passe en **Portefeuille virtuel** (démo).
2. Va dans **Paramètres → Trading → API Key Management** et crée une clé.
   Choisis l'environnement **Virtual/Demo** avec la permission **Write**.
3. Mets `ETORO_API_KEY` et `ETORO_USER_KEY` dans `.env`.

## Utilisation

```bash
# 1. Tester la stratégie sur ~3 ans de vraies données (Yahoo Finance)
python -m etoro_bot backtest --data yahoo

# 2. Un scan « à blanc » : affiche ce que le bot ferait aujourd'hui (aucun ordre)
python -m etoro_bot scan --mode paper --data yahoo

# 3. Lancer le bot sur le compte DÉMO eToro, du lundi au vendredi
python -m etoro_bot run --mode demo

# État du portefeuille du bot
python -m etoro_bot status --mode demo
```

Options utiles : `--capital 100`, `--paths 100000` (plus de simulations),
`--workers 8` (plus de sous-agents en parallèle), `--symbols AAPL,NVDA,MSFT`.

Le bot doit tourner en continu (PC allumé, serveur ou petit VPS). Exemple avec `tmux` :
`tmux new -s bot 'python -m etoro_bot run --mode demo'`.
Il surveille les positions toutes les 15 min et cherche de nouveaux trades chaque jour
à 20h15 UTC, juste avant la clôture de Wall Street. Il n'ouvre rien le vendredi soir,
pour éviter le risque du week-end.

Journaux : `logs/bot.log`, `logs/decisions-AAAA-MM-JJ.json` (détail de chaque vote),
`state/ledger-demo.json` (positions et P&L du budget de 100 $).

## Réglages (`etoro_bot/config.py`)
- `RiskConfig` : capital, risque par trade, levier (1 par défaut), limites de perte.
- `SimulationConfig` : nombre de simulations, seuils du comité (espérance minimale,
  profit factor, t-stat…).
- `DEFAULT_WATCHLIST` : actifs suivis (actions US, ETF, or, BTC, ETH). La crypto coûte
  cher sur eToro (1 % par côté), donc le comité la valide rarement.

## À vérifier avant le premier lancement en démo
L'API publique d'eToro évolue : certaines routes v1 sont marquées « deprecated » et
remplacées par `POST /api/v2/trading/execution/demo/orders`. Toutes les routes sont
regroupées dans `ENDPOINTS`, dans `etoro_bot/etoro_client.py`. Compare-les avec
https://api-portal.etoro.com et ajuste-les si besoin. Lance d'abord un `scan` en mode
`paper` avec `--data etoro` pour vérifier que les données arrivent bien.

## Tests
```bash
pytest -q
```
