# Origine des skills ig-*

Copiés depuis https://github.com/Jakeschincariol/instagram-agent-skill (commit d03c56b, licence MIT, voir `LICENCE-instagram-agent-skill.txt`).

Modifications apportées dans ce dépôt :

1. Les fichiers d'état sont lus et écrits dans `.claude/instagram/` à la racine du projet au lieu de `~/.claude/instagram/`, pour qu'ils soient conservés dans le dépôt.
2. Prise en charge du français, en plus de l'anglais :
   - `ig-reel/hookscore.py`, `ig-reel/beats.py`, `ig-caption/caption.py`, `ig-human/detect.py`, `ig-human/humanize.py`, `ig-viral/swipe.py` : lettres accentuées, euros et unités françaises, vocabulaire français (tension, nombres, impératifs, ouvertures molles, demandes), élisions, tutoiement et vouvoiement.
   - `ig-reel/hooks.json` : champs `template_fr`, `example_fr`, `on_screen_fr`, `match_fr` pour les 26 formules.
   - `ig-human/slop.json` : 28 formules, 16 mots et 13 tournures en français.
3. Correction d'un défaut d'origine dans `hookscore.py` : une ouverture molle était détectée par début de chaîne, si bien que « yo » pénalisait toute accroche commençant par « You ». La comparaison se fait désormais sur des mots entiers ; trois des 26 exemples anglais gagnent 3,6 points, les autres notes anglaises sont inchangées.

Les scripts Python sont locaux (bibliothèque standard uniquement, aucun accès réseau). Les listes de mots françaises sont un point de départ à enrichir ; les messages affichés par les outils restent en anglais.
