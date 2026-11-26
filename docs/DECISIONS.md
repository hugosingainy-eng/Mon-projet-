# Décisions

Chaque décision : ce qui a été choisi, pourquoi, et ce qui la ferait changer.

1. **Expo 58 + React Native + TypeScript + Expo Router.** Un seul code pour iOS, Android et le web ; c'est la pile demandée et la mieux outillée. La version web sert aussi d'aperçu et de terrain de test automatique.
2. **Données sur l'appareil d'abord, Supabase ensuite.** Pour des données aussi intimes, ne rien stocker en ligne par défaut est le choix le plus protecteur, et l'app fonctionne sans compte. Supabase (comptes, PostgreSQL, RLS) est prêt côté schéma pour la synchronisation, en option.
3. **Un petit serveur Node comme passerelle IA**, plutôt qu'une Edge Function Supabase. Il existait, il est testé ici, il diffuse les réponses en continu et s'héberge partout. Une Edge Function resterait possible : la logique tient dans deux fichiers.
4. **Modèle : Claude Opus 5.5, interchangeable** (`CONFIE_MODEL`). La qualité d'écoute est le cœur du produit. Le coût par conversation et l'option d'un modèle plus économique pour l'offre gratuite sont chiffrés dans `RECHERCHE-VOIX-COUTS.md`.
5. **Voix : services vocaux du téléphone pour le lancement.** Gratuit, sans fournisseur audio supplémentaire, hors ligne possible selon l'appareil. Limite : qualité de voix variable et interruption au toucher plutôt qu'à la voix. Une voix « avancée » via un service en ligne est une option premium à décider après mesure des coûts.
6. **Mémoire = liste courte de faits, pas un enregistrement des conversations.** Transparente, modifiable, désactivée par défaut. L'IA propose, la personne peut annuler d'un geste.
7. **Balises texte plutôt qu'appels d'outils** pour les vidéos, exercices et la mémoire. Plus simple, compatible avec tous les modèles, et la personne ne voit jamais la mécanique.
8. **Vidéos : uniquement via l'API officielle YouTube.** Sans clé, l'app ouvre une recherche plutôt que d'inventer des titres. L'app ne certifie pas les qualifications des créateurs.
9. **Pas de base documentaire (RAG) pour l'instant.** Les techniques proposées sont classiques et bien connues du modèle ; les exercices sont rédigés à la main avec leur source. Une base vérifiée par un professionnel serait l'étape suivante, pas un préalable.
10. **Pas de paiement dans cette version.** Aucun faux paywall. Le modèle freemium proposé est dans la recherche ; il sera branché après validation des coûts réels.
11. **Pas de rouge, pas d'emoji, une seule ombre.** Pour tenir la direction artistique : calme, premium, sans distraction.
12. **Illustrations vectorielles dessinées dans la palette** plutôt que des photos : nettes à toutes les tailles, légères, cohérentes en thème sombre.
13. **Accompagnement généraliste.** Confie n'est pas réservée à l'amour : la personne choisit son sujet (amour et relations, moral, stress, confiance, motivation, solitude, autre).
