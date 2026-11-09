"""Agent 9 - Directeur : orchestre l'équipe et applique les limites dures.

Ordre d'une sélection : Recruteur, Inspecteur, Renseignement, IA, budget selon
le climat, garder ou couper les copies actuelles, Diversification, Simulateur,
puis ordres.

Le Directeur est le seul à passer des ordres, et uniquement sur des COPIES de
traders (jamais d'action en direct). Chaque ordre passe par bot/securite.py.
"""
import datetime as dt
import logging
import os
import uuid

from .. import securite
from ..donnees import champ, mirror_id, mirrors, rendements_journaliers, valeur_mirror
from ..etat import iso, maintenant
from ..rapport import ecrire_rapport
from . import analyste_ia, diversification, inspecteur, marche, recruteur, renseignement
from . import sentinelle, simulateur, veille_x

log = logging.getLogger("directeur")


def nouvelle_reference():
    return "bot" + uuid.uuid4().hex[:28]  # 31 caractères (35 max chez eToro)


class Directeur:
    def __init__(self, api, cfg, etat, client_ia=None, outils=None, dry_run=False,
                 chemin_rapport=None, chemin_cache=None):
        dossier = cfg.get("fichiers", {}).get("dossier_data", "data")
        self.api = api
        self.cfg = cfg
        self.etat = etat
        self.ia = client_ia
        self.outils = outils
        self.dry_run = dry_run
        self.chemin_rapport = chemin_rapport or os.path.join(dossier, "rapport.md")
        self.chemin_cache = chemin_cache or os.path.join(dossier, "cache_13f.json")
        self.dernier_rapport = None

    # =================================================================
    #  Synchronisation avec eToro
    # =================================================================
    def synchroniser(self):
        """Met à jour la valeur des copies du bot. Une copie du bot absente
        d'eToro a été fermée hors du bot : on la compte avec sa dernière valeur
        connue (les pertes restent comptées)."""
        portefeuille = self.api.portefeuille()
        liste = mirrors(portefeuille)
        par_id = {mirror_id(m): m for m in liste if mirror_id(m)}
        self._suivre_ordres_en_attente()
        for mid, c in list(self.etat.copies_ouvertes().items()):
            m = par_id.get(mid)
            if m is not None:
                c["derniere_valeur"] = valeur_mirror(m)
                c["maj_le"] = iso(maintenant())
            elif self.dry_run and mid.startswith("SIM-"):
                continue  # copie simulée : elle n'existe pas chez eToro
            else:
                res = self.etat.fermer_copie(mid, None, "fermée hors du bot")
                self.etat.alerte("La copie de %s a été fermée hors du bot : résultat compté "
                                 "avec sa dernière valeur connue (%+.2f $)" % (c["username"], res))
        perso = [m for m in liste if mirror_id(m) not in self.etat.mirror_ids_du_bot()]
        self.cids_personnels = {str(champ(m, "parentCID", "ParentCID")) for m in perso}
        self.etat.data["historique"].append({"date": iso(maintenant()),
                                             "pnl_total": round(self.etat.pnl_total(), 2)})
        self.etat.data["historique"] = self.etat.data["historique"][-3000:]
        return portefeuille

    def _suivre_ordres_en_attente(self):
        for ref, o in list(self.etat.data.get("ordres_en_attente", {}).items()):
            try:
                res = self.api.copie_suivi(ref)
            except Exception as exc:  # noqa: BLE001
                log.warning("Suivi de l'ordre %s impossible (%s)", ref, exc)
                continue
            if res is None:
                continue
            del self.etat.data["ordres_en_attente"][ref]
            self._enregistrer_resultat(res, o, ref)

    # =================================================================
    #  Sécurité
    # =================================================================
    def controle_securite(self):
        """True si tout va bien ; False si l'arrêt d'urgence est (ou était) actif."""
        if self.etat.arret_actif:
            return False
        if securite.doit_arreter(self.cfg, self.etat):
            self.arret_urgence("perte de %.2f $ (limite %.2f $ = -%.0f %% du budget)" % (
                self.etat.pnl_total(), securite.seuil_arret(self.cfg),
                100 * securite.perte_max(self.cfg)))
            return False
        return True

    def arret_urgence(self, raison):
        self.etat.alerte("ARRÊT D'URGENCE : " + raison)
        self.fermer_tout("arrêt d'urgence")
        self.etat.declencher_arret(raison)
        self.etat.sauvegarder()

    def fermer_tout(self, raison):
        for mid in list(self.etat.copies_ouvertes()):
            self.fermer(mid, raison)

    def fermer(self, mid, raison, bannir=False):
        securite.verifier_proprietaire(self.etat, mid)
        c = self.etat.copies[str(mid)]
        if not c.get("ouverte"):
            return
        log.info("Fermeture de la copie de %s (%s)", c["username"], raison)
        if not self.dry_run and not str(mid).startswith("SIM-"):
            try:
                self.api.copie_fermer(int(mid) if str(mid).isdigit() else mid,
                                      nouvelle_reference())
            except Exception as exc:  # noqa: BLE001
                self.etat.alerte("Fermeture de %s impossible (%s) : nouvel essai au prochain "
                                 "cycle" % (c["username"], exc))
                return
        self.etat.fermer_copie(mid, c["derniere_valeur"], raison)
        if bannir:
            self.etat.bannir(c["username"], self.cfg["sentinelle"]["semaines_bannissement"],
                             raison)

    # =================================================================
    #  Ordres
    # =================================================================
    def investir(self, trader, montant):
        """Ouvre une nouvelle copie (ou y ajoute de l'argent)."""
        montant = round(float(montant), 2)
        securite.verifier_ajout(self.cfg, self.etat, montant)
        cid = trader["cid"]
        if str(cid) in getattr(self, "cids_personnels", set()):
            raise securite.RefusSecurite("vous copiez déjà %s vous-même : le bot n'y touche pas"
                                         % trader["username"])
        ref = nouvelle_reference()
        infos = {"parentCID": cid, "username": trader["username"], "montant": montant,
                 "date": iso(maintenant())}
        if self.dry_run:
            log.info("[SIMULATION] Copie de %s pour %.2f $ (aucun ordre envoyé)",
                     trader["username"], montant)
            self.etat.ajouter_copie("SIM-" + ref, cid, trader["username"], montant, ref)
            return "SIM-" + ref
        if not self.api.copie_eligibilite(cid, montant):
            raise securite.RefusSecurite("eToro refuse la copie de %s (test d'éligibilité)"
                                         % trader["username"])
        self.etat.data["ordres_en_attente"][ref] = infos
        self.etat.sauvegarder()  # en cas de plantage, on sait qu'un ordre est parti
        self.api.copie_ordre(cid, montant, ref)
        res = self.api.attendre_copie(ref)
        if res is None:
            self.etat.alerte("Ordre de copie de %s toujours en cours : suivi au prochain cycle"
                             % trader["username"])
            return None
        del self.etat.data["ordres_en_attente"][ref]
        return self._enregistrer_resultat(res, infos, ref)

    def _enregistrer_resultat(self, res, infos, ref):
        if not res.get("isSuccess"):
            self.etat.alerte("Ordre de copie de %s refusé par eToro : %s" % (
                infos["username"], res.get("errorMessage") or res))
            return None
        mid = str(champ(res, "mirrorID", "mirrorId", defaut=""))
        if not mid:
            self.etat.alerte("Ordre de %s réussi mais sans mirrorID" % infos["username"])
            return None
        if mid in self.etat.copies:
            c = self.etat.copies[mid]
            c["investi"] += infos["montant"]
            c["derniere_valeur"] += infos["montant"]
            c["ouverte"] = True
        else:
            self.etat.ajouter_copie(mid, infos["parentCID"], infos["username"],
                                    infos["montant"], ref)
        return mid

    def ajuster(self, mid, delta):
        """Ajoute (delta > 0) ou retire (delta < 0) de l'argent à une copie du bot."""
        securite.verifier_proprietaire(self.etat, mid)
        c = self.etat.copies[mid]
        if delta > 0:
            securite.verifier_ajout(self.cfg, self.etat, delta)
        if delta < 0 and -delta >= c["derniere_valeur"] * 0.98:
            return self.fermer(mid, "réduction totale")
        if not self.dry_run and not mid.startswith("SIM-"):
            ref = nouvelle_reference()
            self.api.copie_ordre(c["parentCID"], round(delta, 2), ref)
            res = self.api.attendre_copie(ref)
            if res is not None and not res.get("isSuccess"):
                self.etat.alerte("Ajustement de %s refusé : %s" % (c["username"], res))
                return None
        if delta > 0:
            c["investi"] += delta
            c["derniere_valeur"] += delta
        else:
            retrait = -delta
            v = max(c["derniere_valeur"], 0.01)
            f = min(1.0, retrait / v)
            realise = f * (v - c["investi"])
            self.etat.data["pnl_realise"] += realise
            c["investi"] -= f * c["investi"]
            c["derniere_valeur"] -= retrait
        log.info("Copie de %s ajustée de %+.2f $", c["username"], delta)
        return mid

    # =================================================================
    #  Cycles
    # =================================================================
    def cycle_controle(self):
        """Toutes les 5 minutes : sécurité, Sentinelle, contrôle rapide du marché."""
        if self.etat.arret_actif:
            if self.etat.copies_ouvertes():
                # Une fermeture a échoué pendant l'arrêt : on réessaie à chaque cycle.
                self.synchroniser()
                self.fermer_tout("arrêt d'urgence (nouvel essai)")
                self.etat.sauvegarder()
            log.info("Bot arrêté (%s). Lancez --reset pour le réarmer.",
                     self.etat.data["arret"]["raison"])
            return
        self.synchroniser()
        if not self.controle_securite():
            return
        for d in sentinelle.controle_pertes(self.etat, self.cfg):
            self.etat.alerte("Sentinelle : " + d["username"] + " - " + d["raison"])
            self.fermer(d["mirror_id"], d["raison"], bannir=True)
        _, alerte = marche.controle_rapide(self.api, self.cfg, self.etat)
        if alerte:
            self.reajuster(self.etat.data["exposition"])
        self.controle_securite()
        self.etat.sauvegarder()

    def cycle_quotidien(self, aujourd_hui=None):
        """Chaque jour : marché, comportement des traders, veille actualités."""
        if self.etat.arret_actif:
            return False
        aujourd_hui = aujourd_hui or dt.date.today()
        ancien = self.etat.data.get("climat", "calme")
        rapport_m = marche.analyser_marche(self.api, self.cfg, self.etat, aujourd_hui)
        self.etat.data["climat"] = rapport_m["climat"]
        self.etat.data["exposition"] = rapport_m["exposition"]
        self.etat.data["dernier_marche"] = _resume_marche(rapport_m)
        for d in sentinelle.controle_comportement(self.api, self.etat, self.cfg, aujourd_hui):
            self.etat.alerte("Sentinelle : " + d["username"] + " - " + d["raison"])
            self.fermer(d["mirror_id"], d["raison"], bannir=True)
        self.veille_quotidienne()
        self.etat.data["derniere_analyse_jour"] = aujourd_hui.isoformat()
        self.etat.sauvegarder()
        change = rapport_m["climat"] != ancien
        if change:
            self.etat.alerte("Le climat passe de %s à %s : nouvelle sélection" % (
                ancien, rapport_m["climat"]))
        return change

    def veille_quotidienne(self):
        """Actualités sur les traders copiés : si plus de 25 % de leur portefeuille
        est touché, l'IA enquête et peut couper la copie."""
        copies = self.etat.copies_ouvertes()
        if not copies or self.outils is None:
            return
        seuil = self.cfg["renseignement"]["actualites"]["seuil_enquete"]
        portefeuilles = {}
        for mid, c in copies.items():
            try:
                portefeuilles[mid] = self._poids_tickers(c["username"])
            except Exception as exc:  # noqa: BLE001
                log.warning("Veille : portefeuille de %s illisible (%s)", c["username"], exc)
        tickers = set().union(*[set(p) for p in portefeuilles.values()]) if portefeuilles else set()
        try:
            nouvelles = renseignement.actualites_risquees(self.outils, self.cfg, tickers)
        except Exception as exc:  # noqa: BLE001
            log.warning("Veille actualités en échec (%s)", exc)
            nouvelles = {}
        alertes_x = veille_x.veiller(self.ia, self.cfg, [c["username"] for c in copies.values()],
                                     tickers)
        for mid, poids in portefeuilles.items():
            c = copies[mid]
            part = renseignement.part_touchee(poids, nouvelles)
            alerte_x = alertes_x.get(c["username"])
            if part > seuil or (alerte_x and alerte_x["gravite"] == "forte"):
                concernees = {t: nouvelles.get(t) for t in poids if t in nouvelles}
                self.etat.alerte("Actualités inquiétantes sur %.0f %% du portefeuille de %s : "
                                 "enquête de l'IA" % (100 * part, c["username"]))
                verdict = analyste_ia.enqueter(self.ia, c["username"],
                                               {"actualites": concernees, "x": alerte_x})
                if verdict["couper"]:
                    self.fermer(mid, "enquête IA : " + verdict["raison"], bannir=True)

    def reajuster(self, exposition):
        """Réduit les copies existantes pour respecter une exposition plus basse.
        Ne fait QUE réduire (jamais d'ajout ici)."""
        copies = self.etat.copies_ouvertes()
        if not copies:
            return
        cc = self.cfg["copie"]
        total = securite.capital(self.cfg, self.etat) * exposition
        n, part = securite.nb_et_part(total, len(copies), cc["montant_min_copie"])
        tri = sorted(copies.items(), key=lambda kv: kv[1]["derniere_valeur"] / max(
            kv[1]["investi"], 0.01), reverse=True)
        for i, (mid, c) in enumerate(tri):
            if i >= n:
                self.fermer(mid, "réajustement : climat %s" % self.etat.data.get("climat"))
                continue
            delta = part - c["investi"]
            if delta < -cc["montant_min_ajustement"]:
                try:
                    self.ajuster(mid, delta)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Réajustement de %s impossible (%s)", c["username"], exc)

    # =================================================================
    #  Sélection complète
    # =================================================================
    def selection(self, aujourd_hui=None):
        aujourd_hui = aujourd_hui or dt.date.today()
        if self.etat.arret_actif:
            log.info("Sélection annulée : arrêt d'urgence actif")
            return None
        self.synchroniser()
        if not self.controle_securite():
            return None
        if not self.etat.data.get("marche"):
            self.cycle_quotidien(aujourd_hui)
        cfg, etat = self.cfg, self.etat
        r = {"date": iso(maintenant()), "mode": cfg["mode"], "dry_run": self.dry_run,
             "rejets": [], "ordres": [], "alertes": []}

        # 1. Recruteur
        candidats, rej = recruteur.recruter(self.api, cfg, etat, aujourd_hui)
        r["rejets"] += rej
        # Les copies personnelles de l'utilisateur sont intouchables
        perso = getattr(self, "cids_personnels", set())
        gardes = []
        for t in candidats:
            if str(t["cid"]) in perso:
                r["rejets"].append({"username": t["username"], "agent": "Directeur",
                                    "raison": "vous le copiez déjà vous-même"})
            else:
                gardes.append(t)
        candidats = gardes

        # Les copies actuelles du bot sont réexaminées comme des candidats
        actuelles = {c["username"]: (mid, c) for mid, c in etat.copies_ouvertes().items()}
        noms_candidats = {t["username"] for t in candidats}
        rejets_recruteur = {x["username"]: x["raison"] for x in rej
                            if not x["raison"].startswith("hors des")}
        a_couper = {}
        for u, (mid, c) in actuelles.items():
            if u in rejets_recruteur:
                a_couper[mid] = "ne passe plus les filtres : " + rejets_recruteur[u]
            elif u not in noms_candidats:
                candidats.append({"username": u, "cid": c["parentCID"], "score": 0.0,
                                  "deja_copie": True})
        for t in candidats:
            t["deja_copie"] = t["username"] in actuelles

        # 2. Inspecteur
        candidats, rej = inspecteur.inspecter(self.api, cfg, candidats)
        r["rejets"] += rej
        for x in rej:
            if x["username"] in actuelles:
                a_couper[actuelles[x["username"]][0]] = "Inspecteur : " + x["raison"]

        # 3. Renseignement
        intel = self._renseignement(candidats, aujourd_hui)
        r["renseignement"] = intel["rapport"]
        candidats.sort(key=lambda t: t.get("score", 0.0), reverse=True)

        # 4. Analyste IA
        marche_resume = etat.data.get("dernier_marche", {})
        rapports_ia = {
            "marche": marche_resume,
            "candidats": [_resume_trader(t) for t in candidats],
            "copies_actuelles": [{"username": c["username"], "investi": c["investi"],
                                  "valeur": c["derniere_valeur"]}
                                 for c in etat.copies_ouvertes().values()],
            "renseignement": intel["rapport"],
            "alertes_recentes": etat.data["alertes"][-10:],
        }
        avis = analyste_ia.consulter(self.ia, cfg, rapports_ia,
                                     [t["username"] for t in candidats])
        r["ia"] = avis

        # 5. Budget selon le climat (+ avis IA qui ne peut que réduire)
        climat = etat.data.get("climat", "calme")
        expo_climat = cfg["marche"]["exposition"][climat]
        exposition, candidats, rej = analyste_ia.appliquer(avis, expo_climat, candidats)
        r["rejets"] += rej
        for x in rej:
            if x["username"] in actuelles:
                a_couper[actuelles[x["username"]][0]] = x["raison"]
        exposition = min(exposition, securite.EXPOSITION_MAX_ABSOLUE)
        cap = securite.capital(cfg, etat)
        total = cap * exposition
        cc = cfg["copie"]
        n_max, part = securite.nb_et_part(total, cc["nb_traders"], cc["montant_min_copie"])
        r["budget"] = {"capital": cap, "climat": climat, "exposition": exposition,
                       "montant_expose": total, "nb_traders": n_max, "part": part}

        # 6. Garder ou couper les copies actuelles
        for mid, raison in a_couper.items():
            self.fermer(mid, raison)
            r["ordres"].append({"type": "fermeture", "username": etat.copies[mid]["username"],
                                "raison": raison})
        gardes_actuels = [t for t in candidats if t["deja_copie"]
                          and actuelles[t["username"]][0] not in a_couper]
        nouveaux = [t for t in candidats if not t["deja_copie"]]
        gardes_actuels.sort(key=lambda t: _perf(actuelles[t["username"]][1]), reverse=True)
        while len(gardes_actuels) > n_max:
            t = gardes_actuels.pop()
            mid = actuelles[t["username"]][0]
            self.fermer(mid, "moins de place (climat %s)" % climat)
            r["ordres"].append({"type": "fermeture", "username": t["username"],
                                "raison": "moins de place (climat %s)" % climat})

        # 7. Diversification : les nouveaux doivent être compatibles avec les copies gardées
        nouveaux, rej = diversification.diversifier(nouveaux, cfg, deja=gardes_actuels,
                                                    entre_eux=False)
        r["rejets"] += rej
        pool = nouveaux[:int(cfg["simulateur"].get("max_candidats_explores", 8))]
        for t in nouveaux[len(pool):]:
            r["rejets"].append({"username": t["username"], "agent": "Simulateur",
                                "raison": "hors des %d meilleurs candidats explorés"
                                % len(pool)})

        # 8. Simulateur : TOUTES les équipes possibles x toutes les mises,
        #    au moins 10 000 futurs simulés pour chacune, avant le moindre ordre.
        mise, alloc, essais, equipe = None, {}, [], []
        tous = gardes_actuels + pool
        if tous and n_max > 0:
            rendements = self._rendements(tous, aujourd_hui)
            usernames = [t["username"] for t in tous]
            matrice, _ = simulateur.aligner(rendements, usernames,
                                            cfg["simulateur"]["historique_jours"])
            equipes = simulateur.options_possibles(
                gardes_actuels, pool, n_max,
                lambda a, b: diversification.compatibles(a, b, cfg))
            meilleure, essais = simulateur.explorer(
                equipes, matrice, usernames,
                lambda eq, m: self._allocation(eq, total * m, actuelles), cap, cfg)
            if meilleure:
                mise, alloc = meilleure["mise"], meilleure["allocation"]
                equipe = [t for t in tous if t["username"] in alloc]
        r["equipe_proposee"] = [t["username"] for t in equipe]
        r["simulateur"] = sorted(essais, key=lambda o: (-o["feu_vert"], -o["mise"],
                                                        -o.get("pire_5", -9)))
        r["nb_options"] = len(essais)
        r["nb_futurs"] = sum(o.get("nb_simulations", 0) for o in essais)
        r["feu_vert"] = mise is not None
        if mise is not None:
            # Les copies actuelles qui ne font pas partie de la meilleure option sont fermées
            for t in gardes_actuels:
                if t["username"] not in alloc:
                    self.fermer(actuelles[t["username"]][0], "pas dans la meilleure option")
                    r["ordres"].append({"type": "fermeture", "username": t["username"],
                                        "raison": "pas dans la meilleure option"})

        # 9. Ordres
        if mise is None:
            # Feu rouge : aucune nouvelle copie, et aucun ajout. On peut seulement réduire.
            self.reajuster(min(exposition, etat.data.get("exposition", 1.0)))
        else:
            self._passer_ordres(alloc, equipe, actuelles, r)
        etat.data["derniere_selection"] = iso(maintenant())
        etat.data["exposition"] = exposition
        for t in equipe:
            if t.get("portefeuille"):
                etat.data["references_traders"][t["username"]] = {
                    "levier_moyen": t["portefeuille"]["levier_moyen"],
                    "risque": t.get("risque")}
        r["copies"] = [{"username": c["username"], "investi": round(c["investi"], 2),
                        "valeur": round(c["derniere_valeur"], 2), "mirror": mid}
                       for mid, c in etat.copies_ouvertes().items()]
        r["pnl_total"] = etat.pnl_total()
        r["alertes"] = etat.data["alertes"][-15:]
        etat.sauvegarder()
        self.dernier_rapport = r
        try:
            ecrire_rapport(r, self.chemin_rapport)
        except Exception as exc:  # noqa: BLE001
            log.warning("Rapport non écrit (%s)", exc)
        return r

    # -----------------------------------------------------------------
    def _passer_ordres(self, alloc, equipe, actuelles, r):
        cc = self.cfg["copie"]
        par_nom = {t["username"]: t for t in equipe}
        # D'abord les réductions (libèrent du budget), ensuite les ajouts.
        plan = []
        for u, cible in alloc.items():
            if u in actuelles:
                mid, c = actuelles[u]
                if not c.get("ouverte"):
                    continue
                delta = cible - c["investi"]
                if abs(delta) >= max(cc["montant_min_ajustement"],
                                     cc["seuil_reajustement"] * c["investi"]):
                    plan.append((delta, u, mid))
            else:
                plan.append((cible, u, None))
        plan.sort(key=lambda p: p[0])
        for delta, u, mid in plan:
            try:
                if mid:
                    self.ajuster(mid, delta)
                    r["ordres"].append({"type": "ajustement", "username": u,
                                        "montant": round(delta, 2)})
                else:
                    nouveau = self.investir(par_nom[u], delta)
                    r["ordres"].append({"type": "nouvelle copie", "username": u,
                                        "montant": round(delta, 2),
                                        "statut": "ok" if nouveau else "en attente/refusé"})
            except securite.RefusSecurite as exc:
                self.etat.alerte("Ordre bloqué par la sécurité (%s) : %s" % (u, exc))
                r["ordres"].append({"type": "bloqué", "username": u, "raison": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self.etat.alerte("Ordre pour %s en échec : %s" % (u, exc))
                r["ordres"].append({"type": "échec", "username": u, "raison": str(exc)})

    def _allocation(self, equipe, total, actuelles):
        """Montant par trader : parts égales + petit bonus pour les copies gagnantes
        (« scale »), sans jamais dépasser `total` ni descendre sous le minimum."""
        cc = self.cfg["copie"]
        minimum = cc["montant_min_copie"]
        # Les nouveaux les moins bien classés sautent en premier si la part est trop petite.
        ordre = [t for t in equipe if t["deja_copie"]] + sorted(
            [t for t in equipe if not t["deja_copie"]], key=lambda t: -t.get("score", 0))
        n, part = securite.nb_et_part(total, len(ordre), minimum)
        if n == 0:
            return {}
        retenus = ordre[:n]
        sc = cc.get("scaling", {})
        cibles = {}
        for t in retenus:
            bonus = 0.0
            if sc.get("actif") and t["username"] in actuelles:
                gain = _perf(actuelles[t["username"]][1])
                bonus = sc["bonus_max"] * min(1.0, max(0.0, gain / sc["gain_pour_bonus_max"]))
            cibles[t["username"]] = part * (1 + bonus)
        somme = sum(cibles.values())
        if somme > total:
            cibles = {u: v * total / somme for u, v in cibles.items()}
        if any(v < minimum for v in cibles.values()):
            cibles = {u: part for u in cibles}
        return {u: round(v, 2) for u, v in cibles.items()}

    def _rendements(self, equipe, aujourd_hui):
        jours = self.cfg["simulateur"]["historique_jours"]
        debut = (aujourd_hui - dt.timedelta(days=int(jours * 1.5))).isoformat()
        out = {}
        for t in equipe:
            try:
                out[t["username"]] = rendements_journaliers(
                    self.api.gains_journaliers(t["username"], debut, aujourd_hui.isoformat()),
                    self.cfg)
            except Exception as exc:  # noqa: BLE001
                log.warning("Rendements journaliers de %s indisponibles (%s)",
                            t["username"], exc)
                out[t["username"]] = {}
        return out

    def _symboles(self, ids):
        cache = self.etat.data.setdefault("symboles", {})
        manquants = [i for i in ids if str(i) not in cache]
        for i in range(0, len(manquants), 50):
            try:
                for ins in self.api.instruments(ids=manquants[i:i + 50]):
                    iid = champ(ins, "instrumentId", "instrumentID", "InstrumentID")
                    sym = champ(ins, "symbol", "Symbol", "symbolFull")
                    if iid is not None and sym:
                        cache[str(iid)] = str(sym).upper()
            except Exception as exc:  # noqa: BLE001
                log.warning("Symboles introuvables (%s)", exc)
        return {i: cache.get(str(i)) for i in ids}

    def _poids_tickers(self, username, analyse=None):
        if analyse is None:
            from ..donnees import analyser_portefeuille_live
            analyse = analyser_portefeuille_live(self.api.portefeuille_live(username), self.cfg)
        syms = self._symboles(list(analyse["poids"]))
        poids = {}
        for iid, w in analyse["poids"].items():
            s = syms.get(iid)
            if s:
                poids[s] = poids.get(s, 0.0) + w
        return poids

    def _renseignement(self, candidats, aujourd_hui):
        """Bonus grands investisseurs, malus actualités et veille X. Jamais bloquant."""
        cfg = self.cfg
        rapport = {"favoris": {}, "congres": {}, "actualites": {}, "x": {}, "notes": []}
        for t in candidats:
            t["score_base"] = t.get("score", 0.0)
            t["tickers"] = self._poids_tickers(t["username"], t.get("portefeuille")) \
                if t.get("portefeuille") else {}
        tous = set().union(*[set(t["tickers"]) for t in candidats]) if candidats else set()
        favoris, congres, nouvelles, alertes_x = {}, {}, {}, {}
        if self.outils is not None:
            for nom, fn in (
                    ("Grands Investisseurs", lambda: renseignement.favoris_grands_investisseurs(
                        self.outils, cfg, self.chemin_cache)),
                    ("Congrès", lambda: renseignement.achats_congres(self.outils, cfg,
                                                                     aujourd_hui)),
                    ("Actualités", lambda: renseignement.actualites_risquees(
                        self.outils, cfg, tous))):
                try:
                    res = fn()
                except Exception as exc:  # noqa: BLE001 - un outil en panne ne bloque rien
                    log.warning("Renseignement %s en échec (%s)", nom, exc)
                    rapport["notes"].append("%s indisponible" % nom)
                    res = {}
                if nom == "Grands Investisseurs":
                    favoris = res
                elif nom == "Congrès":
                    congres = res
                else:
                    nouvelles = res
        else:
            rapport["notes"].append("outils de renseignement désactivés")
        try:
            alertes_x = veille_x.veiller(self.ia, cfg, [t["username"] for t in candidats], tous)
        except Exception as exc:  # noqa: BLE001
            log.warning("Veille X en échec (%s)", exc)
        for t in candidats:
            bonus, communs = renseignement.bonus_grands_investisseurs(t["tickers"], favoris, cfg)
            malus, part = renseignement.malus_actualites(t["tickers"], nouvelles, cfg)
            mx = veille_x.malus_x(t["username"], t["tickers"], alertes_x, cfg)
            t["bonus_gi"], t["communs_gi"], t["malus_news"], t["malus_x"] = bonus, communs, malus, mx
            t["score"] = t["score_base"] * max(0.0, 1 + bonus - malus - mx)
        rapport["favoris"] = {t["username"]: t["communs_gi"] for t in candidats if t["communs_gi"]}
        rapport["congres"] = dict(sorted(congres.items(), key=lambda kv: -(
            kv[1]["achats"] + kv[1]["ventes"]))[:15])
        rapport["actualites"] = {k: v[:3] for k, v in list(nouvelles.items())[:15]}
        rapport["x"] = alertes_x
        return {"rapport": rapport}


def _perf(c):
    return c["derniere_valeur"] / c["investi"] - 1 if c.get("investi") else 0.0


def _resume_trader(t):
    return {k: t.get(k) for k in ("username", "gain", "chute", "risque", "mois_gagnants",
                                  "copieurs", "score", "bonus_gi", "malus_news", "malus_x",
                                  "deja_copie")} | {"tickers": dict(list(sorted(
                                      (t.get("tickers") or {}).items(),
                                      key=lambda kv: -kv[1]))[:8])}


def _resume_marche(rapport_m):
    out = {"climat": rapport_m["climat"], "exposition": rapport_m["exposition"],
           "date": rapport_m["date"], "indices": {}}
    for s, v in rapport_m["indices"].items():
        if "erreur" in v:
            out["indices"][s] = v
        else:
            out["indices"][s] = {k: (round(v[k], 4) if isinstance(v[k], float) else v[k])
                                 for k in ("climat", "points", "raisons", "baisse_plus_haut",
                                           "ratio_vol", "variation_5j", "sous_mm200")}
    return out
