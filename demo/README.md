# Démonstration — ce que l'équipe d'agents a fait avec ta vidéo et ton compte TikTok

Date : 10/11/2026. Point de départ : l'enregistrement d'écran de la vidéo « offre anniversaire 20 ans » (1 935 vues) et la capture du profil @miedaou.

Rien n'a été publié. Tout est à valider par Mièdaou.

## 1. La vidéo refaite (sans nouveau tournage)
| Fichier | Contenu |
|---|---|
| `video-offre-20-ans/rendu/offre-20-ans-habillee.mp4` | La vidéo habillée : 15,6 s, 1080 x 1920, 12 Mb/s |
| `video-offre-20-ans/rendu/avant-apres.jpg` | Comparaison image par image avant / après |
| `video-offre-20-ans/rendu/miniature.jpg` | Miniature « 50 € OFFERTS* / SUR VOTRE MÉNAGE » |
| `video-offre-20-ans/feuille-habillage.md` | Le plan du directeur artistique, seconde par seconde, avec son diagnostic (3/10 pour l'original) |
| `video-offre-20-ans/habillage.json` | La feuille traduite pour l'outil de montage, avec les écarts assumés |
| `video-offre-20-ans/controle-qualite.md` | Le contrôle qualité du directeur artistique (6/10, À CORRIGER) et les 9 corrections appliquées depuis |

Ce qui change :
- **L'offre est visible dès la 1re seconde** (affiche en ouverture), puis en bandeaux « 50 € OFFERTS* » et « + PAYEZ -50 %* », au lieu de 11 s.
- **Sous-titres mot par mot**, mot prononcé en orange, pour ceux qui regardent sans le son.
- **Zooms et recadrages** toutes les 1 à 2 s, centrés sur le visage.
- **Textes d'origine illisibles masqués** par des bandeaux aux couleurs Mièdaou.
- **Carton final** : DEVIS GRATUIT, lien en bio, 0262 30 36 37, miedaou.fr, toute La Réunion.
- **Mentions** « *Voir conditions en agence » et « Crédit d'impôt selon conditions » à chaque apparition de l'offre.
- **Son** normalisé (-14 LUFS).

## 2. Les autres livrables des agents
| Agent | Fichier | En bref |
|---|---|---|
| Stratège contenu | `../contenus/strategie/2026-11-10.md` | La vidéo coulisses fait 7,1 fois la médiane du compte, l'offre 20 ans 0,37 fois. Formats gagnants, hashtags, style de montage, 5 idées de vidéos avec accroche notée. Confiance faible : un seul compte analysé. |
| Bios et profils | `audit-profil-tiktok.md` et `../contenus/bios.md` | Profil TikTok noté 28/100, 74/100 après corrections. Nouvelles bios (version offre 20 ans et version permanente), vidéos à épingler. |
| Agence TikTok | `../contenus/scripts/2026-11-10-tiktok-offre-20-ans.md` | Script de la vidéo à re-tourner (offre dite en moins de 3 s) et 3 déclinaisons : avant/après, coulisses des 20 ans, « c'est quoi l'avance immédiate ? ». |
| Conversion devis | `../contenus/scripts/2026-11-10-conversion-offre-20-ans.md` | Appel à l'action « Écris DEVIS », 12 réponses types, parcours en message privé, hashtags. |

## 3. Légende et hashtags proposés pour publier la vidéo refaite
> Mièdaou fête ses 20 ans à La Réunion : 50 € offerts sur un contrat régulier ménage et repassage (voir conditions en agence). Toi, tu dirais quoi en 1 mot ? Devis gratuit, lien en bio.

`#974 #lareunion #menageadomicile #creditdimpot #bonplan974 #miedaou`

## 4. Claude Design et Claude Motion
| Artefact | Lien |
|---|---|
| Système de design Mièdaou (couleurs, polices, zones sûres, logo) | https://claude.ai/artifact/GSguYQPSVk5mj48M2zgyPp |
| Film Claude Motion « Offre 20 ans » (15 s, vertical, musique originale, export MP4 depuis la page) | https://claude.ai/artifact/KvXpHFrgVp6NciYU5WnD2z |

Ces pages sont privées : partage-les depuis leur menu Partager si quelqu'un d'autre doit les voir.

## 5. L'automatisation
Pour toute nouvelle vidéo : `/traiter-video chemin/de/la/video.mp4` dans Claude Code. La chaîne :
1. préparation automatique (images, son, transcription française) ;
2. stratège, directeur artistique, agence TikTok et conversion en parallèle ;
3. montage automatique avec `outils/habiller_video.py` ;
4. miniature ;
5. contrôle qualité ;
6. rapport.

Détails techniques : `../outils/README.md`.

## 6. À faire par Mièdaou
- **Valider la vidéo**, puis la publier (ou la republier) avec la légende ci-dessus.
- **Accord écrit de la conseillère** pour son image.
- **Licence de la musique d'origine** : à vérifier, ou remplacer par un son de la bibliothèque commerciale TikTok au moment de publier.
- **Date de fin de l'offre** des 20 ans.
- **Logo officiel en PNG** pour le carton final.
- **Fichier vidéo d'origine** (pas un enregistrement d'écran) pour les prochaines vidéos.
- **Bios** : mettre les nouvelles en ligne, passer TikTok en compte professionnel, épingler les 3 vidéos conseillées.
