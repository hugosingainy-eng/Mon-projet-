# Community manager IA de Mièdaou — conception

## But
Faire connaître Mièdaou Services à La Réunion sur TikTok, Instagram et Snapchat : 10 000 abonnés TikTok (départ 7 488) et 10 à 30 devis en 30 jours. Notoriété chez les 18-30 ans, clients chez les 25-60 ans.

## Approche retenue
Une équipe de sous-agents Claude Code versionnée dans ce dépôt, pilotée par un Directeur CM (`CLAUDE.md`) et lancée par des commandes. Les agents préparent ; un humain de Mièdaou filme, valide et publie.

Écartée : une application autonome qui publie seule. Elle exige des accès API par réseau (absents pour Snapchat en organique) et retarderait le démarrage.

## Composants
- `marque/fiche-marque.md` : faits, avantages client, cibles, ton. Seule source de vérité.
- `marque/charte-graphique.md` : couleurs, polices, formats, qualité vidéo.
- `marque/bibliotheque-animations.md` : effets de montage style TikTok (sous-titres, titres, zooms, transitions, sons) et recettes.
- `.claude/agents/` : stratege-contenu, directeur-artistique, veille-tendances, agence-tiktok, agence-instagram, agence-snapchat, hashtags-seo, monteur-video, bios-profils, conversion-devis, analyste.
- `.claude/commands/` : `/semaine`, `/tendances`, `/video`, `/bios`, `/bilan`.
- `contenus/` : bios, hashtags, calendrier 30 jours, scripts, plans de montage.
- `suivi/` : `kpi.csv`, `devis.csv`, bilans.

## Flux
Veille → agences (en parallèle) → hashtags et conversion → monteur → validation humaine → publication → saisie des chiffres → analyste → plan de la semaine suivante.

## Règles transverses
Avantage client en gros dans chaque contenu ; appel au devis avec lien du site ; aucune affirmation hors fiche de marque ; accord écrit pour toute personne filmée, jamais de visage d'enfant sans accord parental ; audio sous licence ; pas de faux contenu généré ; pas d'achat d'abonnés ni d'automatisation d'engagement.

## Monteur vidéo
Rushs réels comme base. CoDesign (IMG.LY) pour montage, titres, sous-titres et export mp4 ; Nano Banana (Gemini) pour images ; Veo (Gemini) pour plans d'illustration ; CapCut pour la finition humaine. Si un outil n'est pas connecté, le monteur livre le plan de montage et les prompts au lieu d'une vidéo.

## Limites connues
- Pas de publication automatique.
- L'objectif 10 000 n'est pas garanti ; l'analyste mesure l'écart chaque semaine.
- Les chiffres sont saisis à la main par l'équipe.
- Le site n'a pas pu être lu directement lors de la conception ; la fiche de marque vient de résultats de recherche et doit être relue par Mièdaou.
