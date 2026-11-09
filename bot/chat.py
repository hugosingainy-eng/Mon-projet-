"""Discuter avec le bot, en français : dans le terminal (--chat) ou sur Telegram.

Ce que le chat peut faire :
- LIRE et expliquer : état, copies, rapport, raisons des rejets, climat ;
- agir UNIQUEMENT dans le sens prudent : stop (avec confirmation), pause,
  reprendre après une pause, bannir un trader.

Ce que le chat ne peut JAMAIS faire : augmenter le budget, passer en argent
réel, lever l'arrêt à -5 % (--reset reste en ligne de commande), toucher à vos
copies personnelles. L'IA ne fait que répondre aux questions : elle ne
déclenche aucune action.

Les actions sont déposées dans data/commandes/ et exécutées par la boucle
principale au plus tard quelques secondes plus tard.
"""
import json
import logging
import os
import tempfile
import threading
import time
import unicodedata
import uuid

import requests

from .etat import Etat, iso, maintenant

log = logging.getLogger("chat")

AIDE = (
    "Je comprends :\n"
    "- « statut » ou « comment vont mes copies ? »\n"
    "- « climat » : l'état du marché\n"
    "- « rapport » : le dernier rapport\n"
    "- « pourquoi <trader> ? » : la raison d'un rejet\n"
    "- « pause » / « reprendre » : suspendre les nouveaux investissements\n"
    "- « bannir <trader> »\n"
    "- « stop » ou « arrête tout » : ferme les copies du bot (confirmation demandée)\n"
    "Je ne peux pas augmenter le budget, passer en argent réel ni lever l'arrêt -5 %."
)

INTERDITS = ("augmente", "monte le", "passe en reel", "passer en reel", "argent reel",
             "mode reel", "reset", "rearm", "debloque", "plus de risque", "plus de levier",
             "double", "leve l'arret", "lever l'arret")


def sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")


