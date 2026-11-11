"""Connexion à MetaTrader 5 (MT5).

Le module Python officiel `MetaTrader5` (de MetaQuotes) pilote le logiciel
MetaTrader 5 installé sur le MÊME ordinateur Windows. Il faut donc :
  1. installer MetaTrader 5 (Windows) et ouvrir un compte DÉMO chez un courtier ;
  2. laisser MetaTrader 5 ouvert pendant que le bot tourne ;
  3. cocher « Autoriser le trading algorithmique » dans MetaTrader 5.

Sur Linux/Mac, on peut utiliser le pont `mt5linux` (MetaTrader 5 tourne sous
Wine) : mettre `mt5.connexion: mt5linux` dans config.yaml.

SÉCURITÉ : le bot ne touche QUE les positions qui portent son numéro
« magic ». Vos positions manuelles ne sont jamais modifiées ni fermées.
Il refuse de démarrer si config.yaml dit « demo » mais que le compte MT5
connecté est un compte RÉEL.
"""
import datetime as dt
import logging

log = logging.getLogger("mt5")

# Valeurs des constantes MetaTrader 5 (identiques dans le module officiel)
TIMEFRAME_D1 = 16408
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
TRADE_ACTION_DEAL = 1
TRADE_ACTION_SLTP = 6
ORDER_TIME_GTC = 0
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2
TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_PLACED = 10008
ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_TRADE_MODE_CONTEST = 1
ACCOUNT_TRADE_MODE_REAL = 2
POSITION_TYPE_BUY = 0


class ErreurMT5(Exception):
    pass


def charger_module(cfg_mt5):
    """Importe le module officiel (Windows) ou le pont mt5linux."""
    connexion = cfg_mt5.get("connexion", "direct")
    if connexion == "mt5linux":
        try:
            from mt5linux import MetaTrader5  # type: ignore
        except ImportError as exc:
            raise ErreurMT5("Le paquet 'mt5linux' n'est pas installé (pip install mt5linux)") from exc
        return MetaTrader5(host=cfg_mt5.get("hote", "localhost"),
                           port=int(cfg_mt5.get("port", 18812)))
    try:
        import MetaTrader5 as module  # type: ignore
    except ImportError as exc:
        raise ErreurMT5(
            "Le module Python 'MetaTrader5' est introuvable. Il ne fonctionne que sous "
            "Windows : pip install MetaTrader5 (voir README, section MetaTrader 5).") from exc
    return module


def _dict(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "_asdict"):
        return obj._asdict()
    return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}


