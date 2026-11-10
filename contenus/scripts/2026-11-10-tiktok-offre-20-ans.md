# TikTok : offre 20 ans de Mièdaou (re-tournage + 3 déclinaisons)

Date : 10/11/2026 · Agence TikTok · Statut : à valider par Mièdaou, puis directeur artistique (feuille d'habillage) et monteur.

Source des faits : `marque/fiche-marque.md`, section « Offre en cours — 20 ans de Mièdaou ». Rien d'autre n'est affirmé.

**Faits utilisés, et seulement eux :**
- Mièdaou fête ses 20 ans.
- 50 € offerts pour tout contrat régulier de ménage et repassage. Mention : « voir conditions en agence ».
- Cumulable avec l'avance immédiate du crédit d'impôt (Urssaf) : -50 % sur la facture, tous les mois. Mention : « selon conditions ».
- Ménage à partir de 25 € TTC/h, soit environ 12,50 €/h après avantage fiscal (selon conditions et plafonds).
- Devis et visite d'évaluation gratuits. Site https://www.miedaou.fr, tél. 0262 30 36 37.

**À confirmer par Mièdaou avant publication :** date de fin de l'offre (aucune date n'est dite dans les scripts ; si elle est confirmée, l'ajouter au texte écran de la fin, c'est le meilleur levier d'urgence).

**Méthode et outils :** accroches tirées de `.claude/skills/ig-reel/hooks.json` (champs `template_fr` / `example_fr`), notées avec `hookscore.py` ; scripts minutés avec `beats.py` (165 mots/min) ; texte parlé et légendes passés dans `ig-human` (`humanize.py` : 0 artefact retiré ; `detect.py` : score humain 85,2/100, PASS). Seule modification proposée par `humanize.py` : supprimer l'espace avant « : » et « ? ». Refusée, c'est la typographie française.

---

## 1. Re-tournage : « Lâche ton balai » (offre 20 ans, face caméra)

- **Cible :** clients 25-60 ans (parents actifs, cadres débordés).
- **Objectif :** devis (et abonnés grâce à la série de la semaine).
- **Durée :** 20,4 s (beats.py, cible 20 s). 9:16, sous-titres mot par mot obligatoires.
- **Ce qui change par rapport à l'original (1 935 vues) :** l'offre est dite et écrite dès 0 s au lieu de 11 s ; texte à l'écran dès la première image ; une coupe ou un zoom toutes les 2 à 4 s au lieu d'un plan fixe de 10 s ; musique très basse sous la voix (ou aucune) pour que la voix et les sous-titres passent.

### Accroches (3 formules différentes, notées avec hookscore.py)

| # | Formule (hooks.json) | Phrase dite (0-2 s) | Texte écran (image 1) | Note | Durée dite |
|---|---|---|---|---|---|
| A | #2 Negative Command (« Arrête de… Fais… à la place ») | « Lâche ton balai : 50 € offerts, moitié prix. » | 50 € OFFERTS + -50 % | **84,4 STRONG** | 2,9 s |
| B | #1 Cost Confession (« 25 € de l'heure, c'est ce que tu crois payer… ») | « Tu paies 12,50 €, et 50 € offerts. » | 12,50 €/H AU LIEU DE 25 € + 50 € OFFERTS | **100 STRONG** | 2,9 s |
| C | #20 Permission (« Tu n'as pas besoin de… ») | « Ton ménage moitié prix, 50 € offerts : pas besoin d'attendre. » | -50 % + 50 € OFFERTS | **93,8 STRONG** | 3,6 s (offre dite à 2,2 s) |

**Choix pour le tournage : A.** C'est la seule des trois qui dit les deux offres en entier (« 50 € offerts » et « moitié prix ») en moins de 3 s, et elle crée la boucle de fin (« balai »). B a la meilleure note mais ne dit le -50 % qu'à travers 12,50 € : à tester en deuxième version, avec « à partir de 25 €/h, selon conditions » écrit à l'écran. C dépasse 3 s au total : à garder pour une variante Instagram.

Tourner les trois accroches à la suite (même décor, 1 prise chacune) pour pouvoir publier une variante plus tard sans re-tourner.

### Avantage en gros (avant 3 s)

Plein écran à 0,0 s, centré dans la zone sûre (entre y=230 et y=1440 sur 1080x1920, 230 px libres à droite) :

> **50 € OFFERTS**
> **+ PAYEZ -50 %**
> *selon conditions · voir conditions en agence*

### Script parlé (passé dans ig-human)

```
Lâche ton balai : 50 € offerts, moitié prix.
Mièdaou fête ses 20 ans.
50 € offerts sur un contrat régulier ménage et repassage.
Et l'avance immédiate : tu paies 50 % de ta facture.
Chaque mois, pas l'année d'après.
Les 2 se cumulent, voir conditions en agence.
Devis gratuit, lien en bio.
Le balai, on s'en occupe.
```

### Minutage (sortie beats.py, --target 20)

```
BEAT SHEET  ·  56 words  ·  ~20.4s at 165 wpm  ·  target 20.0s
  0:00.0   2.9s  HOOK    Lâche ton balai : 50 € offerts, moitié prix.
  0:02.9   1.8s          Mièdaou fête ses 20 ans.
  0:04.7   3.6s          50 € offerts sur un contrat régulier ménage et repassage.
  0:08.4   3.6s  MID     Et l'avance immédiate : tu paies 50 % de ta facture.
  0:12.0   1.8s          Chaque mois, pas l'année d'après.
  0:13.8   2.9s          Les 2 se cumulent, voir conditions en agence.
  0:16.7   1.8s          Devis gratuit, lien en bio.
  0:18.6   1.8s  CTA     Le balai, on s'en occupe.
  - Loops: the last beat repeats "balai" from the hook.
  - Length is on target (20.4s against 20.0s).
```

### Déroulé plan par plan

| Temps | Ce qu'on voit | Ce qu'on dit | Texte écran (séparé des sous-titres) |
|---|---|---|---|
| 0:00-0:03 | Gros plan taille. La conseillère tient un balai, le tend vers la caméra puis le lâche hors champ. Mouvement dès la première image, pas de coucou ni d'entrée dans le couloir. | « Lâche ton balai : 50 € offerts, moitié prix. » | **50 € OFFERTS + -50 %** (plein écran, dès l'image 1) · petit : *selon conditions* |
| 0:03-0:05 | Coupe, plan plus serré, sourire. Une petite affiche « 20 ans » dans le décor si elle existe. | « Mièdaou fête ses 20 ans. » | **MIÈDAOU A 20 ANS** |
| 0:05-0:08 | Coupe sur l'affiche bleue d'origine (`demo/video-offre-20-ans/affiche-offre.jpg`) avec zoom lent, voix par-dessus. | « 50 € offerts sur un contrat régulier ménage et repassage. » | **50 € OFFERTS** · contrat régulier ménage + repassage · *voir conditions en agence* |
| 0:08-0:12 | Retour face caméra, cadrage différent (de côté ou plus large). Elle compte sur ses doigts « moitié ». | « Et l'avance immédiate : tu paies 50 % de ta facture. » | **-50 % SUR TA FACTURE** · *avance immédiate Urssaf, selon conditions* |
| 0:12-0:14 | Zoom avant sur le visage. | « Chaque mois, pas l'année d'après. » | **CHAQUE MOIS** |
| 0:14-0:17 | Plan serré, elle joint les deux mains (geste « les deux ensemble »). | « Les 2 se cumulent, voir conditions en agence. » | **50 € + -50 % = CUMULABLES** · *voir conditions en agence* |
| 0:17-0:19 | Elle pointe vers le haut de l'écran (où sera le lien de la bio). | « Devis gratuit, lien en bio. » | **DEVIS GRATUIT · LIEN EN BIO** |
| 0:19-0:20 | Elle ramasse le balai, clin d'œil. Carton final. | « Le balai, on s'en occupe. » | Carton : **miedaou.fr · 0262 30 36 37** · *Offre 20 ans : voir conditions en agence. -50 % selon conditions.* |

