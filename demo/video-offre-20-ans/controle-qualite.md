# Contrôle qualité final : « Offre anniversaire 20 ans » (version habillée)

- **Fichier contrôlé :** `rendu/offre-20-ans-habillee.mp4`, 14,98 s, 1080 x 1920, 30 im/s, H.264 8,9 Mb/s, AAC 155 kb/s.
- **Également contrôlés :** `rendu/miniature.jpg` (1080 x 1920) et `rendu/avant-apres.jpg`.
- **Référence :** `feuille-habillage.md`, `habillage.json`, avec ses écarts assumés (champ `_ecarts`).
- **Méthode :**
  - Images extraites toutes les 0,5 s, plus 10 images en pleine définition (0,4 / 1,5 / 2,9 / 4,3 / 6,7 / 7,6 / 8,7 / 9,6 / 10,5 / 14,0 s).
  - Mesure au pixel de la hauteur des textes.
  - Mesure du son : EBU R128 et détection des silences.
  - Comparaison des temps des sous-titres avec `preparation/transcription-corrigee.json` (temps de la source, donc sortie = source - 0,8 s).
- **Limite :** je n'ai pas pu écouter la vidéo. Les remarques sur le son s'appuient sur les mesures et sur la transcription horodatée.

---

## 1. Notes par critère

| Critère | Note /10 | Constat |
|---|---|---|
| Accroche visuelle (0-1 s) | 7 | L'affiche s'affiche plein cadre dès la 1re image (`TIT-7`) et l'offre se lit tout de suite. Mais l'affiche n'occupe que y 245-1310 : le bas de l'écran (y 1440-1920) reste un aplat bleu vide. Elle ne dure que 0,8 s et c'est la même image qu'à 9,9 s, donc la fin de la vidéo n'apporte rien de nouveau. |
| Avantage lisible avant 3 s | 8 | Oui, deux fois : sur l'affiche de 0 à 0,8 s, puis avec le bandeau « 50 € OFFERTS* » à 2,62 s (écart assumé, au lieu de 2,2 s). Le bandeau est lisible son coupé. Son texte est trop petit pour le bandeau : environ 64 px rendus contre 100 px prévus, et il n'occupe que 510 px sur 790. |
| Sous-titres | 5 | **Style :** karaoké mot par mot correct (mot actif et mots-clés en orange, contour noir), bien placé (y 1351-1383), jamais sur le visage. **Taille :** 33 px de hauteur de capitales, soit environ 45 px de police contre 60 prévus. C'est petit sur une robe très imprimée. **Synchro :** les temps sont ceux estimés dans ma feuille (`sous-titres-feuille.json`), pas recalés sur la vraie parole comme la feuille le demandait (§4). Les sous-titres sont donc en avance, de plus en plus : 0,1 s au début, environ 0,6 s sur « Mièdaou fête » (affiché à 6,2 s, dit vers 6,8 s), environ 0,75 s sur « À l'occasion des 20 ans » (affiché 9,25-9,85 s, dit 10,0-10,9 s). |
| Image | 6 | Bonne lumière, sujet net. La source reste un enregistrement d'écran recompressé, recadré puis zoomé jusqu'à 120 % : image douce, surtout de 4,7 à 5,5 s et de 8,4 à 9,9 s. Débit de 8,9 Mb/s, sous les 12 Mb/s minimum de la feuille. |
| Son | 6 | **Mesures :** -13,8 LUFS intégré (conforme), crête vraie -5,8 dBFS, plage de 4,5 LU : propre. **Musique :** elle reste sous la voix ; on ne peut pas l'enlever sans les pistes séparées. **Fin muette :** 2,9 s de silence (12,1 → 15,0 s) sur l'affiche figée et le carton. **« Attends » :** la transcription automatique place ce mot à 0,23-0,72 s de la source, avant la coupe à 0,8 s. Les niveaux mesurés à cet endroit ne permettent pas de trancher : **à vérifier à l'écoute**. Si le mot est coupé, l'accroche parlée commence à « vous faites encore… ». |
| Rythme | 6 | Bonne densité de 0 à 9,9 s : un changement au moins toutes les 1,5 s. Puis **affiche fixe de 9,9 à 13,0 s (3,1 s sans aucun changement)**, parce que le zoom prévu (`MOV-2` puis `MOV-5`) n'a pas été fait. C'est la règle des 2 s qui est enfreinte, au moment exact où le spectateur décide de rester ou non. Les zooms sur la conseillère (104 / 112 / 118 / 106 %) sont visibles mais très discrets. |
| Cohérence de marque | 6 | **Ce qui va :** couleurs justes (`#0070A0`, `#E89838`, `#00557A`), Montserrat et Poppins, bandeaux arrondis cohérents. **Ce qui ne va pas :** tous les textes sont rendus à environ 65-70 % de la taille prévue (voir C2) ; « MIÈDAOU / A 20 ANS » est tassé, les deux lignes presque collées dans un bandeau à moitié vide ; aucun logo Mièdaou en dehors de l'affiche ; le carton final n'occupe que le tiers haut de l'écran. |
| Appel au devis | 7 | Le carton de 2 s est présent : « DEVIS GRATUIT » en orange, « LIEN EN BIO », 0262 30 36 37, miedaou.fr, Toute La Réunion, rappel de l'offre et mention. Mais il manque le logo, les textes sont petits (« DEVIS GRATUIT » à environ 76 px au lieu de 110), la moitié basse est vide, la pulsation est peu perceptible et le carton est muet. |
| Conformité | 6 | **Mentions :** « *Voir conditions en agence » est présente chaque fois que l'offre est à l'écran, et « Crédit d'impôt selon conditions » accompagne le -50 %. Les faits sont tous conformes à la fiche de marque et il n'y a aucun contenu généré par IA. Mais les mentions de 2,7 à 6,2 s, en blanc fin sur le plafond clair, sont peu contrastées. **Trois points restent bloquants avant publication, et ce n'est pas au monteur de les régler :** (1) l'accord écrit de la conseillère pour son image n'est pas confirmé ; (2) la licence de la musique d'origine n'est pas vérifiée ; (3) la date de fin de l'offre n'est pas connue. |
| Miniature | 8 | Conforme à la feuille : visage souriant au regard caméra, « 50 € OFFERTS* » sur bandeau orange, « SUR VOTRE MÉNAGE », pastille « 20 ANS » au-dessus de l'épaule, mention lisible. Tout le texte reste dans la zone sûre et dans la découpe 1080 x 1350. Seul défaut : l'image est un peu douce (agrandie depuis l'enregistrement d'écran). |