class ClientMT5:
    def __init__(self, cfg, module=None):
        self.cfg = cfg
        self.cm = cfg.get("mt5", {})
        self.sec = cfg.get("_secrets", {})
        self.m = module
        self.magic = int(self.cm.get("magic", 20261111))
        self.connecte = False
        self._symboles = {}

    # --- connexion ------------------------------------------------------
    def connecter(self):
        if self.connecte:
            return True
        if self.m is None:
            self.m = charger_module(self.cm)
        args = {}
        if self.sec.get("MT5_PATH"):
            args["path"] = self.sec["MT5_PATH"]
        if self.sec.get("MT5_LOGIN"):
            args.update(login=int(self.sec["MT5_LOGIN"]), password=self.sec.get("MT5_PASSWORD", ""),
                        server=self.sec.get("MT5_SERVER", ""))
        args["timeout"] = int(self.cm.get("timeout_ms", 60000))
        if not self.m.initialize(**args):
            raise ErreurMT5("Connexion à MetaTrader 5 impossible (%s). MetaTrader 5 est-il "
                            "ouvert et connecté à votre compte démo ?" % (self.m.last_error(),))
        compte = self.compte()
        mode_compte = compte.get("trade_mode")
        if self.cfg.get("mode", "demo") == "demo" and mode_compte == ACCOUNT_TRADE_MODE_REAL:
            self.m.shutdown()
            raise ErreurMT5("SÉCURITÉ : config.yaml est en mode DÉMO mais le compte MetaTrader 5 "
                            "connecté est un compte RÉEL. Connectez-vous à un compte démo.")
        if self.cfg.get("mode") == "real" and mode_compte != ACCOUNT_TRADE_MODE_REAL:
            log.warning("Mode 'real' demandé, mais le compte MT5 est un compte démo.")
        info_terminal = _dict(self.m.terminal_info()) or {}
        if info_terminal and not info_terminal.get("trade_allowed", True):
            log.warning("Le trading algorithmique est désactivé dans MetaTrader 5 : cliquez sur "
                        "le bouton « Trading algorithmique » (Algo Trading) dans la barre d'outils.")
        self.connecte = True
        log.info("Connecté à MetaTrader 5 : compte %s (%s), serveur %s", compte.get("login"),
                 "DÉMO" if mode_compte != ACCOUNT_TRADE_MODE_REAL else "RÉEL",
                 compte.get("server"))
        return True

    def compte(self):
        c = _dict(self.m.account_info())
        if not c:
            raise ErreurMT5("Informations du compte indisponibles (%s)" % (self.m.last_error(),))
        return c

    def est_demo(self):
        return self.compte().get("trade_mode") != ACCOUNT_TRADE_MODE_REAL

    # --- symboles -------------------------------------------------------
    def resoudre(self, nom):
        """Trouve le vrai nom du symbole chez le courtier (US500, US500.cash, SP500…)."""
        if nom in self._symboles:
            return self._symboles[nom]
        candidats = [nom] + list(self.cm.get("alias", {}).get(nom, []))
        tous = [s.name for s in (self.m.symbols_get() or [])]
        trouve = None
        for c in candidats:
            if c in tous:
                trouve = c
                break
        if trouve is None:
            for c in candidats:
                proches = sorted(s for s in tous if s.upper().startswith(c.upper()))
                if proches:
                    trouve = proches[0]
                    break
        if trouve:
            self.m.symbol_select(trouve, True)
        self._symboles[nom] = trouve
        return trouve

    def infos(self, symbole):
        self.m.symbol_select(symbole, True)
        i = _dict(self.m.symbol_info(symbole))
        if not i:
            raise ErreurMT5("Symbole %s inconnu chez ce courtier" % symbole)
        return i

    def bougies(self, symbole, nb=400):
        """Liste de (date, ouverture, haut, bas, clôture) du plus ancien au plus récent."""
        tf = getattr(self.m, "TIMEFRAME_D1", TIMEFRAME_D1)
        rates = self.m.copy_rates_from_pos(symbole, tf, 0, int(nb))
        if rates is None or len(rates) == 0:
            raise ErreurMT5("Pas d'historique pour %s (%s)" % (symbole, self.m.last_error()))
        out = []
        for r in rates:
            jour = dt.datetime.fromtimestamp(int(r["time"]), dt.timezone.utc).date()
            out.append((jour, float(r["open"]), float(r["high"]), float(r["low"]),
                        float(r["close"])))
        return out

    def prix(self, symbole):
        t = _dict(self.m.symbol_info_tick(symbole))
        if not t or not t.get("bid"):
            raise ErreurMT5("Pas de prix pour %s (marché fermé ?)" % symbole)
        return float(t["bid"]), float(t["ask"])

    def valeur_mouvement(self, symbole, volume, prix_depart, prix_arrivee):
        """Gain (ou perte) en devise du compte pour une position acheteuse."""
        v = self.m.order_calc_profit(ORDER_TYPE_BUY, symbole, float(volume), float(prix_depart),
                                     float(prix_arrivee))
        if v is None:
            raise ErreurMT5("Calcul impossible pour %s (%s)" % (symbole, self.m.last_error()))
        return float(v)

    def notionnel_par_lot(self, symbole, prix):
        """Valeur exposée d'1 lot, en devise du compte (sans levier)."""
        return abs(self.valeur_mouvement(symbole, 1.0, prix, prix * 1.01)) * 100

    # --- positions --------------------------------------------------------
    def positions(self):
        return [_dict(p) for p in (self.m.positions_get() or [])]

    def positions_du_bot(self):
        return [p for p in self.positions() if int(p.get("magic", 0)) == self.magic]

    def _remplissage(self, symbole):
        mode = int(self.infos(symbole).get("filling_mode", 0))
        if mode & 1:
            return getattr(self.m, "ORDER_FILLING_FOK", ORDER_FILLING_FOK)
        if mode & 2:
            return getattr(self.m, "ORDER_FILLING_IOC", ORDER_FILLING_IOC)
        return getattr(self.m, "ORDER_FILLING_RETURN", ORDER_FILLING_RETURN)

    def _envoyer(self, requete, verifier_seulement=False):
        if verifier_seulement:
            res = _dict(self.m.order_check(requete))
            if not res or int(res.get("retcode", -1)) not in (0, TRADE_RETCODE_DONE):
                raise ErreurMT5("Ordre refusé par la vérification : %s" % (
                    (res or {}).get("comment") or self.m.last_error(),))
            return res
        res = _dict(self.m.order_send(requete))
        if not res or int(res.get("retcode", -1)) not in (TRADE_RETCODE_DONE,
                                                          TRADE_RETCODE_PLACED):
            raise ErreurMT5("Ordre refusé par MetaTrader 5 : %s (code %s)" % (
                (res or {}).get("comment") or self.m.last_error(), (res or {}).get("retcode")))
        return res

    def acheter(self, symbole, volume, stop_loss, commentaire="bot", verifier_seulement=False):
        _, ask = self.prix(symbole)
        requete = {
            "action": getattr(self.m, "TRADE_ACTION_DEAL", TRADE_ACTION_DEAL),
            "symbol": symbole, "volume": float(volume),
            "type": getattr(self.m, "ORDER_TYPE_BUY", ORDER_TYPE_BUY),
            "price": ask, "sl": float(stop_loss), "tp": 0.0, "deviation": 20,
            "magic": self.magic, "comment": commentaire[:25],
            "type_time": getattr(self.m, "ORDER_TIME_GTC", ORDER_TIME_GTC),
            "type_filling": self._remplissage(symbole),
        }
        return self._envoyer(requete, verifier_seulement)

    def fermer(self, position):
        """Ferme une position du bot (refuse toute position sans notre magic)."""
        if int(position.get("magic", 0)) != self.magic:
            raise ErreurMT5("SÉCURITÉ : la position %s n'appartient pas au bot" %
                            position.get("ticket"))
        symbole = position["symbol"]
        bid, ask = self.prix(symbole)
        achat = int(position.get("type", 0)) == POSITION_TYPE_BUY
        requete = {
            "action": getattr(self.m, "TRADE_ACTION_DEAL", TRADE_ACTION_DEAL),
            "symbol": symbole, "volume": float(position["volume"]),
            "type": getattr(self.m, "ORDER_TYPE_SELL" if achat else "ORDER_TYPE_BUY",
                            ORDER_TYPE_SELL if achat else ORDER_TYPE_BUY),
            "position": int(position["ticket"]), "price": bid if achat else ask,
            "deviation": 20, "magic": self.magic, "comment": "bot fermeture",
            "type_time": getattr(self.m, "ORDER_TIME_GTC", ORDER_TIME_GTC),
            "type_filling": self._remplissage(symbole),
        }
        return self._envoyer(requete)

    def profit_realise(self, ticket):
        """Résultat final d'une position fermée (stop-loss touché, fermée à la main…)."""
        deals = self.m.history_deals_get(position=int(ticket))
        if not deals:
            return None
        total = 0.0
        for d in deals:
            d = _dict(d)
            total += float(d.get("profit", 0)) + float(d.get("commission", 0)) + float(
                d.get("swap", 0)) + float(d.get("fee", 0) or 0)
        return total
