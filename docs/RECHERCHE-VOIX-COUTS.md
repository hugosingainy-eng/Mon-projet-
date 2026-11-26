# Confie — Recherche : voix, coûts, freemium, réglementation

*Recherche faite le 26 novembre 2026. Chaque prix renvoie à sa page officielle. « Non vérifié » = je n'ai pas pu lire le chiffre sur une page officielle ; à contrôler avant toute décision.*
*Taux de change utilisé : 1 € = 1,0935 $ (taux de référence BCE du 25/11/2026), soit 1 $ ≈ 0,9145 € — [source BCE](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html).*

## En bref

- **Lancement :** garder la voix du téléphone (gratuite, déjà en place). Coût voix : 0 €.
- **Offre premium « voix avancée » :** écoute par Deepgram (serveur européen) → Claude reste le « cerveau » → voix ElevenLabs Flash (ou Cartesia). Environ **0,22 $ par conversation vocale de 10 minutes**, à plafonner (ex. 150 min/mois).
- **Coût du texte, utilisateur régulier (30 conversations/mois) :** ≈ **0,15 $** avec Haiku 5.5, ≈ **2,92 $** avec Sonnet 5.5, ≈ **5,84 $** avec Opus 5.5.
- **Prix conseillé :** 9,99 €/mois ou 79,99 €/an. Rentable pour un utilisateur régulier ; **déficitaire pour un très gros utilisateur** sans garde-fous (voir §4).
- **Règle absolue :** aucun écran de paiement en moment de détresse ; les ressources de crise (3114, 15, 112) sont toujours gratuites.

---

## 1. Options de voix

### 1.1 Tableau comparatif

Latences : ce sont des **annonces des fournisseurs**, pas des mesures indépendantes. Qualité du français : je n'ai trouvé **aucun comparatif indépendant fiable** ; seul un test d'écoute avec de vrais utilisateurs francophones tranchera.