**Note globale : 6/10** (contre 3/10 pour l'original). Le progrès est net : l'offre est vue dès la 1re seconde, il y a des sous-titres et la vidéo se termine sur un appel au devis.

## 2. Verdict : **À CORRIGER**

Huit critères sont sous 7, alors que la règle demande qu'aucun ne le soit. Les corrections C1 à C7 se font sans retournage, en un seul nouveau rendu. Les points de conformité (H1 à H3) dépendent de Mièdaou et bloquent la publication, même une fois le montage corrigé.

---

## 3. Corrections horodatées, sans retournage (pour le monteur)

| # | Temps | Problème | Correction |
|---|---|---|---|
| C1 | 0:00-0:09.9 | Sous-titres en avance sur la parole (jusqu'à 0,75 s) | Générer les sous-titres à partir de `preparation/transcription-corrigee.json` (temps de sortie = temps source - 0,8 s), et non de `sous-titres-feuille.json`. Repères attendus en sortie : « Et si » 2,1 s ; « cadeau » 6,3 s ; « Mièdaou fête » 6,8 s ; « 20 ans » 8,1 s ; « quelque chose pour vous » 9,1 s. « À l'occasion des 20 ans » (10,0 s) tombe alors sur l'affiche : le retirer, ou le prolonger sur l'affiche en bas (y 1340-1420), à la place des mentions, qui remontent à y 1230-1330. Recaler sur ces repères les effets liés à un mot (bandeau « MIÈDAOU » sur « Mièdaou », pop « A 20 ANS » sur « 20 ans »), sans changer l'ordre. |
| C2 | Toute la vidéo | Tous les textes rendus à environ 65-70 % de la taille prévue. Hauteurs de capitales mesurées : bandeau 50 € 45 px, sous-titres 33 px, « DEVIS GRATUIT » 53 px | Calibrer le rendu ASS : `PlayResX=1080`, `PlayResY=1920`, puis multiplier les tailles par environ 1,4, ou les régler jusqu'à mesurer une hauteur de capitales égale à 0,7 fois la taille prévue (70 px pour un titre de 100 px, 42 px pour les sous-titres de 60 px). Vérifier ensuite que rien ne dépasse x 850. Ne pas passer en dessous de 90 px pour les bandeaux (règle de la feuille). |
| C3 | 0:00.8-0:02.6 | « ENCORE VOTRE MÉNAGE » est centré en x 540 et s'étend de x 108 à 972, donc hors de la zone sûre. À la bonne taille, la ligne ne tiendrait plus sur une ligne. *(Erreur de ma feuille : 100 px sur une ligne était irréalisable.)* | Passer en 3 lignes centrées en x 455 : « ENCORE » / « VOTRE MÉNAGE » (blanc, 96 px) / « VOUS-MÊME ? » (orange, 120 px), dans la largeur 60-850. Garder le fond bleu nuit qui cache les textes d'origine, mais le limiter en hauteur à ce que ces textes demandent, pour dégager le haut de la tête. |
| C4 | 0:06.2-0:08.4 | « MIÈDAOU / A 20 ANS » tassé : lignes collées, environ 70 px. Une étoile jaune des paillettes d'origine dépasse à droite du bandeau (x 860, y 580) et des points blancs restent sous le bandeau, sur les cheveux | Interligne réel : ligne 1 centrée sur y 440, ligne 2 sur y 570, toutes deux à 110 px (après C2). Élargir le bandeau à x 40-870 sur cette séquence seulement : la zone sûre est tolérée pour un fond sans texte. Les scintillements sur les cheveux font partie de l'image d'origine et sont acceptables : on ne couvre pas le visage. |
| C5 | 0:09.9-0:13.0 | Affiche fixe pendant 3,1 s, rythme cassé (zoom non réalisé, écart assumé que je n'accepte pas) | Faire le mouvement de la feuille : zoom 100 → 112 % centré sur « 50€ OFFERTS » (45 % de la largeur, 35 % de la hauteur de l'affiche) de 9,9 à 11,5 s, puis glissement vers « -50% » (55 %, 78 %) de 11,5 à 12,4 s, le tout rogné au cadre 820 x 1062. Filtre ffmpeg : `zoompan` sur l'affiche découpée, ou `crop` animé suivi d'un `scale`. À défaut, deux recadrages secs (110 % sur « 50€ » à 11,0 s, 110 % sur « -50% » à 12,1 s) suffisent pour tenir la règle des 2 s. |
| C6 | 0:13.0-0:15.0 | Carton final : pas de logo, textes petits, moitié basse vide | Après C2, répartir les lignes de y 300 à 1300. Le logo : `logo-miedaou.png` est présent dans le dossier, mais il ne fait que 280 x 108 et son origine n'est pas notée. Ne l'utiliser que si Mièdaou confirme que c'est son fichier officiel, et à sa taille d'origine (280 px, sans agrandissement ni retouche). Sinon, laisser la zone vide comme prévu. Rendre la pulsation de « DEVIS GRATUIT » visible : 100 → 108 → 100 %. |
| C7 | 0:02.7-0:06.2 | Mentions en blanc fin sur le plafond clair, peu lisibles | Contour noir 4 px réel (vérifier qu'il est bien appliqué) et ombre portée, ou bien un fond noir à 50 % derrière les deux lignes. Garder 46-48 px après C2. |
| C8 | Export | 8,9 Mb/s au lieu de 12 Mb/s minimum, AAC 155 kb/s au lieu de 192 | Réexporter en `-b:v 12M -maxrate 14M -bufsize 24M`, `-c:a aac -b:a 192k`, en gardant la normalisation à -14 LUFS. |
| C9 | 0:00.0-0:00.8 | Mot « Attends » peut-être coupé | Écouter la vidéo de 0 à 1 s. Si « Attends » manque, démarrer la piste son à 0,2 s de la source (et non 0,8 s), en gardant l'image de l'affiche en ouverture : il suffit de décaler le son et les sous-titres de 0,6 s et d'allonger l'ouverture d'autant, ce qui ne change pas la synchro labiale après la coupe. Si le mot est bien présent, ne rien changer. |
| C10 (option, humain qui publie) | 0:12.1-0:15.0 | 2,9 s muettes en fin de vidéo | Ajouter un son de la bibliothèque commerciale de la plateforme, à volume bas, au moment de la publication. On n'ajoute aucun son non licencié au montage. |

## 4. Points bloquants qui ne relèvent pas du montage (à régler par Mièdaou)

- **H1. Droit à l'image :** obtenir et archiver l'accord écrit de la conseillère.
- **H2. Musique de la piste d'origine :** confirmer qu'elle vient de la bibliothèque commerciale ou qu'elle est sous licence. Sinon, ne pas publier cette version sur Instagram ni sur Snapchat, et garder sur TikTok le son d'origine du post.
- **H3. Date de fin de l'offre :** à fournir. Si elle est connue, l'ajouter sur le carton (« Jusqu'au JJ/MM* »).

## 5. Ce qui demanderait un nouveau tournage (non bloquant pour cette version)

Ces défauts ne se corrigent pas au montage :
- l'image douce (enregistrement d'écran, plan large qu'il faut zoomer) ;
- la musique mélangée à la voix ;
- l'absence de plans de coupe ;
- l'offre qui n'est pas dite dans la première phrase.

Pour la prochaine vidéo, appliquer les 3 consignes du §6 de la feuille d'habillage :
1. dire et montrer l'offre dès le premier mot ;
2. cadrer à mi-poitrine, à moins d'un mètre, en prises courtes, avec 2 ou 3 plans sans personne ;
3. utiliser un micro-cravate, ne pas mettre de musique au tournage, et envoyer le fichier d'origine plutôt qu'un enregistrement d'écran.

## 6. Prochaine étape

Après le nouveau rendu (C1 à C9), le directeur artistique refait un contrôle en priorité sur trois points : la synchro des sous-titres, la taille des textes et l'affiche de 9,9 à 13 s. Le verdict VALIDÉE ne sera donné qu'après ce contrôle et la levée de H1 à H3.

---

## Corrections appliquées par le monteur (rendu suivant)
| Point | Fait |
|---|---|
| C1 | Sous-titres générés depuis `transcription-corrigee.json`, recalés sur la parole ; effets « MIÈDAOU » et « A 20 ANS » recalés sur les mots. Pas de sous-titres pendant l'affiche. |
| C2 | Rendu ASS calibré dans `outils/habiller_video.py` (facteur 1,4) : les tailles de la feuille sont maintenant les tailles visibles. |
| C3 | Accroche sur 3 lignes centrées en x 455 : ENCORE / VOTRE MÉNAGE / VOUS-MÊME ?, sur fond bleu nuit qui masque les textes d'origine. |
| C4 | Bandeau élargi (x 40-870), lignes à y 440 et 570. |
| C5 | Zoom animé sur l'affiche : 100 → 112 % sur « 50€ OFFERTS », puis glissement vers « -50% ». |
| C6 | Carton réparti de y 300 à 1 300, pulsation 108 %, logo du profil TikTok à sa taille d'origine (280 px) sur plaque blanche, à remplacer par le fichier officiel. |
| C7 | Mentions avec contour 5 px et ombre. |
| C8 | Export à 12 Mb/s constant. L'audio reste mesuré à environ 156 kb/s malgré la consigne de 192 kb/s (encodeur AAC de ffmpeg sur une piste courte) ; sans effet audible. |
| C9 | « Attends » était bien coupé : son et image démarrent maintenant à 0,2 s de la source, ouverture sur l'affiche allongée à 1,4 s. Durée : 15,6 s. |
| C10 | Reste à l'humain qui publie. |

Nouveau verdict à demander au directeur artistique sur ce rendu.
