# Design system

Direction : minimaliste, apaisante, premium, humaine. Le vert sauge est la couleur centrale, sur fond crème. Beaucoup d'espace, peu d'éléments, aucune couleur agressive.

## Couleurs (`mobile/src/theme/index.ts`)

| Rôle | Clair | Usage |
|---|---|---|
| Fond | `#F6F3EC` crème | toutes les pages |
| Surface | `#FCFBF8` blanc doux | cartes, champs, zone de saisie |
| Surface secondaire | `#E7EDE4` sauge clair | bulles de la personne, puces sélectionnées |
| Sauge | `#A8B9A1` | icônes, indicateurs, accents |
| Texte / bouton principal | `#30483C` vert forêt | titres, texte, bouton principal |
| Texte discret | `#8C918B` gris doux | légendes |
| Accent | `#C6A77B` | réservé, à utiliser avec parcimonie |
| Attention | `#9A6A4F` brun terre | erreurs et actions destructrices (pas de rouge) |

Un thème sombre reprend les mêmes rôles. Les écrans n'utilisent jamais de couleur en dur : toujours `useColors()`.

## Typographie
- **Fraunces demi-gras** (serif) pour les titres : chaleureuse et affirmée.
- **Figtree** pour le texte : ronde, très lisible.
- Échelle : `display` 32 · `title` 26 · `heading` 20 · `body` 16,5 · `small` 14,5 · `caption` 13.
- Les textes secondaires sont en vert forêt adouci, jamais en gris pâle.

## Espaces et formes
- Espaces : 4 · 8 · 12 · 16 · 24 · 32 · 48. Marges de page : 24.
- Rayons : 10 · 18 · 24 · 30 · pilule. Cartes et puces pleines, sans contour. Une seule ombre, très légère, pour ce qui flotte.
- Zones tactiles : 44 pt minimum ; bouton principal 54 pt.
- Largeur maximale du contenu : 560 pt (tablettes et web).

## Composants (`mobile/src/ui`)
`Screen`, `Header`, `Txt`, `Button` (principal, doux, contour, discret), `IconButton`, `Chip`, `Card`, `Row`, `Toggle`, `Field`, `Scale`, `SectionTitle`, `Empty`, `Divider`, `Icon` (jeu d'icônes maison au trait fin), `Botanical` (illustration d'accueil), `Sheet`.

## Mouvement
Apparitions en fondu de 300 à 500 ms, jamais de rebond ni d'effet rapide. Le cercle du mode vocal et des exercices de respiration bouge lentement.

## Ton des textes
Tutoiement, phrases courtes, chaleureux sans être mielleux. Pas d'emoji. On dit ce que fait l'app et ce qu'elle ne fait pas.

## Accessibilité
Chaque élément tactile a un rôle et un libellé ; les états (sélectionné, désactivé) sont annoncés ; le texte forêt sur crème dépasse le contraste AA ; les erreurs sont annoncées aux lecteurs d'écran.

## Images
Les visuels sont dessinés en vectoriel dans la palette (pas de photo lourde à charger). Une piste d'illustration a été générée avec Canva comme référence d'ambiance. Les connecteurs d'images photo (CoDesign, Higgsfield) demandent une connexion du propriétaire et n'ont pas pu être utilisés.
