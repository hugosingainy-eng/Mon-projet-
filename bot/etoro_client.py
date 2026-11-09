"""Client de l'API officielle eToro (https://api-portal.etoro.com).

- En-têtes : x-api-key, x-user-key et un x-request-id (UUID) NEUF à chaque requête.
- Démo / réel : une clé ne marche que pour un environnement ; les chemins démo
  contiennent /demo/.
- Limites : 60 requêtes/min en général, 20/min pour le trading, une pause
  minimale entre deux appels, et respect de l'en-tête Retry-After sur 429.

Les formes exactes des réponses sont « à vérifier » sur une vraie réponse :
le client accepte plusieurs noms de clés possibles et ne plante pas si un
champ manque.
"""
import collections
import logging
import time
import uuid

import requests

log = logging.getLogger("etoro")


class ErreurAPI(Exception):
    def __init__(self, message, statut=None, corps=None):
        super().__init__(message)
        self.statut = statut
        self.corps = corps


class ErreurPassagere(ErreurAPI):
    """Erreur réseau, 429 ou 5xx : on peut réessayer plus tard."""


class LimiteurDebit:
    """Fenêtre glissante : au plus `par_minute` appels sur 60 s, et une pause
    minimale entre deux appels."""

    def __init__(self, par_minute, pause_min=0.0, horloge=time.monotonic, dormir=time.sleep):
        self.par_minute = max(1, int(par_minute))
        self.pause_min = float(pause_min)
        self.horloge = horloge
        self.dormir = dormir
        self.appels = collections.deque()

    def attendre(self):
        t = self.horloge()
        while self.appels and t - self.appels[0] >= 60:
            self.appels.popleft()
        attente = 0.0
        if self.appels and self.pause_min:
            attente = max(attente, self.pause_min - (t - self.appels[-1]))
        if len(self.appels) >= self.par_minute:
            attente = max(attente, 60 - (t - self.appels[0]) + 0.05)
        if attente > 0:
            self.dormir(attente)
        self.appels.append(self.horloge())


