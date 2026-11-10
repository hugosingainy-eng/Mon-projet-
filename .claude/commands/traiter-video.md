---
description: Automatisation complète - transforme une vidéo brute en vidéo TikTok habillée, avec légende, hashtags, réponses et contrôle qualité
---
Vidéo à traiter : $ARGUMENTS
(chemin d'un fichier vidéo, de préférence le fichier d'origine plutôt qu'un enregistrement d'écran ; éventuellement suivi d'une consigne)

Tu es le Directeur CM. Déroule cette chaîne sans t'arrêter, dans un dossier `demo/AAAA-MM-JJ-sujet/` :

1. **Préparation (toi)** : `python3 outils/preparer_video.py <vidéo> <dossier>/preparation`. Regarde `planche.jpg` et lis `transcription.txt`. Corrige la transcription (noms propres, « Mièdaou », chiffres) dans `transcription-corrigee.json` en gardant les temps. Repère les textes déjà incrustés dans la vidéo et les transitions de l'original (images à 5 par seconde avec ffmpeg si besoin). Écris `brief.md` : déroulé plan par plan, parole, constats.
2. **En parallèle** :
   - `stratege-contenu` : ce que cette vidéo vaut par rapport à ce qui marche (format, accroche, montage), en s'appuyant sur le dernier fichier de `contenus/strategie/`.
   - `directeur-artistique` : diagnostic noté et **feuille d'habillage** (`feuille-habillage.md`) réalisable avec `outils/habiller_video.py` (lui donner la liste des effets que l'outil sait faire : voir l'en-tête du script).
   - `agence-tiktok` : version re-tournée améliorée + légende.
   - `conversion-devis` : appel à l'action, hashtags, réponses aux commentaires probables.
3. **Montage (toi, rôle du monteur)** : traduis la feuille en `habillage.json` (exemple complet : `demo/video-offre-20-ans/habillage.json`), lance `python3 outils/habiller_video.py <dossier>/habillage.json`, extrais des images clés et vérifie toi-même : textes dans la zone sûre, rien sur le visage, textes d'origine masqués, offre lisible avant 3 s. Le script refuse de rendre si un texte passe trop vite (1 s + 0,3 s par mot, carton 3 s, sous-titres 0,8 s) : allonge ou coupe des mots, ne force pas. Corrige et relance jusqu'à ce que ce soit propre. Note les écarts avec la feuille dans le champ `_ecarts`.
4. **Miniature** : selon la feuille, en image 1080 x 1920 (`rendu/miniature.jpg`).
5. **Contrôle** : `directeur-artistique` note le rendu final (images extraites) et donne VALIDÉE ou À CORRIGER. Applique les corrections faisables sans retournage, une fois.
6. **Rapport** : `README.md` du dossier avec la vidéo, la miniature, la planche avant/après, la légende, les hashtags, l'appel à l'action, la musique recommandée (son qui marche le mieux en ce moment et qui colle à la vidéo, utilisable par un compte professionnel, + 2 alternatives), le verdict qualité, et ce que Mièdaou doit faire (valider, accords d'image, publier).

Règles : rien n'est publié ; aucun chiffre inventé ; mentions « *Voir conditions en agence » / « selon conditions » à l'écran dès qu'une offre ou le -50 % apparaît ; ne jamais annoncer comme fait ce qui ne l'est pas.
