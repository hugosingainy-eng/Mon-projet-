"""Directeur MetaTrader 5 : orchestre les agents et applique les limites dures.

Ordre d'une décision (chaque jour) :
  Marché (climat) -> Stratégie (signaux) -> Sorties des positions cassées ->
  Analyste IA (peut seulement réduire) -> Budget selon le climat ->
  Diversification (corrélation) -> Simulateur (TOUTES les options, 10 000 futurs
  minimum par option) -> Ordres.

Règles dures (bot/securite.py et ce fichier) :
- le bot n'engage jamais plus que `budget` (valeur exposée, sans effet de levier) ;
- chaque position a un stop-loss chez le courtier ; perte au stop <= 1 % du budget ;
- arrêt total à -5 % du budget (réalisé + latent) jusqu'à --reset ;
- achat seulement : aucune vente à découvert ;
- le bot ne touche QUE ses positions (numéro magic) : jamais les vôtres ;
- --dry-run : aucun ordre envoyé, fichier d'état séparé.
"""
import datetime as dt
import logging
import math
import os

import numpy as np

from .. import securite
from ..agents import analyste_ia, marche, simulateur
from ..etat import iso, maintenant
from . import strategie
from .client import ErreurMT5

log = logging.getLogger("directeur_mt5")

SYSTEME_IA = (
    "Tu es l'analyste des risques d'un bot de trading PRUDENT sur MetaTrader 5 (compte "
    "démo). Il achète seulement des indices, de l'or ou des devises en tendance haussière, "
    "avec stop-loss. Tu peux chercher l'actualité récente. Ton rôle est uniquement de "
    "signaler des dangers : réduire l'exposition ou opposer un veto à un instrument, jamais "
    "augmenter le risque. Réponds UNIQUEMENT en JSON : "
    '{"risque_marche": "faible|moyen|eleve", "exposition_max": nombre entre 0.2 et 1.0, '
    '"vetos": [{"username": "SYMBOLE", "raison": "..."}], "resume": "3 phrases maximum"}'
)


