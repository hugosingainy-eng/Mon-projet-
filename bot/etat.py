"""État du bot, sauvegardé en JSON avec une écriture atomique.

On écrit d'abord dans un fichier temporaire, puis on le renomme : si le PC
s'éteint pendant l'écriture, l'ancien état reste intact.

Ce que l'état retient :
- les copies créées PAR LE BOT (jamais les vôtres) et leur dernière valeur connue ;
- les gains/pertes réalisés des copies fermées (même fermées hors du bot) ;
- l'arrêt d'urgence, les traders bannis, le climat du marché, les dates des cycles.
"""
import copy
import datetime as dt
import json
import logging
import os
import tempfile

log = logging.getLogger("etat")

ETAT_VIDE = {
    "version": 1,
    "copies": {},            # mirrorID -> infos (copies du bot uniquement)
    "ordres_en_attente": {}, # referenceID -> infos
    "pnl_realise": 0.0,      # gains/pertes des copies fermées
    "arret": {"actif": False, "raison": None, "date": None},
    "pause": False,
    "bannis": {},            # username -> date de fin (ISO)
    "climat": "calme",
    "exposition": 1.0,
    "marche": {},
    "derniere_selection": None,
    "derniere_analyse_jour": None,
    "derniere_veille": None,
    "references_traders": {},  # username -> mesures au moment de la sélection
    "alertes": [],
    "historique": [],          # suivi de la valeur totale
}


def maintenant():
    return dt.datetime.now(dt.timezone.utc)


def iso(d):
    return d.replace(microsecond=0).isoformat() if d else None


def lire_date(texte):
    if not texte:
        return None
    try:
        d = dt.datetime.fromisoformat(str(texte).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


class Etat:
    def __init__(self, chemin):
        self.chemin = chemin
        self.data = copy.deepcopy(ETAT_VIDE)
        self.charger()

    # --- fichier -------------------------------------------------------
    def charger(self):
        if not os.path.isfile(self.chemin):
            return
        try:
            with open(self.chemin, encoding="utf-8") as fh:
                lu = json.load(fh)
        except (OSError, ValueError) as exc:
            # On garde une copie du fichier abîmé pour pouvoir l'examiner
            log.error("État illisible (%s) : on repart d'un état vide et on garde "
                      "l'ancien fichier en .corrompu", exc)
            try:
                os.replace(self.chemin, self.chemin + ".corrompu")
            except OSError:
                pass
            return
        for k, v in ETAT_VIDE.items():
            self.data[k] = lu.get(k, copy.deepcopy(v))
        for k, v in lu.items():
            self.data.setdefault(k, v)

    def sauvegarder(self):
        dossier = os.path.dirname(os.path.abspath(self.chemin))
        os.makedirs(dossier, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".etat-", suffix=".tmp", dir=dossier)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.chemin)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # --- copies du bot -------------------------------------------------
    @property
    def copies(self):
        return self.data["copies"]

    def copies_ouvertes(self):
        return {mid: c for mid, c in self.copies.items() if c.get("ouverte")}

    def mirror_ids_du_bot(self):
        return set(self.copies.keys())

    def ajouter_copie(self, mirror_id, parent_cid, username, montant, reference_id):
        self.copies[str(mirror_id)] = {
            "parentCID": parent_cid,
            "username": username,
            "investi": float(montant),
            "derniere_valeur": float(montant),
            "ouverte": True,
            "cree_le": iso(maintenant()),
            "reference_id": reference_id,
            "maj_le": iso(maintenant()),
        }

    def fermer_copie(self, mirror_id, valeur_finale, raison):
        c = self.copies.get(str(mirror_id))
        if not c or not c.get("ouverte"):
            return 0.0
        valeur = c["derniere_valeur"] if valeur_finale is None else float(valeur_finale)
        resultat = valeur - c["investi"]
        c["ouverte"] = False
        c["ferme_le"] = iso(maintenant())
        c["raison_fermeture"] = raison
        c["valeur_finale"] = valeur
        c["resultat"] = resultat
        self.data["pnl_realise"] = float(self.data.get("pnl_realise", 0.0)) + resultat
        return resultat

    # --- pertes --------------------------------------------------------
    def pnl_latent(self):
        return sum(c["derniere_valeur"] - c["investi"] for c in self.copies_ouvertes().values())

    def pnl_total(self):
        return float(self.data.get("pnl_realise", 0.0)) + self.pnl_latent()

    def investi_total(self):
        return sum(c["investi"] for c in self.copies_ouvertes().values())

    # --- arrêt / bannis ------------------------------------------------
    @property
    def arret_actif(self):
        return bool(self.data["arret"].get("actif"))

    def declencher_arret(self, raison):
        self.data["arret"] = {"actif": True, "raison": raison, "date": iso(maintenant())}

    def reinitialiser_arret(self):
        """Réarme le bot après --reset. Les pertes passées sont oubliées :
        la limite de -5 % repart de zéro sur le budget."""
        self.data["arret"] = {"actif": False, "raison": None, "date": None}
        self.data["pnl_realise"] = 0.0
        self.data["pause"] = False
        self.data["reset_le"] = iso(maintenant())

    def prendre_reset_du_disque(self):
        """Si `--reset` a été lancé pendant que la boucle tourne, la boucle l'applique
        (sinon elle écraserait le fichier avec son ancien état)."""
        try:
            with open(self.chemin, encoding="utf-8") as fh:
                disque = json.load(fh)
        except (OSError, ValueError):
            return False
        if (disque.get("reset_le") or "") > (self.data.get("reset_le") or ""):
            self.reinitialiser_arret()
            self.data["reset_le"] = disque["reset_le"]
            log.info("--reset détecté : le bot est réarmé")
            return True
        return False

    def bannir(self, username, semaines, raison=""):
        fin = maintenant() + dt.timedelta(weeks=semaines)
        self.data["bannis"][username] = iso(fin)
        self.alerte("Trader %s banni %d semaines : %s" % (username, semaines, raison))

    def est_banni(self, username, quand=None):
        fin = lire_date(self.data["bannis"].get(username))
        return bool(fin and fin > (quand or maintenant()))

    def alerte(self, texte):
        log.warning(texte)
        self.data["alertes"].append({"date": iso(maintenant()), "texte": texte})
        self.data["alertes"] = self.data["alertes"][-200:]
