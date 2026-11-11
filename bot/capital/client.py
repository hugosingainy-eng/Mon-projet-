"""Connexion à Capital.com par son API officielle (https://open-api.capital.com).

Fonctionne sur n'importe quel ordinateur (Chromebook compris) : tout passe par
Internet. Vérifié d'après la collection Postman officielle de Capital.com
(github.com/capital-com-sv/capital-api-postman) :
- démo : https://demo-api-capital.backend-capital.com/api/v1
- session : POST /session (en-tête X-CAP-API-KEY, identifiant + mot de passe),
  la réponse donne les en-têtes CST et X-SECURITY-TOKEN ; la session expire
  après 10 minutes d'inactivité (on se reconnecte tout seul) ; 1 connexion/s max ;
- prix : GET /prices/{epic}?resolution=DAY&max=1000 ; marchés : GET /markets/{epic} ;
- positions : GET /positions, POST /positions, DELETE /positions/{dealId} ;
- confirmation : GET /confirms/{dealReference}.

SÉCURITÉ :
- en mode "demo", le bot n'utilise QUE l'adresse démo ;
- le bot ne touche QUE les positions qu'il a ouvertes lui-même (leur numéro
  « dealId » est gardé dans son état) ; les vôtres ne sont jamais fermées ;
- le bot n'achète jamais un instrument sur lequel vous avez une position à vous
  (sinon Capital.com pourrait mélanger ou compenser les deux).
"""
import datetime as dt
import logging
import time

import requests

log = logging.getLogger("capital")


class ErreurCapital(Exception):
    pass


def _mid(prix):
    if not isinstance(prix, dict):
        return None
    b, a = prix.get("bid"), prix.get("ask")
    if b is None and a is None:
        return None
    if b is None or a is None:
        return float(b if b is not None else a)
    return (float(b) + float(a)) / 2