# --- File de commandes -----------------------------------------------------
def deposer_commande(dossier, action, **args):
    os.makedirs(dossier, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dossier, prefix=".cmd-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"action": action, "args": args, "date": iso(maintenant())}, fh)
    final = os.path.join(dossier, "%d-%s.json" % (time.time() * 1000, uuid.uuid4().hex[:6]))
    os.replace(tmp, final)
    return final


def lire_commandes(dossier):
    """Lit et supprime les commandes en attente (dans l'ordre)."""
    if not os.path.isdir(dossier):
        return []
    out = []
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith(".json"):
            continue
        chemin = os.path.join(dossier, nom)
        try:
            with open(chemin, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, ValueError):
            pass
        try:
            os.unlink(chemin)
        except OSError:
            pass
    return out


ACTIONS_AUTORISEES = {"stop", "pause", "reprendre", "bannir"}


def executer_commandes(directeur, dossier):
    """Appelé par la boucle principale. Seules les actions prudentes passent."""
    for cmd in lire_commandes(dossier):
        action = cmd.get("action")
        if action not in ACTIONS_AUTORISEES:
            log.warning("Commande refusée : %r", action)
            continue
        etat = directeur.etat
        if action == "stop":
            try:
                directeur.synchroniser()  # copies déjà fermées par --stop : marquées fermées
            except Exception as exc:  # noqa: BLE001
                log.warning("Synchronisation avant arrêt impossible (%s)", exc)
            directeur.fermer_tout("stop demandé")
            etat.declencher_arret("arrêt manuel demandé par le chat")
        elif action == "pause":
            etat.data["pause"] = True
            etat.alerte("Pause demandée par le chat : plus de nouvel investissement")
        elif action == "reprendre":
            etat.data["pause"] = False
            etat.alerte("Fin de la pause demandée par le chat")
        elif action == "bannir":
            u = str(cmd.get("args", {}).get("username", ""))
            if u:
                for mid, c in etat.copies_ouvertes().items():
                    if c["username"].lower() == u.lower():
                        directeur.fermer(mid, "banni par le chat")
                etat.bannir(u, directeur.cfg["sentinelle"]["semaines_bannissement"],
                            "demandé par le chat")
        etat.sauvegarder()


# --- Le chat ---------------------------------------------------------------
class Chat:
    def __init__(self, cfg, chemin_etat, chemin_rapport, dossier_commandes, client_ia=None):
        self.cfg = cfg
        self.chemin_etat = chemin_etat
        self.chemin_rapport = chemin_rapport
        self.dossier = dossier_commandes
        self.ia = client_ia
        self.confirmation_en_attente = False

    def _etat(self):
        return Etat(self.chemin_etat)  # relu à chaque question (lecture seule)

    def statut(self):
        e = self._etat()
        L = ["Mode : %s | budget : %s $" % (self.cfg["mode"], self.cfg["budget"])]
        if e.arret_actif:
            L.append("⛔ ARRÊT actif : %s (python -m bot.main --reset pour réarmer)"
                     % e.data["arret"]["raison"])
        if e.data.get("pause"):
            L.append("⏸ En pause : pas de nouvel investissement")
        L.append("Climat : %s (exposition %.0f %%)" % (e.data.get("climat"),
                                                     100 * e.data.get("exposition", 1)))
        copies = e.copies_ouvertes()
        if not copies:
            L.append("Aucune copie ouverte (cash).")
        for c in copies.values():
            L.append("- %s : investi %.2f $, valeur %.2f $ (%+.2f $)" % (
                c["username"], c["investi"], c["derniere_valeur"],
                c["derniere_valeur"] - c["investi"]))
        L.append("Résultat total : %+.2f $ (réalisé %+.2f $)" % (
            e.pnl_total(), e.data.get("pnl_realise", 0)))
        return "\n".join(L)

    def _rapport(self):
        try:
            with open(self.chemin_rapport, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            return ""

    def repondre(self, texte):
        t = sans_accents(texte.strip())
        if self.confirmation_en_attente:
            self.confirmation_en_attente = False
            if t in ("oui", "o", "yes", "confirme", "je confirme"):
                deposer_commande(self.dossier, "stop")
                return ("Demande d'arrêt envoyée : le bot va fermer SES copies (jamais les "
                        "vôtres) et s'arrêter. Pour le relancer : python -m bot.main --reset")
            return "Arrêt annulé."
        if not t or t in ("aide", "help", "?"):
            return AIDE
        if any(m in t for m in ("stop", "arrete tout", "arreter tout", "ferme tout",
                                "coupe tout")):
            if self.cfg.get("chat", {}).get("confirmation_stop", True):
                self.confirmation_en_attente = True
                return "⚠️ Fermer toutes les copies du bot et l'arrêter ? Répondez « oui »."
            deposer_commande(self.dossier, "stop")
            return "Demande d'arrêt envoyée."
        if t.startswith("pause"):
            deposer_commande(self.dossier, "pause")
            return "Pause demandée : plus aucun nouvel investissement (la sécurité continue)."
        if t.startswith("reprendre"):
            deposer_commande(self.dossier, "reprendre")
            return "Fin de pause demandée (les limites de sécurité restent identiques)."
        if t.startswith("bannir"):
            u = texte.strip().split()[-1] if len(texte.split()) > 1 else ""
            if not u or u.lower() == "bannir":
                return "Précisez le trader : « bannir NomDuTrader »."
            deposer_commande(self.dossier, "bannir", username=u)
            return "Bannissement de %s demandé (sa copie par le bot sera fermée)." % u
        if any(m in t for m in INTERDITS):
            return ("Je ne peux pas faire ça depuis le chat : le budget, l'argent réel, le "
                    "levier et l'arrêt -5 % ne se changent que dans config.yaml / .env ou "
                    "avec --reset. C'est voulu, pour votre sécurité.")
        if any(m in t for m in ("statut", "etat", "copies", "comment va", "comment vont",
                                "status", "resultat", "gain", "perte")):
            return self.statut()
        if any(m in t for m in ("climat", "marche")):
            e = self._etat()
            m = e.data.get("dernier_marche") or {}
            return "Climat : %s. Détails : %s" % (e.data.get("climat"),
                                                 json.dumps(m.get("indices", {}),
                                                            ensure_ascii=False)[:1500])
        if t.startswith("rapport"):
            r = self._rapport()
            return r[:3500] if r else "Pas encore de rapport (aucune sélection faite)."
        if t.startswith("pourquoi") or "rejet" in t:
            mots = [m.strip("?!.,") for m in texte.split()[1:]]
            lignes = [l for l in self._rapport().splitlines() if l.startswith("| ")
                      and any(m and m.lower() in l.lower() for m in mots)]
            if lignes:
                return "\n".join(lignes[:10])
        return self._demander_ia(texte)

    def _demander_ia(self, question):
        if self.ia is None:
            return "Je n'ai pas compris. " + AIDE
        contexte = {"statut": self.statut(), "rapport": self._rapport()[:20000]}
        systeme = ("Tu es l'assistant d'un bot de copy trading eToro prudent. Réponds en "
                   "français simple, pour un débutant, en 6 phrases maximum, à partir du "
                   "contexte fourni. Tu ne peux déclencher AUCUNE action et ne promets "
                   "jamais de gains. Si l'utilisateur veut agir, rappelle-lui les commandes "
                   "« stop », « pause », « bannir ».")
        try:
            return self.ia.demander(systeme, json.dumps(contexte, ensure_ascii=False)
                                    + "\n\nQuestion : " + question, recherche=False)
        except Exception as exc:  # noqa: BLE001
            return "L'IA ne répond pas (%s). %s" % (exc, AIDE)


def boucle_terminal(chat, entree=input, sortie=print):
    sortie("Discussion avec le bot (tapez « quitter » pour sortir, « aide » pour l'aide).")
    while True:
        try:
            texte = entree("vous > ")
        except (EOFError, KeyboardInterrupt):
            break
        if sans_accents(texte.strip()) in ("quitter", "exit", "quit"):
            break
        sortie("bot > " + chat.repondre(texte))


class Telegram:
    """Mini-client Telegram (long polling). Ne répond qu'à VOTRE conversation."""

    def __init__(self, token, chat_id, chat, session=None):
        self.url = "https://api.telegram.org/bot%s/" % token
        self.chat_id = str(chat_id)
        self.chat = chat
        self.session = session or requests.Session()
        self.decalage = None
        self.actif = False

    def traiter(self, mise_a_jour):
        msg = mise_a_jour.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != self.chat_id:
            return None  # message d'un inconnu : ignoré
        texte = msg.get("text") or ""
        reponse = self.chat.repondre(texte)
        self.envoyer(reponse)
        return reponse

    def envoyer(self, texte):
        try:
            self.session.post(self.url + "sendMessage",
                              json={"chat_id": self.chat_id, "text": texte[:4000]}, timeout=30)
        except requests.RequestException as exc:
            log.warning("Telegram : envoi impossible (%s)", exc)

    def une_passe(self):
        params = {"timeout": 25}
        if self.decalage is not None:
            params["offset"] = self.decalage
        rep = self.session.get(self.url + "getUpdates", params=params, timeout=40)
        for maj in rep.json().get("result", []):
            self.decalage = maj["update_id"] + 1
            self.traiter(maj)

    def demarrer(self):
        self.actif = True

        def tourner():
            while self.actif:
                try:
                    self.une_passe()
                except Exception as exc:  # noqa: BLE001 - Telegram ne doit pas tuer le bot
                    log.warning("Telegram : %s", exc)
                    time.sleep(15)

        th = threading.Thread(target=tourner, name="telegram", daemon=True)
        th.start()
        return th