**Raison de s'abonner :** la fin annonce la semaine (voir les 3 déclinaisons ci-dessous) ; ajouter un texte écran de 1 s avant le carton : « Cette semaine : tout sur l'offre 20 ans. Abonne-toi. »

### Légende TikTok

> Ménage à moitié prix + 50 € offerts pour les 20 ans de Mièdaou à La Réunion (selon conditions, voir conditions en agence). Tu savais que les deux se cumulent ? Devis gratuit, lien en bio.

- **Mot-clé recherché :** « ménage à moitié prix » ; secondaires : « aide ménagère La Réunion », « crédit d'impôt ménage ». Hashtags à finaliser par l'agent hashtags-seo.
- **Question :** « Tu savais que les deux se cumulent ? »
- **Appel au devis :** « Devis gratuit, lien en bio » (dit, écrit, et en légende) vers https://www.miedaou.fr.

### Liste de tournage (moins de 30 min, au téléphone)

- **Lieu :** le même couloir beige lumineux que l'original (bonne lumière).
- **Personne :** la même conseillère (accord écrit de droit à l'image déjà requis ; le vérifier).
- **Accessoires :** un balai ; l'affiche bleue de l'offre (fichier existant) ; une affiche « 20 ans » si elle existe ; téléphone en 9:16 sur trépied à hauteur des yeux ; micro-cravate ou téléphone proche de la bouche.
- **Son :** voix seule, pas de musique au tournage ; musique ajoutée au montage depuis la bibliothèque commerciale TikTok, très basse.
- **Plans :** 6 prises courtes (une par ligne) en changeant le cadrage entre chacune, plus les accroches B et C.
- **Temps estimé :** 20 min de tournage, 10 min de marge.

---

## 2. Déclinaison 1 : « Avant / Après 974 » (ménage + offre)

- **Cible :** clients 25-60 ans.
- **Objectif :** devis.
- **Durée :** 18,6 s (beats.py, cible 20 s). 9:16, sous-titres obligatoires.
- **Série :** « Avant / Après 974 », épisode 1.

### Accroche (notée)

| Formule (hooks.json) | Phrase dite (0-2 s) | Texte écran | Note | Durée dite |
|---|---|---|---|---|
| **#13 Before And After, On Screen (retenue)** | « Ton salon avant. Après. Tu paies moitié prix. » | AVANT → APRÈS · **-50 %** | **100 STRONG** | 2,9 s |
| #3 Nobody Tells You (variante) | « Personne te dit : ton ménage, moitié prix. » | TON MÉNAGE À MOITIÉ PRIX | 84,4 STRONG | 2,5 s |

### Avantage en gros (avant 3 s)

**TON MÉNAGE -50 %** · *selon conditions*, sur la coupe avant/après.

### Script parlé et minutage (beats.py, --target 20)

```
0:00.0  2.9s  HOOK  Ton salon avant. Après. Tu paies moitié prix.
0:02.9  2.5s        Avec l'avance immédiate, tu paies la moitié.
0:05.5  1.8s        Tout de suite, selon conditions.
0:07.3  2.9s  MID   Et pour nos 20 ans : 50 € offerts.
0:10.2  2.5s        Sur un contrat régulier ménage et repassage.
0:12.7  3.3s        Voir conditions en agence. Devis gratuit, lien en bio.
0:16.0  2.5s  CTA   Abonne-toi pour le prochain Avant Après 974.
Loop : « avant, après » repris de l'accroche. Longueur dans la cible.
```

### Déroulé plan par plan

| Temps | Ce qu'on voit | Texte écran |
|---|---|---|
| 0:00-0:03 | Plan fixe du salon « avant » (même angle), coupe nette sur le même angle « après ». | **AVANT** puis **APRÈS** · **-50 %** *selon conditions* |
| 0:03-0:07 | Gros plans satisfaisants en accéléré : surface essuyée, sol, coussins remis. Mains de l'intervenante uniquement. | **AVANCE IMMÉDIATE = TU PAIES LA MOITIÉ** · *selon conditions* |
| 0:07-0:13 | Plan large de la pièce finie, lent travelling. | **20 ANS : 50 € OFFERTS** · contrat régulier ménage + repassage · *voir conditions en agence* |
| 0:13-0:16 | Pile de linge repassé posée sur le canapé. | **DEVIS GRATUIT · LIEN EN BIO** |
| 0:16-0:19 | Retour sur le plan « avant » (boucle). | **AVANT / APRÈS 974 · ABONNE-TOI** · carton miedaou.fr · 0262 30 36 37 |

Voix off enregistrée au téléphone par la conseillère du re-tournage (continuité de visage et de voix sur la semaine).

### Légende TikTok

> Avant / après ménage à La Réunion, et tu paies la moitié avec l'avance immédiate (selon conditions). C'est quelle pièce chez toi qui mérite son avant / après ? Devis gratuit, lien en bio.

- **Mot-clé recherché :** « avant après ménage » ; secondaire : « ménage La Réunion ».
- **Question :** « C'est quelle pièce chez toi qui mérite son avant / après ? »
- **Appel au devis :** « Devis gratuit, lien en bio ».

### Liste de tournage

- **Lieu :** domicile d'un client réel en contrat ménage, **avec accord écrit** pour filmer le logement. Aucun objet personnel identifiable (photos de famille, courrier, adresse), aucun visage de client, aucun enfant.
- **Personne :** une intervenante (mains seulement, ou visage avec accord écrit).
- **Accessoires :** téléphone sur trépied fixé au même point pour l'avant et l'après (marquer la position au scotch), produits et chiffons habituels.
- **Règle de véracité :** vrai avant, vrai après, même pièce, même jour. Pas de mise en scène ni de retouche. Ne pas annoncer de durée d'intervention ; si on veut la dire, utiliser la durée réelle notée sur place ({{durée réelle}}).
- **Temps estimé :** 5 min de prise de vue au total (avant + après + 4 gros plans pendant l'intervention habituelle), 15 min de voix off et montage simple.

---

## 3. Déclinaison 2 : coulisses « L'équipe fête les 20 ans »

- **Cible :** 18-30 ans (notoriété, abonnés) et clients 25-60 ans.
- **Objectif :** abonnés (format coulisses, celui de la meilleure vidéo du compte : 37,8 K vues).
- **Durée :** 24,7 s (beats.py, cible 26 s). 9:16, sous-titres obligatoires.

### Accroche (notée)

| Formule (hooks.json) | Phrase dite (0-2 s) | Texte écran | Note | Durée dite |
|---|---|---|---|---|
| **#24 The Reveal (retenue)** | « Mièdaou a 20 ans. Toi, 50 € offerts. » | **MIÈDAOU A 20 ANS · 50 € OFFERTS** | **84,4 STRONG** | 2,9 s |
| #14 The Callout (variante) | « 20 ans à La Réunion : on t'offre 50 €. » | 20 ANS · 50 € POUR TOI | 84,4 STRONG | 3,3 s |

### Avantage en gros (avant 3 s)

**50 € OFFERTS** · *voir conditions en agence*

### Script parlé et minutage (beats.py, --target 26)

```
0:00.0  2.9s  HOOK  Mièdaou a 20 ans. Toi, 50 € offerts.
0:02.9  2.5s        Ici, c'est le bureau, à La Réunion.
0:05.5  2.5s        Mièdaou en 1 mot ? {{réponse réelle 1}}.
0:08.0  2.2s        {{réponse réelle 2}}. {{réponse réelle 3}}.
0:10.2  2.9s  MID   Le cadeau, c'est pour toi : 50 € offerts.
0:13.1  2.5s        Sur un contrat régulier ménage et repassage.
0:15.6  2.9s        Plus 50 % avec l'avance immédiate, selon conditions.
0:18.6  3.3s        Voir conditions en agence. Devis gratuit, lien en bio.
0:21.8  2.9s  CTA   Abonne-toi, on fête nos 20 ans avec toi.
Loop : « 20 ans » repris de l'accroche. Longueur dans la cible.
```

Les `{{réponse réelle}}` sont les vrais mots dits par les collègues au tournage : ne rien écrire à leur place, ne pas leur souffler de réponse.

### Déroulé plan par plan

| Temps | Ce qu'on voit | Texte écran |
|---|---|---|
| 0:00-0:03 | La conseillère entre dans le champ avec un carton « 20 ans » (ou un gâteau si l'équipe en a vraiment un ce jour-là), le montre à la caméra. | **MIÈDAOU A 20 ANS · 50 € OFFERTS** · *voir conditions en agence* |
| 0:03-0:05 | Plan rapide du bureau, l'équipe au travail. | **LE BUREAU MIÈDAOU** |
| 0:05-0:10 | Micro-trottoir de bureau : 3 collègues, 1 plan chacun (1-2 s), question écrite « Mièdaou en 1 mot ? ». | **MIÈDAOU EN 1 MOT ?** + le mot de chacun en gros |
| 0:10-0:16 | Retour sur la conseillère, elle pointe la caméra. | **50 € OFFERTS POUR TOI** · contrat régulier ménage + repassage |
| 0:16-0:19 | Même plan, zoom avant. | **+ -50 % AVANCE IMMÉDIATE** · *selon conditions* |
| 0:19-0:22 | Toute l'équipe fait coucou en même temps (le coucou de la vidéo d'origine, placé ici à la fin). | **DEVIS GRATUIT · LIEN EN BIO** · *voir conditions en agence* |
| 0:22-0:25 | Carton final. | **ABONNE-TOI · ON FÊTE NOS 20 ANS** · miedaou.fr · 0262 30 36 37 |

### Légende TikTok

> Mièdaou fête ses 20 ans à La Réunion : 50 € offerts sur un contrat régulier ménage et repassage (voir conditions en agence). Toi, tu dirais quoi en 1 mot ? Devis gratuit, lien en bio.

- **Mot-clé recherché :** « Mièdaou 20 ans » ; secondaires : « entreprise réunionnaise », « aide à domicile La Réunion ».
- **Question :** « Toi, tu dirais quoi en 1 mot ? » (les réponses donnent la matière à une réponse vidéo en fin de semaine).
- **Appel au devis :** « Devis gratuit, lien en bio ».

### Liste de tournage

- **Lieu :** le bureau Mièdaou.
- **Personnes :** la conseillère du re-tournage + 3 collègues volontaires, **accord écrit de droit à l'image** de chacun.
- **Accessoires :** carton « 20 ans » fait main ou imprimé ; gâteau seulement s'il existe vraiment ; téléphone 9:16.
- **Temps estimé :** 20 min (3 micro-réponses, 4 plans de la conseillère, 1 coucou collectif).

---

## 4. Déclinaison 3 : « Mièdaou i explik » : c'est quoi l'avance immédiate ?

- **Cible :** clients 25-60 ans.
- **Objectif :** devis (et abonnés via la série « Mièdaou i explik », épisode 1).
- **Durée :** 25,1 s (beats.py, cible 26 s). 9:16, sous-titres obligatoires.

### Accroche (notée)

| Formule (hooks.json) | Phrase dite (0-2 s) | Texte écran | Note | Durée dite |
|---|---|---|---|---|
| **#7 Wrong Way, Right Way (retenue)** | « Ton ménage plein tarif ? Pas avec l'avance immédiate. » | **PLEIN TARIF ? NON : -50 %** | **84,4 STRONG** | 2,9 s |
| #26 The Superlative (variante) | « Le plus simple pour ton ménage moitié prix : l'avance immédiate. » | MOITIÉ PRIX : L'AVANCE IMMÉDIATE | 53,4 OK | 3,6 s |

### Avantage en gros (avant 3 s)

**TU PAIES LA MOITIÉ, TOUT DE SUITE** · *selon conditions*

### Script parlé et minutage (beats.py, --target 26)

```
0:00.0  2.9s  HOOK  Ton ménage plein tarif ? Pas avec l'avance immédiate.
0:02.9  1.4s        « C'est quoi, l'avance immédiate ? »
0:04.4  3.3s        Le crédit d'impôt, d'habitude, tu le touches l'année d'après.
0:07.6  2.9s        Avec l'avance immédiate Urssaf, tu paies la moitié.
0:10.6  1.8s        Tout de suite, chaque mois.
0:12.4  2.5s  MID   Ménage à partir de 25 € l'heure ?
0:14.9  2.2s        Tu paies 12,50 €, selon conditions.
0:17.1  3.3s        Pour nos 20 ans : 50 € offerts en plus.
0:20.4  3.3s        Voir conditions en agence. Devis gratuit, lien en bio.
0:23.6  1.4s  CTA   Fini le plein tarif.
Loop : « plein tarif » repris de l'accroche. Longueur dans la cible.
```

La question « C'est quoi, l'avance immédiate ? » est présentée comme une question type, pas comme un commentaire reçu. Si un vrai commentaire pose cette question sous la vidéo 1, utiliser la fonction « répondre en vidéo » de TikTok avec ce commentaire à l'écran (c'est encore mieux).

### Déroulé plan par plan

| Temps | Ce qu'on voit | Texte écran |
|---|---|---|
| 0:00-0:03 | Conseillère face caméra, montre une facture vierge (modèle sans nom ni montant réel) et la déchire en deux. | **PLEIN TARIF ? NON : -50 %** · *selon conditions* |
| 0:03-0:04 | Elle se penche vers la caméra, air interrogatif. | **« C'EST QUOI L'AVANCE IMMÉDIATE ? »** |
| 0:04-0:08 | Calendrier ou téléphone montrant « l'année prochaine ». | **AVANT : REMBOURSÉ L'ANNÉE D'APRÈS** |
| 0:08-0:12 | Retour face caméra, cadrage serré. | **MAINTENANT : TU PAIES LA MOITIÉ TOUT DE SUITE** · *avance immédiate Urssaf* |
| 0:12-0:17 | Texte animé « 25 € → 12,50 € » (le 25 se barre). | **DÈS 25 €/H → ~12,50 €/H** · *selon conditions et plafonds* |
| 0:17-0:20 | Affiche bleue de l'offre, zoom. | **20 ANS : + 50 € OFFERTS** · contrat régulier ménage + repassage · *voir conditions en agence* |
| 0:20-0:25 | Conseillère pointe le lien, carton final. | **DEVIS GRATUIT · LIEN EN BIO** · **MIÈDAOU I EXPLIK · ABONNE-TOI** · miedaou.fr · 0262 30 36 37 |

### Légende TikTok

> C'est quoi l'avance immédiate du crédit d'impôt ? Ton ménage à moitié prix tout de suite, selon conditions. Quelle question on explique la prochaine fois ? Devis gratuit, lien en bio.

- **Mot-clé recherché :** « avance immédiate crédit d'impôt » ; secondaires : « crédit d'impôt ménage », « Urssaf avance immédiate ».
- **Question :** « Quelle question on explique la prochaine fois ? » (alimente les prochains épisodes de la série).
- **Appel au devis :** « Devis gratuit, lien en bio ».

### Liste de tournage

- **Lieu :** le couloir du re-tournage ou le bureau.
- **Personne :** la même conseillère.
- **Accessoires :** une feuille « facture » vierge (aucune donnée client réelle), un calendrier ou un téléphone, l'affiche bleue de l'offre (fichier existant).
- **Temps estimé :** 20 min.
- **Véracité :** ne jamais promettre un montant individuel ; « selon conditions » reste visible pendant tout le passage chiffré.

---

## Planning proposé de la semaine (à ajuster avec l'analyste)

Heures d'audience locale visées : midi ou 18 h-21 h, heure de La Réunion.

| Jour | Vidéo | Heure |
|---|---|---|
| Mar. 10/11 | 1. Re-tournage « Lâche ton balai » | 18 h 30 |
| Jeu. 12/11 | 3. Coulisses « L'équipe fête les 20 ans » | 12 h |
| Sam. 14/11 | 2. Avant / Après 974 | 12 h |
| Lun. 16/11 | 4. Mièdaou i explik : l'avance immédiate (en réponse vidéo si un vrai commentaire le demande) | 19 h |

Mesure du re-tournage : comparer ses vues à 48 h avec l'original (1 935) et la médiane du compte (environ 5 300), et regarder la courbe de rétention à 3 s. Si B est testée plus tard, ne changer que l'accroche pour que la comparaison tienne.

## Contrôles avant envoi au directeur artistique

- [x] Offre (50 € offerts + -50 %) dite et écrite avant 3 s dans le re-tournage.
- [x] « Voir conditions en agence » près de chaque mention des 50 € ; « selon conditions » près de chaque -50 % / 12,50 €.
- [x] Aucun chiffre, témoignage ni date inventés (réponses des collègues et durée d'intervention laissées en `{{...}}`).
- [x] Chaque vidéo se termine par « Devis gratuit, lien en bio ».
- [ ] Accords écrits de droit à l'image : conseillère, collègues, intervenante, client (logement).
- [ ] Date de fin de l'offre confirmée par Mièdaou.
- [ ] Étiquette « contenu généré par IA » : sans objet (aucune image ni voix générée).