class DirecteurMT5:
    plateforme = "mt5"

    def __init__(self, client, cfg, etat, client_ia=None, dry_run=False, chemin_rapport=None):
        from ..config import appliquer_profil
        cfg = appliquer_profil(cfg)
        self.client = client
        self.cfg = cfg
        self.etat = etat
        self.ia = client_ia
        self.dry_run = dry_run
        dossier = cfg.get("fichiers", {}).get("dossier_data", "data")
        self.chemin_rapport = chemin_rapport or os.path.join(dossier, "mt5_rapport.md")
        self.cs = cfg["strategie"]
        self.jours_entre_selections = cfg["strategie"].get("jours_entre_decisions", 1)
        self.plateforme = cfg.get("plateforme", "mt5")
        self.dernier_rapport = None
        self._donnees = {}

    # =================================================================
    #  Synchronisation
    # =================================================================
    def synchroniser(self):
        self.client.connecter()
        if hasattr(self.client, "tickets_du_bot"):
            # Capital.com : le bot reconnaît ses positions grâce à son état
            self.client.tickets_du_bot = set(self.etat.copies.keys())
        reelles = {str(p["ticket"]): p for p in self.client.positions_du_bot()}
        for ticket, c in list(self.etat.copies_ouvertes().items()):
            p = reelles.get(ticket)
            if p is not None:
                c["derniere_valeur"] = c["investi"] + float(p.get("profit", 0))
                c["prix_actuel"] = float(p.get("price_current", 0) or 0)
                c["maj_le"] = iso(maintenant())
            elif self.dry_run and ticket.startswith("SIM-"):
                self._valoriser_simulation(c)
            else:
                profit = None
                try:
                    profit = self.client.profit_realise(ticket)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Historique de la position %s illisible (%s)", ticket, exc)
                valeur = None if profit is None else c["investi"] + profit
                if valeur is None:
                    valeur = self._estimation_prudente(c)
                res = self.etat.fermer_copie(ticket, valeur, "fermée hors du bot ou stop-loss")
                self.etat.alerte("Position %s (%s) fermée hors du bot ou par son stop-loss : "
                                 "%+.2f" % (c["username"], ticket, res))
        self.etat.data["historique"].append({"date": iso(maintenant()),
                                             "pnl_total": round(self.etat.pnl_total(), 2)})
        self.etat.data["historique"] = self.etat.data["historique"][-3000:]

    def _estimation_prudente(self, c):
        """Résultat inconnu : on compte le PIRE entre la dernière valeur connue et la
        valeur au stop-loss (pour que l'arrêt -5 % ne sous-estime jamais une perte)."""
        valeur = c["derniere_valeur"]
        try:
            if c.get("stop") and c.get("prix_entree") and c.get("volume"):
                au_stop = c["investi"] + self.client.valeur_mouvement(
                    c["symbole"], c["volume"], c["prix_entree"], c["stop"])
                valeur = min(valeur, au_stop)
        except Exception:  # noqa: BLE001
            pass
        return valeur

    def _valoriser_simulation(self, c):
        """En --dry-run, on suit la position fictive avec le vrai prix du marché."""
        try:
            bid, _ = self.client.prix(c["symbole"])
        except Exception:  # noqa: BLE001
            return
        if bid <= c.get("stop", 0):
            res = self.etat.fermer_copie(c["ticket"], c["investi"] * c["stop"] / c["prix_entree"],
                                         "stop-loss (simulation)")
            self.etat.alerte("[SIMULATION] Stop-loss touché sur %s : %+.2f" % (c["symbole"], res))
            return
        c["derniere_valeur"] = c["investi"] * bid / c["prix_entree"]
        c["prix_actuel"] = bid

    # =================================================================
    #  Sécurité
    # =================================================================
    def controle_securite(self):
        if self.etat.arret_actif:
            return False
        if securite.doit_arreter(self.cfg, self.etat):
            self.arret_urgence("perte de %.2f (limite %.2f = -%.0f %% du budget)" % (
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
        for ticket in list(self.etat.copies_ouvertes()):
            self.fermer(ticket, raison)

    def fermer(self, ticket, raison, bannir=False):
        securite.verifier_proprietaire(self.etat, ticket)
        c = self.etat.copies[str(ticket)]
        if not c.get("ouverte"):
            return
        log.info("Fermeture de %s (%s)", c["symbole"], raison)
        valeur = c["derniere_valeur"]
        if not self.dry_run and not str(ticket).startswith("SIM-"):
            p = next((x for x in self.client.positions_du_bot()
                      if str(x["ticket"]) == str(ticket)), None)
            if p is not None:
                try:
                    self.client.fermer(p)
                except Exception as exc:  # noqa: BLE001
                    self.etat.alerte("Fermeture de %s impossible (%s) : nouvel essai au "
                                     "prochain cycle" % (c["symbole"], exc))
                    return
                profit = None
                try:
                    profit = self.client.profit_realise(ticket)
                except Exception:  # noqa: BLE001
                    pass
                if profit is not None:
                    valeur = c["investi"] + profit
        self.etat.fermer_copie(ticket, valeur, raison)
        if bannir:
            self.etat.bannir(c["username"], self.cfg["sentinelle"]["semaines_bannissement"],
                             raison)

    # =================================================================
    #  Cycles
    # =================================================================
    def cycle_controle(self):
        """Toutes les 5 minutes : sécurité, Sentinelle, contrôle rapide du marché."""
        if self.etat.arret_actif:
            if self.etat.copies_ouvertes():
                self.synchroniser()
                self.fermer_tout("arrêt d'urgence (nouvel essai)")
                self.etat.sauvegarder()
            log.info("Bot arrêté (%s). Lancez --reset pour le réarmer.",
                     self.etat.data["arret"]["raison"])
            return
        self.synchroniser()
        if not self.controle_securite():
            return
        seuil = self.cfg["sentinelle"]["perte_copie_max"]
        for ticket, c in list(self.etat.copies_ouvertes().items()):
            if c["investi"] > 0 and c["derniere_valeur"] / c["investi"] - 1 <= -seuil:
                self.etat.alerte("Sentinelle : %s perd plus de %.0f %%" % (c["symbole"],
                                                                         100 * seuil))
                self.fermer(ticket, "Sentinelle : perte > %.0f %%" % (100 * seuil), bannir=True)
        if self._controle_rapide_marche():
            self.reajuster(self.etat.data["exposition"])
        self.controle_securite()
        self.etat.sauvegarder()

    def _controle_rapide_marche(self):
        ref = (self.etat.data.get("marche") or {}).get("clotures") or {}
        alerte = False
        for nom in self.cs["indices_climat"]:
            sym = self.client.resoudre(nom)
            if not sym or nom not in ref:
                continue
            try:
                bid, ask = self.client.prix(sym)
            except Exception:  # noqa: BLE001
                continue
            var = ((bid + ask) / 2) / ref[nom] - 1
            if var <= self.cfg["marche"]["chute_jour_stress"]:
                alerte = True
                self.etat.alerte("Chute de %.1f %% sur %s aujourd'hui : climat STRESS" % (
                    100 * var, nom))
        if alerte and self.etat.data.get("climat") != "stress":
            self.etat.data["climat"] = "stress"
            self.etat.data["exposition"] = self.cfg["marche"]["exposition"]["stress"]
            return True
        return False

    def analyser_marche(self):
        cmar = self.cfg["marche"]
        rapport = {"indices": {}, "date": dt.date.today().isoformat()}
        climats, clotures = [], {}
        for nom in self.cs["indices_climat"]:
            sym = self.client.resoudre(nom)
            try:
                b = self.client.bougies(sym, 420) if sym else None
                ind = marche.indicateurs([x[4] for x in b]) if b else None
            except Exception as exc:  # noqa: BLE001
                log.warning("Marché : %s illisible (%s)", nom, exc)
                ind = None
            if ind is None:
                rapport["indices"][nom] = {"erreur": "données indisponibles"}
                climats.append("tendu")  # sans données, on reste prudent
                continue
            c, pts, raisons = marche.climat_indice(ind, cmar)
            rapport["indices"][nom] = {"climat": c, "points": pts, "raisons": raisons}
            clotures[nom] = ind["dernier"]
            climats.append(c)
        rapport["climat"] = marche.pire("calme", *climats)
        rapport["exposition"] = cmar["exposition"][rapport["climat"]]
        self.etat.data["marche"] = {"date": rapport["date"], "clotures": clotures}
        return rapport

    def cycle_quotidien(self, aujourd_hui=None):
        if self.etat.arret_actif:
            return False
        ancien = self.etat.data.get("climat", "calme")
        rm = self.analyser_marche()
        self.etat.data["climat"] = rm["climat"]
        self.etat.data["exposition"] = rm["exposition"]
        self.etat.data["dernier_marche"] = rm
        self.etat.data["derniere_analyse_jour"] = (aujourd_hui or dt.date.today()).isoformat()
        self.etat.sauvegarder()
        return rm["climat"] != ancien

    def reajuster(self, exposition):
        """Réduit l'exposition en fermant les positions les plus faibles. Jamais d'ajout."""
        limite = securite.capital(self.cfg, self.etat) * exposition
        ouvertes = sorted(self.etat.copies_ouvertes().items(),
                          key=lambda kv: kv[1]["derniere_valeur"] / max(kv[1]["investi"], 0.01))
        total = sum(c["investi"] for _, c in ouvertes)
        for ticket, c in ouvertes:
            if total <= limite + 0.01:
                break
            self.fermer(ticket, "réajustement : climat %s" % self.etat.data.get("climat"))
            total -= c["investi"]

    # =================================================================
    #  Décision quotidienne
    # =================================================================
    def selection(self, aujourd_hui=None):
        aujourd_hui = aujourd_hui or dt.date.today()
        if self.etat.arret_actif:
            return None
        self.synchroniser()
        if not self.controle_securite():
            return None
        if not self.etat.data.get("marche"):
            self.cycle_quotidien(aujourd_hui)
        cfg, cs, etat = self.cfg, self.cs, self.etat
        r = {"date": iso(maintenant()), "mode": cfg["mode"], "dry_run": self.dry_run,
             "plateforme": "Capital.com" if self.plateforme == "capital" else "MetaTrader 5",
             "profil": cfg.get("profil", "prudent"), "rejets": [], "ordres": [], "signaux": {}}
        try:
            compte = self.client.compte()
            r["compte"] = {k: compte.get(k) for k in ("login", "server", "currency", "balance",
                                                       "equity")}
            r["compte"]["type"] = "DÉMO" if self.client.est_demo() else "RÉEL"
        except Exception as exc:  # noqa: BLE001
            r["compte"] = {"erreur": str(exc)}

        # 1. Stratégie : signaux sur chaque instrument
        donnees = {}
        for nom in cs["instruments"]:
            sym = self.client.resoudre(nom)
            if not sym:
                r["rejets"].append({"username": nom, "agent": "Stratégie",
                                    "raison": "symbole introuvable chez ce courtier"})
                continue
            try:
                b = self.client.bougies(sym, cs.get("historique_jours", 800))
            except Exception as exc:  # noqa: BLE001
                r["rejets"].append({"username": nom, "agent": "Stratégie",
                                    "raison": "historique indisponible (%s)" % exc})
                continue
            sig = strategie.analyser(b, cs)
            donnees[nom] = {"symbole": sym, "bougies": b, "signal": sig}
            r["signaux"][nom] = {k: sig.get(k) for k in ("raison", "dernier", "mm_longue",
                                                         "atr", "entree", "sortie", "strategie",
                                                         "elan_20j")}
        self._donnees = donnees

        # 2. Positions ouvertes : sortie selon leur stratégie, sinon stop suiveur
        ouvertes = {c["username"]: (t, c) for t, c in etat.copies_ouvertes().items()}
        for nom, (ticket, c) in list(ouvertes.items()):
            sig = (donnees.get(nom) or {}).get("signal") or {}
            strat = c.get("strategie", "tendance")
            if strategie.doit_sortir(sig, strat):
                raison = ("tendance cassée" if strat == "tendance"
                          else "cassure terminée (plus bas 10 j)")
                self.fermer(ticket, raison)
                r["ordres"].append({"type": "fermeture", "instrument": nom, "raison": raison})
                del ouvertes[nom]
                continue
            if cs.get("stop_suiveur", True) and sig.get("valide"):
                self._remonter_stop(ticket, c, sig, r)

        # 3. Candidats à l'achat (jamais sur un instrument où VOUS avez une position)
        try:
            perso = {p.get("symbol") for p in self.client.positions()
                     if not self.client.est_du_bot(p)}
        except Exception:  # noqa: BLE001
            perso = set()
        candidats = []
        for nom, d in donnees.items():
            sig = d["signal"]
            if nom in ouvertes:
                continue
            if d["symbole"] in perso:
                r["rejets"].append({"username": nom, "agent": "Directeur",
                                    "raison": "vous avez déjà une position à vous dessus"})
            elif etat.est_banni(nom):
                r["rejets"].append({"username": nom, "agent": "Sentinelle", "raison": "banni"})
            elif not sig.get("valide"):
                r["rejets"].append({"username": nom, "agent": "Stratégie",
                                    "raison": sig.get("raison")})
            elif not sig["entree"]:
                r["rejets"].append({"username": nom, "agent": "Stratégie",
                                    "raison": "pas de signal : " + sig["raison"]})
            else:
                candidats.append({"username": nom, "score": sig["force"]})
        candidats.sort(key=lambda t: t["score"], reverse=True)

        # 4. Analyste IA (ne peut que réduire)
        avis = analyste_ia.consulter(
            self.ia, cfg, {"marche": etat.data.get("dernier_marche"), "signaux": r["signaux"],
                           "positions": [{"instrument": c["username"],
                                          "investi": c["investi"],
                                          "valeur": c["derniere_valeur"]}
                                         for c in etat.copies_ouvertes().values()]},
            [t["username"] for t in candidats], systeme=SYSTEME_IA)
        r["ia"] = avis
        climat = etat.data.get("climat", "calme")
        expo, candidats, rej = analyste_ia.appliquer(avis, cfg["marche"]["exposition"][climat],
                                                     candidats)
        r["rejets"] += rej
        cap = securite.capital(cfg, etat)
        solde = (r.get("compte") or {}).get("balance")
        if isinstance(solde, (int, float)) and 0 < solde < cap:
            etat.alerte("Le compte ne contient que %.2f : le bot se limite à ce montant" % solde)
            cap = float(solde)
        total = cap * min(expo, securite.EXPOSITION_MAX_ABSOLUE)
        places = max(0, int(cs["positions_max"]) - len(ouvertes))
        r["budget"] = {"capital": cap, "climat": climat, "exposition": expo,
                       "montant_expose": total, "places": places,
                       "deja_engage": sum(c["investi"] for _, c in ouvertes.values())}

        # 5. Tailles de position + Simulateur : toutes les options, 10 000 futurs chacune
        tailles = {}
        for t in candidats[:int(cfg["simulateur"].get("max_candidats_explores", 8))]:
            try:
                tailles[t["username"]] = self._taille(t["username"], donnees[t["username"]],
                                                      total)
            except Exception as exc:  # noqa: BLE001
                tailles[t["username"]] = None
                r["rejets"].append({"username": t["username"], "agent": "Directeur",
                                    "raison": str(exc)})
        pool = [t for t in candidats if tailles.get(t["username"])]
        mise, alloc, essais = None, {}, []
        if pool and places > 0:
            gardes = [{"username": n} for n in ouvertes]
            tous = gardes + pool
            noms = [t["username"] for t in tous]
            rend = {n: strategie.rendements(donnees[n]["bougies"]) for n in noms if n in donnees}
            matrice, _ = simulateur.aligner(rend, noms, cfg["simulateur"]["historique_jours"])
            fixes = {n: c["investi"] for n, (_, c) in ouvertes.items()}

            def allocation(equipe, m):
                out = {}
                deja = sum(fixes.values())
                for t in equipe:
                    n = t["username"]
                    if n in fixes:
                        out[n] = fixes[n]
                        continue
                    vol = self._arrondir(tailles[n]["volume"] * m, tailles[n])
                    if vol is None:
                        return {}
                    out[n] = vol * tailles[n]["notionnel_lot"]
                if sum(out.values()) > total + 0.01 and sum(out.values()) > deja + 0.01:
                    return {}  # dépasserait le budget autorisé
                return out

            equipes = simulateur.options_possibles(
                gardes, pool, len(gardes) + places, lambda a, b: self._compatibles(a, b, matrice,
                                                                                   noms))
            meilleure, essais = simulateur.explorer(equipes, matrice, noms, allocation, cap, cfg)
            if meilleure:
                mise, alloc = meilleure["mise"], meilleure["allocation"]
        r["simulateur"] = sorted(essais, key=lambda o: (-o["feu_vert"], -o["mise"],
                                                        -o.get("pire_5", -9)))
        r["nb_options"] = len(essais)
        r["nb_futurs"] = sum(o.get("nb_simulations", 0) for o in essais)
        r["feu_vert"] = mise is not None

        # 6. Ordres (achats seulement si feu vert)
        if mise is None:
            self.reajuster(expo)
        else:
            for nom in alloc:
                if nom in ouvertes:
                    continue
                try:
                    ok = self.acheter(nom, donnees[nom], tailles[nom], mise)
                    r["ordres"].append({"type": "achat", "instrument": nom, "mise": mise,
                                        "statut": "ok" if ok else "refusé"})
                except securite.RefusSecurite as exc:
                    self.etat.alerte("Achat bloqué par la sécurité (%s) : %s" % (nom, exc))
                    r["ordres"].append({"type": "bloqué", "instrument": nom, "raison": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    self.etat.alerte("Achat de %s en échec : %s" % (nom, exc))
                    r["ordres"].append({"type": "échec", "instrument": nom, "raison": str(exc)})
        etat.data["derniere_selection"] = iso(maintenant())
        r["positions"] = [{"instrument": c["username"], "investi": round(c["investi"], 2),
                           "valeur": round(c["derniere_valeur"], 2), "ticket": t,
                           "stop": c.get("stop")}
                          for t, c in etat.copies_ouvertes().items()]
        r["pnl_total"] = etat.pnl_total()
        r["alertes"] = etat.data["alertes"][-15:]
        etat.sauvegarder()
        self.dernier_rapport = r
        try:
            ecrire_rapport_mt5(r, self.chemin_rapport)
        except Exception as exc:  # noqa: BLE001
            log.warning("Rapport non écrit (%s)", exc)
        return r

    # -----------------------------------------------------------------
    def _remonter_stop(self, ticket, c, sig, r):
        """Stop suiveur : le stop ne fait que MONTER, jamais descendre."""
        try:
            digits = int(self.client.infos(c["symbole"]).get("digits", 5))
            bid, _ = self.client.prix(c["symbole"])
        except Exception:  # noqa: BLE001
            return
        nouveau = round(sig["stop_suiveur"], digits)
        ancien = float(c.get("stop") or 0)
        if nouveau <= ancien or nouveau >= bid * 0.999:
            return
        if not self.dry_run and not str(ticket).startswith("SIM-"):
            p = next((x for x in self.client.positions_du_bot()
                      if str(x["ticket"]) == str(ticket)), None)
            if p is None:
                return
            try:
                self.client.modifier_stop(p, nouveau)
            except Exception as exc:  # noqa: BLE001
                log.warning("Stop de %s non remonté (%s)", c["symbole"], exc)
                return
        c["stop"] = nouveau
        r["ordres"].append({"type": "stop remonté", "instrument": c["username"],
                            "ancien": ancien, "nouveau": nouveau})

    def _compatibles(self, a, b, matrice, noms):
        """Refuse deux instruments trop corrélés (ex. S&P 500 et Nasdaq ensemble)."""
        i, j = noms.index(a["username"]), noms.index(b["username"])
        x, y = matrice[-252:, i], matrice[-252:, j]
        if np.std(x) == 0 or np.std(y) == 0:
            return True
        return float(np.corrcoef(x, y)[0, 1]) <= self.cs["correlation_max"]

    def _arrondir(self, volume, t):
        pas, mini = t["pas"], t["min"]
        v = math.floor(volume / pas + 1e-9) * pas
        v = min(v, t["max"])
        return round(v, 8) if v >= mini - 1e-12 else None

    def _taille(self, nom, d, total):
        """Volume tel que la perte au stop <= risque_par_trade x budget, et valeur exposée
        <= part du budget. Lève une erreur claire si le minimum du courtier est trop gros."""
        cs = self.cs
        sym, sig = d["symbole"], d["signal"]
        info = self.client.infos(sym)
        _, ask = self.client.prix(sym)
        stop = ask - sig["distance_stop"]
        perte_lot = abs(self.client.valeur_mouvement(sym, 1.0, ask, stop))
        notionnel_lot = self.client.notionnel_par_lot(sym, ask)
        budget = float(self.cfg["budget"])
        risque = cs["risque_par_trade"] * min(budget, total if total > 0 else budget)
        part = total / max(1, int(cs["positions_max"]))
        volume = min(risque / perte_lot if perte_lot else 0.0, part / notionnel_lot)
        t = {"pas": float(info.get("volume_step") or 0.01), "min": float(info.get("volume_min")
                                                                          or 0.01),
             "max": float(info.get("volume_max") or 100.0), "notionnel_lot": notionnel_lot,
             "perte_lot": perte_lot, "stop": round(stop, int(info.get("digits", 5))),
             "prix": ask, "symbole": sym}
        t["volume"] = volume
        if self._arrondir(volume, t) is None:
            raise ValueError("taille minimale du courtier trop grosse pour le budget "
                             "(%.2f lot = %.0f exposé)" % (t["min"], t["min"] * notionnel_lot))
        return t

    def acheter(self, nom, d, t, mise):
        volume = self._arrondir(t["volume"] * mise, t)
        if volume is None:
            raise securite.RefusSecurite("volume sous le minimum du courtier")
        montant = volume * t["notionnel_lot"]
        securite.verifier_ajout(self.cfg, self.etat, montant)
        perte_au_stop = volume * t["perte_lot"]
        if perte_au_stop > self.cs["risque_par_trade"] * float(self.cfg["budget"]) * 1.0001:
            raise securite.RefusSecurite("perte au stop trop grande")
        sym = t["symbole"]
        if self.dry_run:
            ticket = "SIM-%s-%d" % (nom, int(maintenant().timestamp()))
            log.info("[SIMULATION] Achat %s %.2f lot (%.2f exposé), stop %s - aucun ordre",
                     sym, volume, montant, t["stop"])
        else:
            self.client.acheter(sym, volume, t["stop"], verifier_seulement=True)
            res = self.client.acheter(sym, volume, t["stop"], commentaire="bot " + nom)
            ticket = str(res.get("order") or res.get("deal"))
            pos = next((p for p in self.client.positions_du_bot()
                        if p.get("symbol") == sym and str(p.get("ticket")) == ticket), None)
            if pos is None:
                pos = next((p for p in self.client.positions_du_bot()
                            if p.get("symbol") == sym), None)
            if pos is not None:
                ticket = str(pos["ticket"])
        self.etat.ajouter_copie(ticket, None, nom, montant, ticket)
        c = self.etat.copies[ticket]
        c.update({"symbole": sym, "volume": volume, "stop": t["stop"],
                  "prix_entree": t["prix"], "ticket": ticket,
                  "strategie": d["signal"].get("strategie") or "tendance"})
        return ticket


# =====================================================================
#  Rapport
# =====================================================================
def _p(v):
    return "—" if v is None else "%.0f %%" % (100 * v)


def _pct(v):
    return "—" if v is None else "%+.1f %%" % (100 * v)


def ecrire_rapport_mt5(r, chemin):
    L = ["# Rapport du bot %s - %s" % (r.get("plateforme", "MetaTrader 5"), r["date"]), ""]
    mode = "DÉMO (argent fictif)" if r["mode"] == "demo" else "ARGENT RÉEL"
    if r.get("dry_run"):
        mode += " - SIMULATION (--dry-run) : aucun ordre envoyé"
    L += ["**Mode :** " + mode, ""]
    c = r.get("compte") or {}
    if "erreur" not in c:
        L += ["**Compte :** %s sur %s (%s) - solde %s %s" % (
            c.get("login"), c.get("server"), c.get("type"), c.get("balance"),
            c.get("currency")), ""]
    L += ["> Rappel : aucun bot ne garantit des gains. Les simulations rejouent le passé.", ""]
    b = r.get("budget", {})
    L += ["## Climat et budget", "",
          "- Climat : **%s** - exposition retenue **%s**" % (b.get("climat"),
                                                           _p(b.get("exposition"))),
          "- Montant exposable : %.2f sur un capital de %.2f (déjà engagé : %.2f)" % (
              b.get("montant_expose", 0), b.get("capital", 0), b.get("deja_engage", 0)),
          "- Profil : **%s** - places libres : %s" % (r.get("profil"), b.get("places")),
          "- Résultat total du bot : **%+.2f**" % r.get("pnl_total", 0), ""]
    L += ["## Signaux de la stratégie (tendance)", "",
          "| Instrument | Dernier | Moyenne 200 j | Élan 20 j | Signal |", "|---|---|---|---|---|"]
    for nom, s in sorted((r.get("signaux") or {}).items(),
                         key=lambda kv: (not kv[1].get("entree"), kv[0])):
        L.append("| %s | %s | %s | %s | %s |" % (
            nom, "%.5g" % s["dernier"] if s.get("dernier") else "—",
            "%.5g" % s["mm_longue"] if s.get("mm_longue") else "—",
            _pct(s.get("elan_20j")),
            ("ACHAT (%s)" % s.get("strategie")) if s.get("entree") else (s.get("raison") or "—")))
    L += ["", "## Simulateur (Monte Carlo)", ""]
    essais = r.get("simulateur") or []
    if not essais:
        L += ["Aucune option à simuler (pas de signal d'achat ou pas de place).", ""]
    else:
        L += ["**%d options examinées, %s futurs simulés** (au moins 10 000 par option) "
              "avant le moindre ordre." % (r.get("nb_options", 0), "{:,}".format(
                  r.get("nb_futurs", 0)).replace(",", " ")), "",
              "| Instruments | Mise | Chances de gagner | Risque d'arrêt | Médiane | Pire 5 % "
              "| Verdict |", "|---|---|---|---|---|---|---|"]
        for e in essais[:10]:
            if not e.get("valide"):
                continue
            L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                ", ".join(e["equipe"]), _p(e["mise"]), _p(e["chance_gain"]),
                _p(e["risque_arret"]), _pct(e["mediane"]), _pct(e["pire_5"]),
                "FEU VERT" if e["feu_vert"] else "refusé"))
        L += ["", "**Décision :** %s" % ("feu vert" if r.get("feu_vert") else
                                         "feu rouge, aucun achat"), ""]
    ia = r.get("ia") or {}
    L += ["## Avis de l'IA", "", "- Exposition max : %s - vetos : %s" % (
        _p(ia.get("exposition_max")),
        ", ".join(v["username"] for v in ia.get("vetos", [])) or "aucun"),
        "- " + (ia.get("resume") or "—"), "", "_L'IA ne peut que rendre le bot plus prudent._",
        ""]
    L += ["## Positions du bot", ""]
    if r.get("positions"):
        L += ["| Instrument | Exposé | Valeur | Résultat | Stop-loss |", "|---|---|---|---|---|"]
        for p in r["positions"]:
            L.append("| %s | %.2f | %.2f | %+.2f | %s |" % (p["instrument"], p["investi"],
                                                         p["valeur"], p["valeur"] - p["investi"],
                                                         p.get("stop")))
    else:
        L.append("Aucune position (le bot reste en cash).")
    L.append("")
    if r.get("ordres"):
        L += ["### Ordres de ce cycle", ""] + ["- " + ", ".join(
            "%s: %s" % kv for kv in o.items()) for o in r["ordres"]] + [""]
    L += ["## Alertes", ""] + ["- %s : %s" % (a["date"], a["texte"])
                               for a in r.get("alertes") or []] + [""]
    L += ["## Raison de chaque refus", "", "| Instrument | Agent | Raison |", "|---|---|---|"]
    for x in r.get("rejets") or []:
        L.append("| %s | %s | %s |" % (x["username"], x["agent"],
                                       str(x["raison"]).replace("|", "/")))
    L.append("")
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return chemin