| Option | Prix actuel | Latence annoncée | Français | Interruption (« barge-in ») | Flux continu | Vie privée | Expo / React Native |
|---|---|---|---|---|---|---|---|
| **(a) Voix du téléphone** — `expo-speech-recognition` + `expo-speech` | Gratuit | Non vérifié (dépend du téléphone) | Voix système, assez robotique ; dépend de l'appareil | À coder soi-même : `Speech.stop()` coupe la voix | Résultats partiels oui | Par défaut l'audio part chez Apple / Google. Mode « sur l'appareil » possible (iOS 17+, Android 13+, modèle de langue à télécharger sur Android) | `expo-speech` marche dans Expo Go ; la reconnaissance exige un « development build ». Mode continu absent sur Android 12 et antérieurs |
| **(b) Deepgram Nova-3** (écoute) | 0,0048 $/min (une langue) ou 0,0058 $/min (multilingue) en direct, tarif promotionnel ; 200 $ de crédit offert | < 300 ms | `fr` et `fr-CA` pris en charge | Détection de fin de parole fournie (modèle Flux multilingue : 0,0078 $/min, français inclus) | Oui | Serveur UE `api.eu.deepgram.com` ouvert à tous ; « zéro conservation » possible sur option ; « prêt pour le RGPD ». Durée de conservation par défaut et contrat DPA : non vérifiés | Connexion WebSocket depuis l'app ou le serveur ; pas de module officiel Expo vérifié |
| **(b) OpenAI transcription** | `gpt-4o-mini-transcribe` 0,003 $/min ; `gpt-4o-transcribe` 0,006 $/min ; `gpt-transcribe` 0,0045 $/min | Non vérifié | Non vérifié | Non (sauf via l'API Realtime) | Selon modèle | Pas d'entraînement sur les données API ; conservation 30 jours max par défaut (aucune pour la transcription) ; résidence UE **sur demande commerciale**, +10 % sur les modèles récents | Simple appel HTTP depuis le serveur Node |
| **(b) ElevenLabs Scribe** | 0,20 $/h (différé), 0,22 $/h (temps réel) | ≈ 150 ms (Scribe v2 Realtime) | « 90+ langues » ; français non listé sur la page lue | Non (transcription seule) | Oui (versions Live / Realtime) | Résidence UE et « zéro conservation » réservées aux clients **Enterprise** | HTTP / WebSocket |
| **(b) AssemblyAI** | 0,15 $/h (différé), 0,30 $/h (temps réel, facturé à la durée de connexion) ; 50 $ offerts | Non vérifié | Français en direct : non confirmé | Non vérifié | Oui | Non vérifié | HTTP / WebSocket |
| **(b) Google Cloud STT** | ≈ 0,016 $/min, 60 min gratuites/mois — **non vérifié** (page officielle illisible par mon outil) | Non vérifié | Non vérifié | Non | Oui | Régions UE disponibles (détail non vérifié) | HTTP / gRPC côté serveur |
| **(c) ElevenLabs** (voix) | Flash : 0,04 $ / 1 000 caractères ; Multilingual v2 et v3 : 0,08 $ ; abonnements 6 $ → 990 $/mois | Flash v2.5 ≈ 100 ms ; v3 Conversational ≈ 165 ms | Français listé sur tous les modèles ; réputées les voix les plus naturelles (affirmation fournisseur) | Il suffit d'arrêter la lecture | Oui (WebSocket) | Idem Scribe : UE et zéro conservation = Enterprise | SDK React Native officiel (pour les agents) ; sinon HTTP |
| **(c) Cartesia Sonic 3.6** | 1 crédit par caractère ; Pro 5 $/mois (100 000 crédits), Startup 49 $/mois (1,25 M) → ≈ 0,04 $ / 1 000 caractères | Non indiquée sur la page lue | Français listé (44 langues) | Arrêter la lecture | Non vérifié sur la page lue | Non vérifié | HTTP / WebSocket |
| **(c) Deepgram Aura-2** | 0,030 $ / 1 000 caractères | ≈ 90 ms (annonce) | **Seulement 2 voix françaises** (Agathe, Hector) | Arrêter la lecture | Oui | Comme Deepgram ci-dessus (couverture du serveur UE pour la voix : non vérifiée) | HTTP / WebSocket |
| **(c) OpenAI TTS** | `tts-1` 15 $ / million de caractères ; `tts-1-hd` 30 $ ; `gpt-4o-mini-tts` 12 $ / million de jetons audio (prix à la minute : non vérifié) | Non vérifié | Non vérifié | Arrêter la lecture | Oui | Comme OpenAI ci-dessus | HTTP |
| **(c) Google Cloud TTS** | ≈ 30 $ / million de caractères (Chirp 3 HD), ≈ 16 $ (Neural2) — **non vérifié** | Non vérifié | Non vérifié | Arrêter la lecture | Oui | Régions UE (non vérifié) | HTTP |
| **(c) Azure Speech** | **Non vérifié** (la page affiche « $- ») ; gratuit : 0,5 million de caractères et 5 h d'écoute par mois | Non vérifié | Non vérifié | Arrêter la lecture | Oui | Régions UE (non vérifié) | SDK natif, pas de module Expo officiel vérifié |
| **(d) ElevenLabs Agents** (« ElevenAgents ») | **0,08 $/min** au-delà du quota inclus (15 min gratuites ; 75 à 12 375 min selon l'abonnement) ; **le modèle de langage est facturé en plus** | « Faible latence », pas de chiffre | 31 langues pour les agents ; français non nommé sur la page lue | Oui, intégré (modèle de tour de parole maison) | Oui | UE et zéro conservation = Enterprise | **SDK officiel Expo/React Native** (`@elevenlabs/react-native`), « development build » obligatoire (pas Expo Go), RN 0.79+ ; on peut brancher son propre modèle |
| **(d) OpenAI Realtime** | `gpt-realtime-2.1` : audio 32 $ entrée / 64 $ sortie par million de jetons ; version mini : 10 $ / 20 $ ; `gpt-live-1.1` : 0,05 $/min actif, 0,02 $/min en veille. Coût par minute des modèles « realtime » : non vérifié | Non chiffrée | Non vérifié | Oui, automatique (coupe la réponse et la tronque) | Oui (WebRTC) | Comme OpenAI ; traçage non conforme à la résidence UE | Pas de SDK Expo officiel ; via `react-native-webrtc` (development build). **Le cerveau serait un modèle OpenAI, pas Claude** : le prompt de sécurité de Confie devrait être refait et retesté |
| **(d) LiveKit Agents** | Gratuit : 1 000 min d'agent/mois ; Ship dès 50 $/mois (5 000 min, puis 0,01 $/min) ; écoute, voix et modèle en plus | Dépend des briques choisies | Dépend des briques | Oui, intégré (détection de tour de parole) | Oui (WebRTC) | Logiciel libre, auto-hébergeable ; blocage de région seulement à partir de l'offre Scale (500 $/mois) | SDK React Native + plugin Expo (development build). Plugin Anthropic : non vérifié sur la page lue |
| **(d) Pipecat / Daily** | Pipecat est libre ; Pipecat Cloud : 0,01 $/min d'agent actif, transport voix 1:1 gratuit ; briques en plus | Dépend des briques | Dépend des briques | Oui (cadre conçu pour ça) | Oui | Auto-hébergeable ; région UE de Pipecat Cloud : non vérifiée | Client React Native : non vérifié |

Sources : [expo-speech](https://docs.expo.dev/versions/latest/sdk/speech/) · [expo-speech-recognition](https://github.com/jamsch/expo-speech-recognition) · [Deepgram prix](https://deepgram.com/pricing) · [Deepgram langues](https://developers.deepgram.com/docs/models-languages-overview) · [Deepgram voix](https://developers.deepgram.com/docs/tts-models) · [Deepgram serveur UE](https://developers.deepgram.com/reference/regional-endpoints) · [Deepgram conformité](https://developers.deepgram.com/docs/data-privacy-compliance) · [OpenAI prix](https://developers.openai.com/api/docs/pricing) · [OpenAI données](https://developers.openai.com/api/docs/guides/your-data) · [OpenAI résidence](https://developers.openai.com/api/docs/guides/data-residency) · [OpenAI interruptions](https://developers.openai.com/api/docs/guides/realtime-conversations) · [ElevenLabs prix API](https://elevenlabs.io/pricing/api) · [ElevenLabs prix agents](https://elevenlabs.io/pricing/agents) · [ElevenLabs modèles](https://elevenlabs.io/docs/overview/models) · [ElevenLabs agents](https://elevenlabs.io/docs/eleven-agents/overview) · [ElevenLabs Expo](https://elevenlabs.io/docs/eleven-agents/guides/integrations/expo-react-native) · [ElevenLabs résidence](https://elevenlabs.io/docs/overview/administration/data-residency) · [ElevenLabs zéro conservation](https://elevenlabs.io/docs/eleven-api/resources/zero-retention-mode) · [AssemblyAI](https://www.assemblyai.com/pricing) · [Cartesia prix](https://cartesia.ai/pricing) · [Cartesia Sonic](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest) · [Google STT](https://cloud.google.com/speech-to-text/pricing) · [Google TTS](https://cloud.google.com/text-to-speech/pricing) · [Azure Speech](https://azure.microsoft.com/en-us/pricing/details/speech/) · [LiveKit prix](https://livekit.com/pricing) · [LiveKit Agents](https://docs.livekit.io/agents/) · [Pipecat Cloud](https://www.daily.co/pricing/pipecat-cloud/)

### 1.2 Recommandation

**(i) Lancement — rester sur la voix du téléphone.**
Gratuit, déjà codé, aucun nouveau sous-traitant pour des données sensibles. Deux améliorations sans coût : activer le mode « reconnaissance sur l'appareil » quand le téléphone le permet (l'audio ne quitte alors pas le téléphone), et couper la voix dès que l'utilisateur reprend la parole.

**(ii) Premium « voix avancée » — une chaîne en trois briques, Claude au milieu.**
1. Écoute : **Deepgram Nova-3** en direct, via le serveur européen.
2. Réflexion : **Claude**, inchangé (même prompt, mêmes garde-fous de sécurité — c'est l'argument décisif contre les solutions « tout-en-un » qui imposent leur propre modèle).
3. Voix : **ElevenLabs Flash v2.5** (ou **Cartesia Sonic**, même ordre de prix ; **Deepgram Aura-2** est 25 % moins cher mais n'a que deux voix françaises).

Coût : ≈ 0,22 $ par conversation vocale de 10 min (calcul au §2.3).
Raccourci possible pour un prototype : **ElevenLabs Agents** avec Claude branché dessus — SDK Expo officiel, interruptions gérées — mais ≈ 0,80 $ par conversation de 10 min, plus Claude, et résidence UE réservée à l'offre Enterprise.

**Point bloquant à lever avant de signer :** ElevenLabs n'offre la résidence UE et la non-conservation qu'en Enterprise. Pour une app de soutien émotionnel, à faire valider par l'avocat ; sinon choisir une voix hébergée en UE (Deepgram Aura-2, Google ou Azure en région européenne).

### 1.3 Ce qui reste non vérifié (voix)

- Qualité réelle du français de chaque fournisseur (aucune source indépendante trouvée) et toutes les latences (annonces commerciales).
- Prix Azure Speech ; prix Google STT/TTS sur la page en direct ; coût à la minute d'OpenAI Realtime et de `gpt-4o-mini-tts`.
- Compatibilité exacte de chaque bibliothèque avec **Expo SDK 58** (seule l'exigence RN 0.79+ d'ElevenLabs est confirmée).
- Durée de conservation par défaut et DPA chez Deepgram ; couverture de la voix (Aura-2) par son serveur UE ; politique de données de Cartesia et d'AssemblyAI.
- Plugin Anthropic de LiveKit, client React Native de Pipecat, région UE de Pipecat Cloud.
- Facturation des silences chez ElevenLabs Agents ; correspondance exacte abonnement ↔ minutes incluses.

---

## 2. Coût par utilisateur

### 2.1 Une conversation de 20 échanges (texte)

Hypothèses données : prompt système 2 500 jetons, message utilisateur 40, réponse 120, historique renvoyé à chaque tour (plafond de 40 messages, jamais atteint en 20 échanges).

- Entrée au tour *n* = 2 500 + 160 × (n − 1) + 40.
- Somme sur 20 tours = 20 × 2 540 + 160 × 190 = **81 200 jetons en entrée**, dont 50 000 de prompt système répété et 31 200 de messages.
- Sortie = 20 × 120 = **2 400 jetons**.

Prix du cache ([page officielle Anthropic](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)) : écriture = 1,25 × le prix d'entrée ; lecture = 0,20 $ (Opus 5.5), 0,10 $ (Sonnet 5.5), 0,01 $ (Haiku 5.5) par million. Le cache expire après 5 minutes sans message ; minimum 512 jetons pour ces trois modèles, donc le prompt de 2 500 jetons est bien « cachable ».

| | Opus 5.5 (4 $ / 20 $) | Sonnet 5.5 (2 $ / 10 $) | Haiku 5.5 (0,10 $ / 0,50 $) |
|---|---|---|---|
| **A. Sans cache** : 81 200 × entrée + 2 400 × sortie | 0,3248 + 0,048 = **0,373 $** | 0,1624 + 0,024 = **0,186 $** | 0,00812 + 0,0012 = **0,0093 $** |
| **B. Prompt système en cache** : 1 écriture de 2 500 + 19 lectures (47 500) + 31 200 au plein tarif + sortie | 0,0125 + 0,0095 + 0,1248 + 0,048 = **0,195 $** | 0,00625 + 0,00475 + 0,0624 + 0,024 = **0,097 $** | 0,00031 + 0,00048 + 0,00312 + 0,0012 = **0,0051 $** |
| **C. Cache aussi sur l'historique** : 5 580 jetons écrits, 75 620 lus, + sortie | 0,0279 + 0,0151 + 0,048 = **0,091 $** | 0,0140 + 0,0076 + 0,024 = **0,046 $** | 0,0007 + 0,0008 + 0,0012 = **0,0027 $** |

Le scénario **B** sert de référence ci-dessous (prudent et simple à mettre en place). **A** est le pire cas : si la personne met plus de 5 minutes entre deux messages — fréquent dans une conversation émotionnelle — le cache est perdu pour ce tour. **C** est la cible technique : il divise encore la facture par deux.

### 2.2 Coût mensuel, texte seul

| Utilisateur | Conversations/mois | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|---|
| Léger | 8 | 1,56 $ | 0,78 $ | 0,04 $ |
| Régulier | 30 | **5,84 $** | **2,92 $** | **0,15 $** |
| Intensif | 100 | 19,48 $ | 9,74 $ | 0,51 $ |

(Scénario B. Sans aucun cache : multiplier par ≈ 1,9. Avec cache complet : diviser par ≈ 2,1.)

### 2.3 Supplément voix (par conversation vocale de 10 minutes)

Hypothèse : l'écoute reste ouverte 10 minutes ; l'assistant parle environ 5 minutes, soit ≈ 4 000 caractères (Cartesia indique 750–800 caractères par minute). Si l'assistant parle davantage, la ligne « voix » augmente en proportion.

| Chaîne | Écoute | Voix | Total par conversation |
|---|---|---|---|
| **Recommandée** : Deepgram Nova-3 multilingue + ElevenLabs Flash | 10 × 0,0058 = 0,058 $ | 4 × 0,04 = 0,16 $ | **≈ 0,22 $** |
| Tout Deepgram (Nova-3 + Aura-2) | 0,058 $ | 4 × 0,03 = 0,12 $ | ≈ 0,18 $ |
| Deepgram + Cartesia (offre Startup) | 0,058 $ | 4 000 crédits ≈ 0,16 $ | ≈ 0,22 $ |
| ElevenLabs Agents (tout-en-un) | — | — | 10 × 0,08 = **0,80 $** + modèle |
| Voix du téléphone | 0 | 0 | 0 $ |

Supplément mensuel si **toutes** les conversations sont vocales (chaîne recommandée) : léger 8 × 0,218 = **1,74 $** ; régulier 30 × 0,218 = **6,54 $** ; intensif 100 × 0,218 = **21,80 $**. La voix coûte donc plus cher que le texte Sonnet : il faut la plafonner.

---

## 3. Autres coûts réels

| Poste | Chiffres officiels | Source |
|---|---|---|
| **Supabase Gratuit** | 0 $ ; 50 000 utilisateurs actifs/mois ; base 500 Mo ; 5 Go de trafic sortant ; 1 Go de fichiers ; 2 projets actifs ; **mise en pause après 1 semaine d'inactivité** ; pas de sauvegardes | [supabase.com/pricing](https://supabase.com/pricing) |
| **Supabase Pro** | 25 $/mois ; 100 000 utilisateurs actifs (puis 0,00325 $ chacun) ; 8 Go de disque (puis 0,125 $/Go) ; 250 Go de trafic (puis 0,09 $/Go) ; 100 Go de fichiers ; sauvegardes quotidiennes 7 jours ; 10 $ de crédit de calcul ; plafond de dépense activé par défaut. Régions UE : Paris, Francfort, Irlande, Stockholm | [prix](https://supabase.com/pricing) · [régions](https://supabase.com/docs/guides/platform/regions) |
| **YouTube Data API v3** | Un appel `search.list` coûte **1 unité** dans un compteur à part, limité à **100 appels par jour** par défaut → **100 recherches gratuites par jour**. Les autres appels partagent 10 000 unités/jour. (L'ancienne règle « 100 unités par recherche » n'est plus celle affichée.) | [developers.google.com](https://developers.google.com/youtube/v3/determine_quota_cost) |
| **Apple Developer Program** | 99 $ par an (ou équivalent en monnaie locale ; montant en euros non vérifié) | [developer.apple.com](https://developer.apple.com/programs/whats-included/) |
| **Google Play Console** | 25 $ une seule fois. Compte personnel : test fermé obligatoire avec **12 testeurs pendant 14 jours** avant publication | [frais](https://support.google.com/googleplay/android-developer/answer/6112435?hl=en) · [test](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en) |
| **Commission Apple (UE, depuis le 1er oct. 2026)** | Achat intégré : **26 %** en standard ; **15 %** pour les membres du Small Business Program (moins de 1 million $ de revenus l'année précédente, ou nouveau développeur) et pour les abonnements après leur première année | [UE](https://developer.apple.com/support/dma-and-apps-in-the-eu/) · [Small Business Program](https://developer.apple.com/app-store/small-business-program/) |
| **Commission Apple (hors UE)** | Abonnements : 30 % la première année, 15 % ensuite ; 15 % dès le départ avec le Small Business Program | [developer.apple.com](https://developer.apple.com/app-store/subscriptions/) |
| **Commission Google Play (EEE)** | Abonnements : **10 % + 5 % de frais de facturation Google = 15 %**. Autres achats : 20 à 25 % + 5 %. Hors zones mises à jour : 15 % sur le premier million $, 15 % sur les abonnements | [support.google.com](https://support.google.com/googleplay/android-developer/answer/112622?hl=en) |
| **Expo EAS Build** | Gratuit : jusqu'à 15 builds Android + 15 iOS par mois, file lente, 45 min max, 1 000 utilisateurs pour les mises à jour. Starter : 19 $/mois + usage (45 $ de crédit) ; build Android 1–2 $, iOS 2–4 $ | [expo.dev/pricing](https://expo.dev/pricing) |
| **Serveur Node — Railway** | Hobby 5 $/mois, 5 $ d'usage inclus ; région UE Amsterdam | [prix](https://railway.com/pricing) · [régions](https://docs.railway.com/reference/regions) |
| **Serveur Node — Render** | Gratuit : 512 Mo, s'endort après 15 min sans trafic et met ≈ 1 minute à se réveiller (**à éviter** pour une app de soutien). Payant dès 7 $/mois (512 Mo). Région UE : non vérifiée | [prix](https://render.com/pricing) · [offre gratuite](https://render.com/docs/free) |

**Frais fixes minimum en production :** Supabase Pro 25 $ + serveur 5–7 $ ≈ **30–32 $/mois**, plus 99 $/an Apple et 25 $ une fois Google.

---

## 4. Proposition freemium

> **Règle non négociable.** Aucun écran de paiement, aucune limite, aucune incitation à s'abonner ne doit apparaître quand une personne est en détresse. Si un signal de crise est détecté, toutes les limites sautent pour la conversation en cours. Les ressources de crise (3114, 15, 112) sont **toujours gratuites, visibles et accessibles sans compte**. La détection de crise doit avoir la même qualité en gratuit et en premium.

**Gratuit**
- Conversations texte, sur Haiku 5.5 (≈ 0,15 $/mois pour un utilisateur régulier), avec une limite quotidienne douce.
- Voix du téléphone (coût nul).
- Ressources de crise, exercices de base.
- À tester avant de décider : que Haiku tienne le ton et les garde-fous de sécurité attendus. Sinon, passer le gratuit sur Sonnet avec une limite plus basse.

**Premium**
- Modèle Sonnet 5.5 (réponses plus fines), mémoire et historique étendus.
- « Voix avancée » : 150 minutes par mois incluses (15 conversations de 10 min).
- Opus 5.5 est trop cher pour un usage illimité à ce prix.

**Prix suggéré : 9,99 €/mois ou 79,99 €/an** (≈ 6,67 €/mois, 33 % de remise).

### Calcul de marge

- Hypothèse : TVA française de 20 % incluse dans le prix, commission de 15 % (Apple Small Business Program, ou Google Play abonnements EEE) calculée sur le hors-taxe. Base de calcul exacte de la commission : à confirmer avec le comptable.
- Mensuel : 9,99 ÷ 1,20 = 8,33 € HT ; × 0,85 = **7,08 € nets par mois**.
- Annuel : 79,99 ÷ 1,20 = 66,66 € HT ; × 0,85 = 56,66 € ; ÷ 12 = **4,72 € nets par mois**.
- Coûts convertis à 1 $ = 0,9145 €. Voix : 0,218 $ = 0,20 € par conversation.

| Utilisateur premium | Texte Sonnet | Voix | Coût total | Marge (mensuel) | Marge (annuel) |
|---|---|---|---|---|---|
| **Régulier** — 30 conv., dont 10 vocales, cache B | 2,92 $ = 2,67 € | 10 × 0,20 = 1,99 € | 4,66 € | **+2,42 €** | **+0,06 €** |
| Régulier, cache complet C | 1,37 $ = 1,25 € | 1,99 € | 3,24 € | **+3,84 €** | **+1,48 €** |
| **Intensif** — 100 conv., voix au plafond (15), cache B | 9,74 $ = 8,91 € | 15 × 0,20 = 2,99 € | 11,90 € | **−4,82 €** | **−7,18 €** |
| Intensif, cache complet C | 4,55 $ = 4,16 € | 2,99 € | 7,15 € | **−0,07 €** | **−2,43 €** |

Hors frais fixes (≈ 30 $/mois) et hors utilisateurs gratuits (≈ 0,14 € chacun par mois sur Haiku).

**Lecture :**
- L'utilisateur régulier est rentable en mensuel ; l'annuel ne l'est vraiment qu'avec le cache complet.
- L'utilisateur intensif fait perdre de l'argent sur Sonnet. Trois leviers, à combiner : (1) mettre en place le cache complet de l'historique — le plus rentable ; (2) une limite d'usage raisonnable au-delà de laquelle le premium bascule sur Haiku, **jamais en situation de crise** ; (3) un prix annuel plus haut ou un plafond voix plus bas.
- Avec une commission de 26 % (Apple UE sans Small Business Program), le net mensuel tombe à 6,16 €.

---

## 5. Points réglementaires à valider avec un avocat

1. **Données de santé (RGPD, art. 9).** Le traitement des données « concernant la santé » est interdit par principe, sauf exceptions dont le **consentement explicite**. Des confidences sur l'humeur, l'anxiété ou des idées suicidaires peuvent être qualifiées de données de santé. À valider : la qualification, le texte de consentement, et les contrats avec chaque sous-traitant (Anthropic, Supabase, fournisseurs de voix), y compris les transferts hors UE. — [CNIL, RGPD chapitre 2](https://www.cnil.fr/fr/reglement-europeen-protection-donnees/chapitre2)

2. **Analyse d'impact (AIPD).** Obligatoire quand le traitement remplit au moins deux des neuf critères de la CNIL. Confie en coche vraisemblablement trois : « données sensibles », « personnes vulnérables », « usage innovant ». **Une AIPD est donc à prévoir avant le lancement.** — [CNIL, AIPD](https://www.cnil.fr/fr/ce-quil-faut-savoir-sur-lanalyse-dimpact-relative-la-protection-des-donnees-aipd)

3. **Hébergement HDS (France).** L'article L.1111-8 du code de la santé publique impose un hébergeur certifié HDS pour les données de santé recueillies à l'occasion d'activités de prévention, de diagnostic, de soins ou de suivi médico-social, hébergées pour le compte d'un tiers. Une app de bien-être sans professionnel de santé peut être hors champ, **mais ce n'est tranché par aucune source officielle que j'ai pu lire** (les pages de l'Agence du numérique en santé étaient illisibles par mon outil ; formulation issue de résumés de recherche). Question précise pour l'avocat : « Confie relève-t-elle du L.1111-8 ? Et si demain des psychologues s'y connectent ? » Les offres standard de Supabase ne sont pas présentées comme HDS (non vérifié). — [ANS, hébergement des données de santé](https://esante.gouv.fr/labels-certifications/hebergement-des-donnees-de-sante) · [ANS, champ d'application](https://esante.gouv.fr/faq/quel-est-le-champ-dapplication-de-la-legislation-relative-lhebergement-de-donnees-de-sante-caractere-personnel)

4. **Apple App Store** — [règles de validation](https://developer.apple.com/app-store/review/guidelines/)
   - 1.4.1 : les apps médicales sont examinées plus sévèrement et doivent rappeler de consulter un médecin. Ne jamais se présenter comme un outil de diagnostic ou de traitement.
   - 5.1.2(i) : il faut **indiquer clairement que des données personnelles sont envoyées à une IA tierce et obtenir l'accord explicite** de l'utilisateur avant.
   - 5.1.1(ix) : les apps de domaines très réglementés (dont la santé) ou demandant des informations sensibles doivent être publiées par une **société**, pas par un particulier.
   - 5.1.3 : pas d'usage publicitaire des données de santé.
   - 1.2 : mécanisme de signalement des contenus choquants et contact publié (vise notamment les apps de création par IA).
   - 3.1.1 : l'abonnement doit passer par l'achat intégré. 2.3.6 : classification d'âge honnête.

5. **Google Play**
   - Déclaration « Health apps » obligatoire dans la console ; la fiche doit préciser que l'app n'est pas un dispositif médical et inviter à consulter un professionnel de santé. — [politique santé](https://support.google.com/googleplay/android-developer/answer/16679511?hl=en)
   - Politique « contenu généré par IA » : elle couvre les apps dont le chatbot est la fonction centrale ; l'éditeur répond des contenus choquants générés. — [politique IA](https://support.google.com/googleplay/android-developer/answer/14094294?hl=en)

6. **Âge minimum.** Le RGPD (art. 8) fixe 16 ans et laisse chaque État descendre jusqu'à 13 ; la France a retenu **15 ans** (art. 45 de la loi Informatique et Libertés) : en dessous, il faut le consentement conjoint du mineur et d'un parent. La CNIL précise que ce n'est pas une « majorité numérique » générale. Vu le sujet, envisager de réserver l'app aux 18 ans et plus, ou au minimum 15 ans avec un parcours adapté ; les éventuelles lois plus récentes sur les mineurs en ligne sont à vérifier. — [RGPD art. 8](https://www.cnil.fr/fr/reglement-europeen-protection-donnees/chapitre2) · [CNIL, moins de 15 ans](https://cnil.fr/fr/recommandation-4-rechercher-le-consentement-dun-parent-pour-les-mineurs-de-moins-de-15-ans) · [CNIL, capacité des mineurs](https://www.cnil.fr/fr/recommandation-1-encadrer-la-capacite-dagir-des-mineurs-en-ligne)

7. **Règlement européen sur l'IA (art. 50).** Obligation d'informer la personne qu'elle parle à une IA, applicable depuis le 2 août 2026 selon plusieurs cabinets d'avocats. Source secondaire : texte officiel et dates du marquage des contenus générés non vérifiés. — [Goodwin](https://www.goodwinlaw.com/en/insights/publications/2026/08/alerts-technology-dpc-eu-ai-act-transparency-obligations-now-in-force) · [Sidley](https://datamatters.sidley.com/2026/06/24/eu-ai-act-transparency-obligations-preparing-for-compliance-by-2-august-2026/)

---

## 6. Récapitulatif de ce qui n'a pas pu être vérifié

- Prix Azure Speech ; prix Google Cloud STT et TTS (pages officielles illisibles par mon outil — chiffres indicatifs seulement).
- Coût à la minute d'OpenAI Realtime et de `gpt-4o-mini-tts`.
- Qualité du français et latences : uniquement des annonces de fournisseurs, aucun banc d'essai indépendant.
- Compatibilité de chaque SDK voix avec Expo SDK 58.
- Deepgram : durée de conservation par défaut, DPA, couverture d'Aura-2 par le serveur UE. Cartesia et AssemblyAI : politique de données ; AssemblyAI : français en direct.
- LiveKit (plugin Anthropic, résidence UE) ; Pipecat (client React Native, région UE).
- ElevenLabs : correspondance abonnement ↔ quotas, facturation des silences.
- Montant en euros de l'adhésion Apple ; région UE chez Render.
- Base de calcul exacte des commissions (hors TVA) : à confirmer avec le comptable.
- HDS : texte exact et applicabilité à Confie ; statut HDS de Supabase.
- Règlement IA : texte officiel de l'art. 50 et dates ; lois françaises récentes sur les mineurs en ligne.
