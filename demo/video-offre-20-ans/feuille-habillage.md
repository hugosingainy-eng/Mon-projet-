# Feuille d'habillage — « Offre anniversaire 20 ans » (version virale, sans nouveau tournage)

- **Vidéo source :** enregistrement d'écran TikTok, 12,9 s, 1180 x 2324, 60 im/s (planche : `planche-originale.jpg`, affiche : `affiche-offre.jpg`).
- **Sortie :** 1080 x 1920, 30 im/s, H.264 12 Mb/s minimum, AAC 192 kb/s. **Durée : 15,0 s** (12,1 s d'images d'origine + 0,9 s d'image figée + 2,0 s de carton final).
- **Rendu :** ffmpeg (le monteur). Polices : Montserrat ExtraBold 800 (titres), Poppins SemiBold 600 (sous-titres, mentions).
- **Faits utilisés (fiche de marque uniquement) :** Mièdaou fête ses 20 ans ; 50 € offerts pour tout contrat régulier de ménage et repassage ; cumulable avec -50 % chaque mois grâce à l'avance immédiate du crédit d'impôt ; « *Voir conditions en agence » ; devis gratuit ; 0262 30 36 37 ; miedaou.fr.
- **Aucun son ajouté :** seule la piste d'origine est utilisée (les codes `SON-x` de la bibliothèque ne sont donc pas employés).

---

## 1. Diagnostic visuel de la vidéo d'origine

| Critère | Note /10 | Constat |
|---|---|---|
| Accroche visuelle (0-1 s) | 3 | La vidéo s'ouvre sur une marche dans le couloir avec un coucou flou : rien à lire, rien de net. La bonne phrase d'accroche n'arrive qu'à 1 s. |
| Avantage lisible avant 3 s | 1 | L'offre (50 € offerts + -50 %) n'apparaît qu'à 11 s, sur une affiche montrée 2 s. |
| Sous-titres | 1 | Aucun sous-titre. Le seul texte (vers 7-9 s, effet « paillettes » au-dessus de la tête) est illisible et hors charte. |
| Image | 6 | Bonne lumière chaude et décor propre, conseillère souriante et nette. Mais le plan est trop large (le visage occupe moins de 20 % de l'écran), et c'est un enregistrement d'écran recompressé, pas le fichier d'origine. |
| Son | 4 | Voix couverte par une musique de fond, volume trop fort (moyenne -9,5 dB). La transcription automatique s'est trompée, donc des spectateurs aussi. |
| Rythme | 2 | Un seul plan fixe de 10 s, sans coupe, sans zoom ni texte. La règle (un changement visuel toutes les 2 s) n'est pas tenue. |
| Cohérence de marque | 5 | L'affiche respecte les couleurs Mièdaou, mais pendant 11 s rien à l'écran ne dit Mièdaou : ni bleu, ni orange, ni logo. |
| Appel au devis | 0 | Ni « Devis gratuit », ni téléphone, ni « lien en bio ». La vidéo se coupe sur l'affiche. |
| Conformité | 6 | La mention « *Voir conditions en agence » est sur l'affiche, mais en 15 px et seulement 2 s. Musique d'origine à vérifier (licence) avant toute republication. Accord écrit de la conseillère pour son image : à confirmer. |

**Note globale : 3/10. Verdict : NON VALIDÉE.** Le fond est bon (énergie, sourire, accroche parlée, vraie offre). Le problème vient de l'ordre et de l'habillage : l'offre doit être lue avant 3 s, et rien ne doit rester fixe plus de 2 s.

**Principe de la refonte :**
1. Couper la marche floue du début : la vidéo démarre sur « Attends ».
2. Annoncer « 50 € OFFERTS* » à 2,2 s, en bandeau, pendant que la conseillère parle.
3. Sous-titres karaoké tout du long.
4. Un zoom ou un recadrage toutes les 1 à 2 s.
5. Cacher le texte « paillettes » sous un bandeau de marque.
6. Montrer l'affiche en grand avec un zoom qui la parcourt.
7. Terminer par un carton « DEVIS GRATUIT ».

---

## 2. Repères de mise en page (1080 x 1920)

- **Zone sûre (charte) :** x de 60 à 850, y de 230 à 1440. Tout texte reste dedans. **Axe de centrage des textes : x = 455** (milieu de la zone sûre), largeur maximum 790 px.
- **Position du sujet après recadrage de base :** sommet de la tête vers y 640, visage de y 850 à 1200, poitrine et robe de 1200 à 1920.
  - **Zone titres :** y 240 à 630, au-dessus de la tête (plafond, lampe).
  - **Zone sous-titres :** y 1310 à 1430, sous le menton, sur la robe.
  - Aucun texte sur le visage.
- **Recadrage de base de la source :** mise à l'échelle 1180 x 2324 → 1080 x 2127, puis découpe 1080 x 1920 à y = 103 (`scale=1080:-2,crop=1080:1920:0:103`). À vérifier sur une image extraite à 3 s : le sommet de la tête doit tomber entre y 620 et 660.
- **Centre des zooms sur le face caméra :** (540, 640), c'est-à-dire le sommet de la tête. Le crâne reste en place et le visage grandit vers le bas, ce qui ne recouvre ni les titres ni les sous-titres. À 112 %, le menton descend à y 1267, au-dessus des sous-titres (1310).
- **Texte « paillettes » d'origine :** vers y 515 à 650 dans le cadre de sortie, de 6,2 s à 8,2 s (sortie). Il est couvert par le bandeau « MIÈDAOU A 20 ANS ». Pendant ce bandeau, pas de zoom au-dessus de 100 %.
- **Affiche dans la source :** zone x 44 à 1032, y 358 à 1638 (`crop=988:1280:44:358`, à ajuster à ±10 px sur une image extraite à 11,5 s de la source). Elle est réduite à 820 x 1062 et posée à x 60, y 245 sur un fond bleu Mièdaou `#0070A0`.
- **Tailles des titres :** 96 à 110 px pour les textes d'une ligne, en dessous des 110-160 px de la charte, parce que la zone sûre ne fait que 790 px de large. Si un texte dépasse x 850 au rendu, réduire de 6 px, sans jamais descendre sous 90 px.

**Correspondance des temps :** sortie = source - 0,8 s, de 0,0 à 12,1 s.

---

## 3. Feuille d'habillage seconde par seconde

Codes : voir `marque/bibliotheque-animations.md`.
- **Fort** = effet fort, au plus un toutes les 3 s. Effets forts aux instants 0,0 / 3,6 / 10,2 / 13,0.
- Changements visuels aux instants 0,0 / 0,8 / 1,1 / 2,2 / 3,6 / 4,7 / 5,5 / 6,2 / 7,1 / 8,4 / 9,0 / 10,2 / 11,0 / 12,1 / 13,0 : jamais plus de 1,5 s sans changement.
- **Ouverture `TIT-7`** (ajoutée à la bibliothèque le 10/11/2026 par le stratège, à cause de cette vidéo) : l'affiche s'affiche plein cadre de 0,0 à 0,8 s, pendant que la piste d'origine démarre déjà sur « Attends ». Ce sont seulement les 0,8 premières secondes d'image du face caméra qui sont remplacées : aucune parole n'est perdue et la synchro labiale reste exacte après la coupe.

| Temps (sortie) | Ce qu'on voit / entend (source) | Effet (code) | Texte exact à l'écran | Couleur / police / taille / position (px) | Son |
|---|---|---|---|---|---|
| **0:00.0-0:00.8** | **Image :** affiche figée (image de la source à 0:11.5), même mise en page qu'à 10,2 s. **Son :** la piste d'origine démarre déjà, « Attends, vous… » (source 0:00.8-0:01.6) | `TIT-7` **fort** (offre en ouverture) : l'affiche apparaît en grossissement 110 → 100 % en 0,12 s + mention + `SUB-1` dès 0,2 s | Affiche (contenu d'origine) / *Voir conditions en agence / Crédit d'impôt selon conditions | Fond `#0070A0`. Affiche 820 x 1062 à x 60, y 245. Mention : blanc à 80 %, Poppins SemiBold 48 px, centrée x 455, y 1325-1373 et 1381-1429. **Sous-titres exceptionnellement à y 1200-1290**, sur la partie « AVEC L'AVANCE IMMÉDIATE » de l'affiche, avec un fond noir à 60 % derrière | Piste d'origine à partir de 0,8 s, fondu d'entrée 0,05 s, normalisée à -14 LUFS |
| **0:00.8-0:01.1** | Coupe vers le face caméra (source 0:01.6-0:01.9), synchro labiale conservée. La marche floue du début n'apparaît jamais. « …faites encore… » | `TIT-1` en version sans tremblement (130 → 100 % en 0,12 s, effet normal) + `MOV-2` zoom lent 100 → 104 % jusqu'à 2,2 s, centré (540, 640) + `SUB-1` | ENCORE VOTRE MÉNAGE | Blanc `#FFFFFF`, contour noir 6 px, Montserrat ExtraBold 100 px, centré x 455, ligne y 300-400 | Origine |
| **0:01.1-0:02.2** | « …votre ménage vous-même ? » | 2e ligne en « pop » (80 → 105 → 100 % en 0,15 s) + `SUB-1` | VOUS-MÊME ? | Orange `#E89838`, contour noir 6 px, Montserrat ExtraBold 130 px, centré x 455, y 410-540 (1re ligne maintenue) | Origine |
| **0:02.2-0:03.6** | « Et si je vous disais que vous pouvez… » | `TIT-2` : les 2 lignes de l'accroche disparaissent (0,1 s), un bandeau orange arrondi glisse de la gauche en 0,25 s + mention en fondu 0,2 s + `SUB-1`. Vidéo maintenue à 104 % | **50 € OFFERTS*** (bandeau) / *Voir conditions en agence (mention) | Bandeau : rectangle `#E89838`, rayon 24 px, x 60-850, y 250-390, ombre noire 30 % décalée de 6 px. Texte blanc, Montserrat ExtraBold 100 px, centré x 455. Mention : blanc, contour noir 4 px, Poppins SemiBold 48 px, centrée x 455, y 520-568 | Origine |
| **0:03.6-0:04.7** | « …vous en débarrasser… » | `MOV-1` **fort**, zoom coup de poing 104 → 112 % en 0,1 s centré (540, 640), puis maintien + 2e bandeau qui glisse de la gauche (0,25 s) + 2e ligne de mention + `SUB-1` | **+ PAYEZ -50 %*** (bandeau 2) / *Voir conditions en agence (mention, ligne 1) / Crédit d'impôt selon conditions (mention, ligne 2) | Bandeau 2 : `#0070A0`, rayon 24 px, x 60-850, y 400-505, texte blanc Montserrat ExtraBold 96 px (90 px s'il dépasse), centré x 455. Mention ligne 1 : y 520-568 ; ligne 2 : y 574-622, mêmes réglages. Le sommet de la tête reste à y 640 grâce au centre de zoom (540, 640) | Origine |
| **0:04.7-0:05.5** | « …tout en profitant… » | `MOV-3` recadrage sauté 112 → 118 %, centré (540, 640), coupe sèche sans transition, bloc offre maintenu + `SUB-1` | (bloc offre et mentions maintenus) | Inchangé | Origine |
| **0:05.5-0:06.2** | « …d'un cadeau ? » | `MOV-3` retour à 106 %, centré (540, 640) + `SUB-1` (« cadeau » en orange) | (bloc offre et mentions maintenus) | Inchangé | Origine |
| **0:06.2-0:07.1** | « Mièdaou fête… ». L'effet « paillettes » d'origine apparaît au-dessus de la tête | Le bloc offre et les mentions sortent par la gauche (0,15 s). Vidéo ramenée à 100 % (coupe sèche) pour que le bandeau couvre les paillettes. Bandeau orange qui glisse de la gauche en 0,25 s (`TIT-2`, effet normal) + `SUB-1` | **MIÈDAOU** (ligne 1 du bandeau) | Bandeau `#E89838`, rayon 24 px, x 60-850, **y 370-640** (couvre tout le texte « paillettes », y 515-650). Ligne 1 : blanc, Montserrat ExtraBold 110 px, centrée x 455, y 385-495 | Origine |
| **0:07.1-0:08.4** | « …ses 20 ans… » | 2e ligne du bandeau en « pop » (80 → 105 → 100 % en 0,15 s) + `SUB-1` | **A 20 ANS** (ligne 2) | Blanc, Montserrat ExtraBold 110 px, centrée x 455, y 510-620. Vidéo à 100 %, sans zoom | Origine |
| **0:08.4-0:09.0** | « …et on a quelque chose pour vous… » | Le bandeau sort par le haut (0,15 s), **seulement si les paillettes ont disparu** (sinon prolonger jusqu'à leur disparition). `MOV-2` en version rapide : zoom progressif 100 → 120 % de 8,4 à 10,2 s, centré (540, 1000), qui monte la tension + `SUB-1` | (aucun titre) | — | Origine |
| **0:09.0-0:10.2** | « …À l'occasion des 20 ans, Mièdaou vous offre… » | `TIT-3` machine à écrire (25 lettres/s), zoom progressif qui continue + `SUB-1` | LE CADEAU… | Blanc, contour noir 6 px, Montserrat ExtraBold 110 px, centré x 455, y 270-380. À 120 % le sommet de la tête est vers y 570, sans chevauchement | Origine |
| **0:10.2-0:11.0** | Affiche (source 0:11.0-0:11.8), sur fond bleu | **Fort** : coupe sèche, l'affiche entre en grossissement 90 → 100 % en 0,15 s (`MOV-1` appliqué à l'affiche). Incrustation de l'affiche en grand + mention en fondu 0,2 s. Sous-titres coupés | Affiche (contenu d'origine) / *Voir conditions en agence (ligne 1) / Crédit d'impôt selon conditions (ligne 2) | Fond plein `#0070A0` 1080 x 1920. Affiche découpée `crop=988:1280:44:358`, réduite à 820 x 1062, posée à x 60, y 245. Mention : blanc à 80 %, Poppins SemiBold 48 px, centrée x 455, lignes y 1325-1373 et 1381-1429 | Origine |
| **0:11.0-0:12.1** | Affiche (source 0:11.8-0:12.9) | `MOV-2` sur l'affiche : zoom 100 → 112 % centré sur « 50€ OFFERTS » (point de l'affiche à 45 % de sa largeur et 35 % de sa hauteur), à l'intérieur du cadre 820 x 1062 (rogné au cadre) | (mention maintenue) | Inchangé | Origine, fondu de sortie de 11,6 à 12,1 s |
| **0:12.1-0:13.0** | Dernière image de l'affiche figée (`tpad=stop_mode=clone:stop_duration=0.9`) | `MOV-5` sans le son « pause » : image figée + glissement du zoom (112 %) vers « -50% » (point à 55 % de la largeur et 78 % de la hauteur) en 0,6 s, puis maintien | (mention maintenue) | Inchangé | Silence (fin de la piste d'origine) |
| **0:13.0-0:15.0** | Carton final | `GFX-5` **fort** : coupe sèche vers le carton. Les éléments entrent l'un après l'autre en grossissement 130 → 100 % (0,12 s chacun, 0,08 s d'écart). « DEVIS GRATUIT » pulse 100 → 106 → 100 % toutes les 0,5 s | Logo Mièdaou / **DEVIS GRATUIT** / LIEN EN BIO / 0262 30 36 37 / miedaou.fr · Toute La Réunion / Offre 20 ans : 50 € offerts* / *Voir conditions en agence | Fond `#0070A0`. **Logo** officiel PNG (fichier à fournir par Mièdaou, jamais déformé ni recoloré), largeur 420 px, centré x 455, y 300-520. **DEVIS GRATUIT** : `#E89838`, Montserrat ExtraBold 110 px, centré x 455, y 600-710. **LIEN EN BIO** : blanc, Montserrat ExtraBold 80 px, y 730-810. **0262 30 36 37** : blanc, Montserrat ExtraBold 96 px, y 860-956. **miedaou.fr · Toute La Réunion** : blanc, Poppins SemiBold 56 px, y 1000-1056. **Offre 20 ans : 50 € offerts*** : blanc, Poppins SemiBold 56 px, y 1150-1206. **Mention** : blanc à 80 %, Poppins SemiBold 48 px, y 1240-1288 | Silence |

**Notes :**
- **Si la vraie parole ne colle pas aux temps du brief** (ils sont approximatifs) : garder l'ordre des effets et recaler chaque effet sur le mot indiqué (« Attends », « disais », « débarrasser », « cadeau », « Mièdaou », « 20 ans », « offre »).
- **Le carton final est muet,** puisqu'aucun son n'est ajouté. C'est acceptable, car TikTok relance la vidéo en boucle. Option réservée à l'humain qui publie : ajouter un son de la bibliothèque commerciale de la plateforme, à volume bas.
- **Logo :** si Mièdaou ne fournit pas le fichier officiel, ne pas découper le logo de l'affiche (basse définition) et ne pas le redessiner. Laisser cette zone vide et remonter les lignes de 220 px.

---

## 4. Sous-titres (`SUB-1`, karaoké mot par mot)

**Style :**
- Police et couleur : Poppins SemiBold 60 px, blanc, contour noir 6 px, une seule ligne, centrée x 455, ligne de base y 1400 (bloc y 1330-1420).
- Mot prononcé : orange `#E89838`, agrandi à 110 %.
- Mots-clés soulignés en orange en permanence dans leur groupe : **ménage, cadeau, 20 ans, vous offre**.
- Les sous-titres sont coupés pendant l'affiche et le carton (dès 10,2 s).

**Temps :** temps de sortie, calqués sur le brief (sortie = source - 0,8 s). Avant le rendu, recaler chaque mot sur la vraie parole avec une transcription horodatée mot par mot (whisper avec horodatage par mot, ou le filtre `whisper` de ffmpeg 8) : la fin (8,2-10,2 s) est très rapide et sera sans doute décalée.

| # | Début | Fin | Texte exact |
|---|---|---|---|
| 1 | 0:00.20 | 0:00.55 | Attends, |
| 2 | 0:00.55 | 0:01.35 | vous faites encore |
| 3 | 0:01.35 | 0:02.20 | votre **ménage** vous-même ? |
| 4 | 0:02.20 | 0:02.65 | Et si je |
| 5 | 0:02.65 | 0:03.10 | vous disais |
| 6 | 0:03.10 | 0:03.75 | que vous pouvez |
| 7 | 0:03.75 | 0:04.65 | vous en débarrasser |
| 8 | 0:04.65 | 0:05.45 | tout en profitant |
| 9 | 0:05.45 | 0:06.20 | d'un **cadeau** ? |
| 10 | 0:06.20 | 0:07.10 | Mièdaou fête |
| 11 | 0:07.10 | 0:08.20 | ses **20 ans**… |
| 12 | 0:08.20 | 0:08.75 | et on a |
| 13 | 0:08.75 | 0:09.25 | quelque chose pour vous. |
| 14 | 0:09.25 | 0:09.55 | À l'occasion |
| 15 | 0:09.55 | 0:09.85 | des **20 ans**, |
| 16 | 0:09.85 | 0:10.20 | Mièdaou **vous offre**… |

Si les groupes 14 et 15 durent chacun moins de 0,3 s après recalage, les fusionner en « À l'occasion des 20 ans, » (5 mots, toléré une fois).

**Mise en œuvre conseillée :**
- Créer un fichier `.ass` (libass, filtre `subtitles=`), avec un événement par état de mot : le groupe affiché, le mot actif en `{\c&H3898E8&\fscx110\fscy110}`.
- Couleur ASS au format BGR : `#E89838` s'écrit `&H3898E8&`.
- Contour : `\bord6`, couleur `&H000000&`.

---

## 5. Miniature recommandée

- **Image :** image figée de la source vers 0:02.0 (sortie 1,2 s) : la conseillère pose la question « vous-même ? », expression interrogative, regard caméra. Si elle a les yeux mi-clos, prendre une image entre 0:09.5 et 0:10.5 de la source (sourire). Recadrer à 118 % centré sur le visage : le visage occupe 35 à 40 % de la hauteur, le haut du crâne vers y 700. Pas d'autre image : pas d'avant/après, pas de visuel généré.
- **Texte (4 mots + mention) :**
  - Ligne 1, au-dessus de la tête : **« 50 € OFFERTS* »** sur bandeau orange `#E89838`, rayon 24 px, texte blanc Montserrat ExtraBold 120 px, centré x 455, y 330-470.
  - Ligne 2 : **« SUR VOTRE MÉNAGE »** en blanc, contour noir 6 px, Montserrat ExtraBold 96 px, centré x 455, y 490-590.
  - Le mot orange est donc « 50 € OFFERTS ».
  - Pastille « 20 ANS » : rond `#0070A0` de 150 px, texte blanc Montserrat ExtraBold 52 px, à x 70, y 610. Au-dessus de l'épaule, jamais sur le visage.
  - Mention : « *Voir conditions en agence », Poppins SemiBold 48 px, blanc, contour noir 4 px, y 1360-1408.
- **Lecture en 1080 x 1350 (grille Instagram) :** tout le texte est entre y 285 et 1635, donc lisible dans la découpe centrale.

---

## 6. Trois consignes de tournage pour la prochaine vidéo

1. **Dire l'offre dans la première phrase et la montrer dès la première seconde.** Par exemple : « 50 € offerts sur votre ménage, et vous payez moitié prix, je vous explique », affiche ou téléphone avec l'offre tenu en main dans le cadre. Pas d'entrée en marchant ni de coucou avant de parler : la vidéo commence sur le premier mot.
2. **Se rapprocher et varier les plans.** Téléphone à la verticale sur un appui, à hauteur des yeux, cadré à mi-poitrine, à moins d'un mètre. Tourner chaque phrase en prise courte séparée, une fois de face et une fois un peu plus serrée, pour pouvoir couper toutes les 2 s. Ajouter 2 ou 3 plans de 3 s sans personne (l'affiche en gros plan, la façade de l'agence, un fer à repasser) pour illustrer l'offre.
3. **Un son propre et un fichier propre.** Micro-cravate (ou téléphone à moins d'un mètre), aucune musique ni effet TikTok au tournage. La musique s'ajoute ensuite depuis la bibliothèque commerciale de la plateforme. Envoyer au monteur **le fichier vidéo d'origine** (pas un enregistrement d'écran), sans texte ni filtre incrusté.

---

## 7. Contrôle final (à faire sur le rendu)

Le verdict VALIDÉE ne pourra être donné qu'après visionnage du fichier rendu. Points à vérifier :
- **Offre lisible :** « 50 € OFFERTS* » est lisible à 2,5 s, son coupé, sur un téléphone.
- **Paillettes :** aucune trace du texte « paillettes » au-dessus du bandeau entre 6,2 et 8,4 s.
- **Zones sûres :** aucun texte au-delà de x 850 ni sous y 1440, rien sur le visage.
- **Mentions :** « *Voir conditions en agence » visible à chaque fois que l'offre est à l'écran, et « Crédit d'impôt selon conditions » près du -50 %.
- **Musique :** confirmer que la musique de la piste d'origine est un son commercial ou sous licence. Sinon, ne pas republier sur Instagram ou Snapchat avec cette piste.
- **Droit à l'image :** accord écrit de la conseillère pour son image, archivé.
- **Date de fin de l'offre :** à confirmer par Mièdaou. Si elle est connue, l'ajouter sur le carton (« Jusqu'au JJ/MM* »).