def extraire_liste(data, *cles):
    """Trouve la liste utile dans une réponse JSON (les noms varient)."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for cle in cles + ("items", "data", "results", "users", "Items", "Data"):
        v = data.get(cle)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            sous = extraire_liste(v, *cles)
            if sous:
                return sous
    return []


class EtoroClient:
    def __init__(self, api_key, user_key, mode="demo", cfg_api=None, session=None,
                 dormir=time.sleep, horloge=time.monotonic):
        if not api_key or not user_key:
            raise ErreurAPI("Clés eToro manquantes : remplissez ETORO_API_KEY et "
                            "ETORO_USER_KEY dans .env")
        if mode not in ("demo", "real"):
            raise ErreurAPI("mode inconnu : %r" % mode)
        cfg_api = cfg_api or {}
        self.api_key = api_key
        self.user_key = user_key
        self.mode = mode
        self.base = cfg_api.get("base_url", "https://public-api.etoro.com").rstrip("/")
        self.timeout = float(cfg_api.get("timeout_secondes", 30))
        self.max_tentatives = int(cfg_api.get("max_tentatives", 5))
        self.backoff = float(cfg_api.get("backoff_base_secondes", 2))
        self.attente_ordre = float(cfg_api.get("attente_ordre_secondes", 120))
        self.session = session or requests.Session()
        self.dormir = dormir
        pause = float(cfg_api.get("pause_min_secondes", 1.1))
        self.limiteur = LimiteurDebit(cfg_api.get("limite_par_minute", 60), pause,
                                      horloge, dormir)
        self.limiteur_trading = LimiteurDebit(cfg_api.get("limite_trading_par_minute", 20),
                                              pause, horloge, dormir)

    # ------------------------------------------------------------------
    def _entetes(self):
        return {
            "x-api-key": self.api_key,
            "x-user-key": self.user_key,
            "x-request-id": str(uuid.uuid4()),  # neuf à chaque requête
            "Accept": "application/json",
        }

    def _requete(self, methode, chemin, params=None, corps=None, trading=False,
                 accepter_404=False):
        url = self.base + chemin
        derniere = None
        for tentative in range(1, self.max_tentatives + 1):
            self.limiteur.attendre()
            if trading:
                self.limiteur_trading.attendre()
            try:
                rep = self.session.request(methode, url, params=params, json=corps,
                                           headers=self._entetes(), timeout=self.timeout)
            except requests.RequestException as exc:
                derniere = ErreurPassagere("Erreur réseau sur %s : %s" % (chemin, exc))
                self._pause(tentative, None)
                continue
            statut = rep.status_code
            if statut == 404 and accepter_404:
                return None
            if statut == 429 or statut >= 500:
                derniere = ErreurPassagere("eToro a répondu %s sur %s" % (statut, chemin),
                                           statut, _texte(rep))
                self._pause(tentative, rep.headers.get("Retry-After"))
                continue
            if statut >= 400:
                raise ErreurAPI("eToro a refusé %s %s (%s) : %s"
                                % (methode, chemin, statut, _texte(rep)[:300]),
                                statut, _texte(rep))
            if not rep.content:
                return {}
            try:
                return rep.json()
            except ValueError:
                raise ErreurAPI("Réponse non JSON sur %s" % chemin, statut, _texte(rep))
        raise derniere or ErreurPassagere("Échec après %d tentatives" % self.max_tentatives)

    def _pause(self, tentative, retry_after):
        attente = self.backoff * (2 ** (tentative - 1))
        if retry_after:
            try:
                attente = max(attente, float(retry_after))
            except ValueError:
                pass
        attente = min(attente, 300)
        log.warning("Pause de %.0f s avant nouvelle tentative (%d/%d)",
                    attente, tentative, self.max_tentatives)
        self.dormir(attente)

    # --- Portefeuille ---------------------------------------------------
    def portefeuille(self):
        """GET /api/v1/trading/info/{demo|real}/pnl -> clientPortfolio."""
        data = self._requete("GET", "/api/v1/trading/info/%s/pnl" % self.mode) or {}
        return data.get("clientPortfolio", data)

    # --- Classement et traders -----------------------------------------
    def classement(self, page=1, taille=100, periode="OneYearAgo", **filtres):
        params = {"period": periode, "page": page, "pageSize": min(int(taille), 100)}
        for cle, val in filtres.items():
            if val is not None:
                params[cle] = str(val).lower() if isinstance(val, bool) else val
        data = self._requete("GET", "/api/v2/portfolios/rankings", params=params)
        return extraire_liste(data, "rankings", "investors")

    def gains(self, username):
        """GET /api/v1/user-info/people/{username}/gain -> {monthly[], yearly[]}."""
        return self._requete("GET", "/api/v1/user-info/people/%s/gain" % username) or {}

    def gains_journaliers(self, username, date_min, date_max):
        data = self._requete("GET", "/api/v1/user-info/people/%s/daily-gain" % username,
                             params={"minDate": date_min, "maxDate": date_max,
                                     "type": "Daily"})
        return extraire_liste(data, "dailyGains", "gains", "daily")

    def trade_info(self, username, periode="OneYearAgo"):
        return self._requete("GET", "/api/v1/user-info/people/%s/tradeinfo" % username,
                             params={"period": periode}) or {}

    def portefeuille_live(self, username):
        return self._requete("GET", "/api/v1/user-info/people/%s/portfolio/live"
                             % username) or {}

    # --- Marché ---------------------------------------------------------
    def instruments(self, symboles=None, ids=None):
        params = {}
        if symboles:
            params["symbols"] = ",".join(symboles)
        if ids:
            params["instrumentsIds"] = ",".join(str(i) for i in ids)
        data = self._requete("GET", "/api/v2/market-data/instruments", params=params)
        return extraire_liste(data, "instruments")

    def cours(self, ids):
        data = self._requete("GET", "/api/v2/market-data/rates",
                             params={"instrumentIds": ",".join(str(i) for i in ids)})
        return extraire_liste(data, "rates")

    def bougies(self, instrument_id, intervalle="1d", depuis=None, limite=400):
        params = {"interval": intervalle, "limit": limite}
        if depuis:
            params["from"] = depuis
        data = self._requete("GET", "/api/v1/data/instruments/%s/candles" % instrument_id,
                             params=params)
        return extraire_liste(data, "results", "candles")

    # --- Copie ----------------------------------------------------------
    @property
    def _base_copie(self):
        return "/api/v2/trading/copy/demo" if self.mode == "demo" else "/api/v2/trading/copy"

    def copie_eligibilite(self, parent_cid, montant):
        data = self._requete("POST", self._base_copie + "/eligibility",
                             corps={"parentCID": parent_cid, "amount": montant}, trading=True)
        return bool((data or {}).get("isSuccess"))

    def copie_ordre(self, parent_cid, montant, reference_id):
        """Montant positif = ajoute de l'argent, négatif = en retire."""
        if len(reference_id) > 35:
            raise ErreurAPI("referenceID trop long (35 caractères max)")
        return self._requete("POST", self._base_copie,
                             corps={"parentCID": parent_cid, "amount": montant,
                                    "referenceID": reference_id}, trading=True) or {}

    def copie_suivi(self, reference_id):
        """None tant que l'opération n'est pas finie (404)."""
        return self._requete("GET", self._base_copie + "/" + reference_id, accepter_404=True)

    def copie_fermer(self, mirror_id, client_request_id):
        return self._requete("POST", self._base_copie + "/close",
                             corps={"mirrorID": mirror_id, "unregisterType": "Close",
                                    "clientRequestID": client_request_id}, trading=True) or {}

    def attendre_copie(self, reference_id, intervalle=3.0):
        """Attend la fin d'un ordre de copie. Renvoie le résultat ou None."""
        ecoule = 0.0
        while ecoule <= self.attente_ordre:
            res = self.copie_suivi(reference_id)
            if res is not None:
                return res
            self.dormir(intervalle)
            ecoule += intervalle
        return None


def _texte(rep):
    try:
        return rep.text or ""
    except Exception:  # noqa: BLE001 - un corps illisible ne doit rien casser
        return ""