class ClientCapital:
    def __init__(self, cfg, session=None, dormir=time.sleep, horloge=time.monotonic):
        self.cfg = cfg
        self.cc = cfg.get("capital", {})
        sec = cfg.get("_secrets", {})
        self.cle = sec.get("CAPITAL_API_KEY", "")
        self.identifiant = sec.get("CAPITAL_IDENTIFIER", "")
        self.mot_de_passe = sec.get("CAPITAL_PASSWORD", "")
        self.demo = cfg.get("mode", "demo") == "demo"
        self.base = (self.cc.get("url_demo") if self.demo else self.cc.get("url_reel")).rstrip("/")
        if self.demo and "demo" not in self.base:
            raise ErreurCapital("SÉCURITÉ : mode démo mais l'adresse n'est pas celle de la démo")
        self.http = session or requests.Session()
        self.dormir = dormir
        self.horloge = horloge
        self.pause = float(self.cc.get("pause_min_secondes", 0.15))
        self.timeout = float(self.cc.get("timeout_secondes", 30))
        self.max_tentatives = int(self.cc.get("max_tentatives", 5))
        self.jetons = None
        self.infos_session = {}
        self._dernier = 0.0
        self._symboles = {}
        self._marches = {}
        self._fx = {}
        self.tickets_du_bot = set()    # rempli par le Directeur depuis son état
        self.connecte = False

    # --- HTTP -------------------------------------------------------------
    def _attendre(self):
        ecart = self.horloge() - self._dernier
        if ecart < self.pause:
            self.dormir(self.pause - ecart)
        self._dernier = self.horloge()

    def _ouvrir_session(self):
        if not (self.cle and self.identifiant and self.mot_de_passe):
            raise ErreurCapital("Identifiants Capital.com manquants : remplissez CAPITAL_API_KEY, "
                                "CAPITAL_IDENTIFIER et CAPITAL_PASSWORD dans .env")
        self._attendre()
        self.dormir(1.0)   # Capital.com : 1 connexion par seconde au plus
        try:
            rep = self.http.post(self.base + "/session",
                                 json={"identifier": self.identifiant,
                                       "password": self.mot_de_passe,
                                       "encryptedPassword": False},
                                 headers={"X-CAP-API-KEY": self.cle}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ErreurCapital("Capital.com injoignable (%s)" % exc) from exc
        if rep.status_code >= 400:
            raise ErreurCapital("Connexion refusée par Capital.com (%s) : %s. Vérifiez la clé API, "
                                "l'e-mail et le mot de passe (et que la clé est bien active)."
                                % (rep.status_code, _texte(rep)[:200]))
        cst, jeton = rep.headers.get("CST"), rep.headers.get("X-SECURITY-TOKEN")
        if not cst or not jeton:
            raise ErreurCapital("Réponse de connexion sans jetons CST / X-SECURITY-TOKEN")
        self.jetons = {"CST": cst, "X-SECURITY-TOKEN": jeton}
        try:
            self.infos_session = rep.json()
        except ValueError:
            self.infos_session = {}

    def requete(self, methode, chemin, params=None, corps=None):
        if self.jetons is None:
            self._ouvrir_session()
        derniere = None
        for tentative in range(1, self.max_tentatives + 1):
            self._attendre()
            try:
                rep = self.http.request(methode, self.base + chemin, params=params, json=corps,
                                        headers=dict(self.jetons), timeout=self.timeout)
            except requests.RequestException as exc:
                derniere = ErreurCapital("Erreur réseau (%s)" % exc)
                self.dormir(min(60, 2 ** tentative))
                continue
            if rep.status_code == 401:          # session expirée (10 min) : on se reconnecte
                self._ouvrir_session()
                derniere = ErreurCapital("Session expirée")
                continue
            if rep.status_code == 429 or rep.status_code >= 500:
                derniere = ErreurCapital("Capital.com a répondu %s" % rep.status_code)
                attente = rep.headers.get("Retry-After")
                try:
                    attente = float(attente) if attente else 2 ** tentative
                except ValueError:
                    attente = 2 ** tentative
                self.dormir(min(120, attente))
                continue
            if rep.status_code >= 400:
                raise ErreurCapital("Capital.com a refusé %s %s (%s) : %s" % (
                    methode, chemin, rep.status_code, _texte(rep)[:300]))
            if not rep.content:
                return {}
            try:
                return rep.json()
            except ValueError as exc:
                raise ErreurCapital("Réponse non JSON sur %s" % chemin) from exc
        raise derniere or ErreurCapital("Échec après plusieurs tentatives")

    # --- interface commune avec MetaTrader 5 ------------------------------
    def connecter(self):
        if not self.connecte:
            self.requete("GET", "/session")
            self.connecte = True
            log.info("Connecté à Capital.com (%s)", "DÉMO" if self.demo else "RÉEL")
        return True

    def compte(self):
        data = self.requete("GET", "/accounts")
        comptes = data.get("accounts", [])
        actif = self.infos_session.get("currentAccountId")
        c = next((x for x in comptes if x.get("accountId") == actif), None) or \
            next((x for x in comptes if x.get("preferred")), None) or (comptes[0] if comptes
                                                                        else {})
        bal = c.get("balance") or {}
        return {"login": c.get("accountId"), "server": "Capital.com " + (
            "DÉMO" if self.demo else "RÉEL"), "currency": c.get("currency"),
                "balance": bal.get("balance"), "equity": (bal.get("balance") or 0) + (
                    bal.get("profitLoss") or 0), "disponible": bal.get("available")}

    def est_demo(self):
        return self.demo

    def _marche(self, epic):
        if epic not in self._marches:
            self._marches[epic] = self.requete("GET", "/markets/" + epic)
        return self._marches[epic]

    def resoudre(self, nom):
        if nom in self._symboles:
            return self._symboles[nom]
        trouve = None
        for epic in [nom] + list(self.cc.get("alias", {}).get(nom, [])):
            try:
                self._marche(epic)
                trouve = epic
                break
            except ErreurCapital:
                continue
        self._symboles[nom] = trouve
        return trouve

    def infos(self, epic):
        m = self._marche(epic)
        regles = m.get("dealingRules") or {}
        mini = float((regles.get("minDealSize") or {}).get("value") or 0.01)
        pas = float((regles.get("minSizeIncrement") or {}).get("value") or mini)
        maxi = float((regles.get("maxDealSize") or {}).get("value") or 1e9)
        snap = m.get("snapshot") or {}
        return {"volume_min": mini, "volume_step": pas, "volume_max": maxi,
                "digits": int(snap.get("decimalPlacesFactor") or 5),
                "devise": (m.get("instrument") or {}).get("currency"),
                "statut": snap.get("marketStatus"),
                "stop_min": float((regles.get("minNormalStopOrLimitDistance") or {}).get(
                    "value") or 0),
                "stop_min_unite": (regles.get("minNormalStopOrLimitDistance") or {}).get(
                    "unit", "PERCENTAGE")}

    def bougies(self, epic, nb=400):
        data = self.requete("GET", "/prices/" + epic,
                            params={"resolution": "DAY", "max": min(int(nb), 1000)})
        out = []
        for p in data.get("prices", []):
            jour = _jour(p.get("snapshotTimeUTC") or p.get("snapshotTime"))
            o, h = _mid(p.get("openPrice")), _mid(p.get("highPrice"))
            low, c = _mid(p.get("lowPrice")), _mid(p.get("closePrice"))
            if jour and c:
                out.append((jour, o or c, h or c, low or c, c))
        out.sort()
        if not out:
            raise ErreurCapital("Pas d'historique pour %s" % epic)
        return out

    def prix(self, epic):
        self._marches.pop(epic, None)          # prix frais
        snap = self._marche(epic).get("snapshot") or {}
        bid, ask = snap.get("bid"), snap.get("offer")
        if not bid or not ask:
            raise ErreurCapital("Pas de prix pour %s (marché fermé ?)" % epic)
        return float(bid), float(ask)

    def _taux(self, devise):
        """Combien vaut 1 unité de `devise` dans la devise du compte."""
        compte = self.infos_session.get("currencyIsoCode") or "EUR"
        if not devise or devise == compte:
            return 1.0
        if devise in self._fx:
            return self._fx[devise]
        taux = None
        for epic, inverse in ((devise + compte, False), (compte + devise, True)):
            try:
                b, a = self.prix(epic)
                m = (b + a) / 2
                taux = 1 / m if inverse else m
                break
            except ErreurCapital:
                continue
        if taux is None:
            raise ErreurCapital("Taux de change %s -> %s introuvable" % (devise, compte))
        self._fx[devise] = taux
        return taux

    def valeur_mouvement(self, epic, volume, prix_depart, prix_arrivee):
        return float(volume) * (float(prix_arrivee) - float(prix_depart)) * self._taux(
            self.infos(epic)["devise"])

    def notionnel_par_lot(self, epic, prix):
        return abs(self.valeur_mouvement(epic, 1.0, prix, prix * 1.01)) * 100

    def positions(self):
        out = []
        for x in self.requete("GET", "/positions").get("positions", []):
            p, m = x.get("position", {}), x.get("market", {})
            upl = float(p.get("upl") or 0)
            try:
                upl *= self._taux(p.get("currency"))
            except ErreurCapital:
                pass
            out.append({"ticket": p.get("dealId"), "symbol": m.get("epic"),
                        "volume": float(p.get("size") or 0),
                        "type": 0 if p.get("direction") == "BUY" else 1,
                        "price_open": float(p.get("level") or 0),
                        "price_current": float(m.get("bid") or 0), "profit": upl,
                        "sl": p.get("stopLevel")})
        return out

    def est_du_bot(self, position):
        return str(position.get("ticket")) in self.tickets_du_bot

    def positions_du_bot(self):
        return [p for p in self.positions() if self.est_du_bot(p)]

    def _confirmer(self, reference):
        for _ in range(10):
            try:
                conf = self.requete("GET", "/confirms/" + reference)
            except ErreurCapital:
                conf = None
            if conf:
                return conf
            self.dormir(1.0)
        raise ErreurCapital("Pas de confirmation pour l'ordre %s" % reference)

    def acheter(self, epic, volume, stop_loss, commentaire="bot", verifier_seulement=False):
        info = self.infos(epic)
        if info.get("statut") not in (None, "TRADEABLE"):
            raise ErreurCapital("Marché %s fermé (%s)" % (epic, info.get("statut")))
        if volume < info["volume_min"] - 1e-12:
            raise ErreurCapital("Taille sous le minimum de Capital.com")
        _, ask = self.prix(epic)
        if stop_loss <= 0 or stop_loss >= ask:
            raise ErreurCapital("Stop-loss invalide")
        distance = ask - stop_loss
        if info["stop_min_unite"] == "PERCENTAGE":
            distance = distance / ask * 100
        if info["stop_min"] and distance < info["stop_min"]:
            raise ErreurCapital("Stop-loss trop proche du prix")
        if verifier_seulement:
            return {"ok": True}
        rep = self.requete("POST", "/positions", corps={
            "epic": epic, "direction": "BUY", "size": float(volume),
            "guaranteedStop": False, "stopLevel": float(stop_loss)})
        conf = self._confirmer(rep.get("dealReference"))
        if conf.get("dealStatus") != "ACCEPTED":
            raise ErreurCapital("Ordre refusé par Capital.com : %s" % (
                conf.get("reason") or conf.get("dealStatus")))
        deal = conf.get("dealId")
        for d in conf.get("affectedDeals") or []:
            if d.get("status") in ("OPENED", "OPEN"):
                deal = d.get("dealId") or deal
        self.tickets_du_bot.add(str(deal))
        return {"order": deal, "deal": deal}

    def fermer(self, position):
        if not self.est_du_bot(position):
            raise ErreurCapital("SÉCURITÉ : la position %s n'appartient pas au bot" %
                                position.get("ticket"))
        rep = self.requete("DELETE", "/positions/" + str(position["ticket"]))
        if rep.get("dealReference"):
            conf = self._confirmer(rep["dealReference"])
            if conf.get("dealStatus") not in (None, "ACCEPTED"):
                raise ErreurCapital("Fermeture refusée : %s" % conf.get("reason"))
        return rep

    def modifier_stop(self, position, nouveau_stop):
        """Déplace le stop-loss d'une position DU BOT (PUT /positions/{dealId})."""
        if not self.est_du_bot(position):
            raise ErreurCapital("SÉCURITÉ : la position %s n'appartient pas au bot" %
                                position.get("ticket"))
        rep = self.requete("PUT", "/positions/" + str(position["ticket"]),
                           corps={"stopLevel": float(nouveau_stop)})
        if rep.get("dealReference"):
            conf = self._confirmer(rep["dealReference"])
            if conf.get("dealStatus") not in (None, "ACCEPTED"):
                raise ErreurCapital("Stop refusé : %s" % conf.get("reason"))
        return rep

    def profit_realise(self, ticket):
        """Capital.com ne donne pas simplement le résultat d'une position fermée :
        le Directeur fait alors une estimation prudente."""
        return None


def _jour(texte):
    if not texte:
        return None
    try:
        return dt.datetime.fromisoformat(str(texte)[:19]).date()
    except ValueError:
        return None


def _texte(rep):
    try:
        return rep.text or ""
    except Exception:  # noqa: BLE001
        return ""
