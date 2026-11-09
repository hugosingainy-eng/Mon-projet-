"""Point d'entrée : python -m bot.main [options]

  (sans option)  boucle 24h/24
  --dry-run      simule sans passer d'ordre (fichier d'état séparé)
  --once         un seul cycle complet puis s'arrête
  --status       affiche l'état
  --stop         ferme les copies du bot (jamais les vôtres) et l'arrête
  --reset        réarme le bot après un arrêt
  --backtest     rejeu historique + Monte Carlo, sans aucun ordre
  --chat         discuter avec le bot dans le terminal
  --test-api     vérifie vos clés eToro (lecture seule)
"""
import argparse
import datetime as dt
import logging
import os
import sys
import time

from .config import ErreurConfig, charger_config, chemin_data
from .etat import Etat, lire_date, maintenant
from .journal import configurer_logs

log = logging.getLogger("main")


def construire(cfg, dry_run, api=None, outils=None, client_ia=None):
    """Assemble l'API, l'état et le Directeur."""
    from .agents.directeur import Directeur
    from .agents.renseignement import Outils
    from .etoro_client import EtoroClient
    from .ia import creer_client_ia
    sec = cfg["_secrets"]
    if api is None:
        api = EtoroClient(sec["ETORO_API_KEY"], sec["ETORO_USER_KEY"], cfg["mode"], cfg["api"])
    etat = Etat(chemin_data(cfg, "etat", dry_run))
    if outils is None:
        outils = Outils(cfg, os.path.join(cfg["fichiers"]["dossier_data"], "renseignement"))
    if client_ia is None:
        client_ia = creer_client_ia(cfg)
    return Directeur(api, cfg, etat, client_ia=client_ia, outils=outils, dry_run=dry_run,
                     chemin_rapport=chemin_data(cfg, "rapport"),
                     chemin_cache=os.path.join(cfg["fichiers"]["dossier_data"],
                                               "cache_13f.json"))


def selection_due(directeur, climat_change):
    if climat_change:
        return True
    derniere = lire_date(directeur.etat.data.get("derniere_selection"))
    jours = directeur.cfg["boucle"]["jours_entre_selections"]
    return derniere is None or maintenant() - derniere >= dt.timedelta(days=jours)


def analyse_due(directeur):
    b = directeur.cfg["boucle"]
    now = maintenant()
    derniere = directeur.etat.data.get("derniere_analyse_jour")
    if derniere is None:
        return True
    return derniere != now.date().isoformat() and now.hour >= b["heure_analyse_quotidienne_utc"]


def un_cycle(directeur, forcer_selection=False):
    """Un tour de boucle. Ne lève jamais : une erreur passagère est journalisée."""
    try:
        directeur.etat.prendre_reset_du_disque()
        directeur.cycle_controle()
        change = False
        if analyse_due(directeur):
            change = directeur.cycle_quotidien()
        if forcer_selection or selection_due(directeur, change):
            directeur.selection()
        return True
    except Exception:  # noqa: BLE001 - la boucle 24h/24 ne doit jamais planter
        log.exception("Erreur pendant le cycle (le bot continue)")
        try:
            directeur.etat.sauvegarder()
        except Exception:  # noqa: BLE001
            pass
        return False


def boucle(directeur, dossier_cmd, dormir=time.sleep, max_tours=None):
    from .chat import executer_commandes
    b = directeur.cfg["boucle"]
    tours = 0
    while max_tours is None or tours < max_tours:
        tours += 1
        ok = un_cycle(directeur)
        attente = b["controle_minutes"] * 60 if ok else b["pause_apres_erreur_secondes"]
        fin = time.monotonic() + attente
        while time.monotonic() < fin:
            try:
                executer_commandes(directeur, dossier_cmd)
            except Exception:  # noqa: BLE001
                log.exception("Commande du chat en échec")
            dormir(min(5, max(0.0, fin - time.monotonic())))
            if max_tours is not None:
                break


def afficher_statut(cfg, dry_run, sortie=print):
    from .chat import Chat
    chat = Chat(cfg, chemin_data(cfg, "etat", dry_run), chemin_data(cfg, "rapport"), "")
    sortie(chat.statut())


def tester_api(api, cfg, sortie=print):
    """Lecture seule : vérifie que les clés marchent et affiche les unités reçues."""
    from .donnees import mirrors, normaliser_trader
    ok = True
    sortie("Test de l'API eToro en mode %s (lecture seule, aucun ordre)" % cfg["mode"].upper())
    try:
        pf = api.portefeuille()
        sortie("✅ Portefeuille : OK (crédit %s, %d copie(s) en cours)" % (
            pf.get("credit"), len(mirrors(pf))))
    except Exception as exc:  # noqa: BLE001
        ok = False
        sortie("❌ Portefeuille : %s" % exc)
        sortie("   -> Vérifiez les deux clés, et que la clé est bien pour l'environnement "
               "%s." % ("DEMO" if cfg["mode"] == "demo" else "REAL"))
    try:
        lignes = api.classement(page=1, taille=5, periode=cfg["recruteur"]["periode"])
        sortie("✅ Classement : OK (%d traders lus)" % len(lignes))
        for l in lignes[:3]:
            t = normaliser_trader(l, cfg)
            sortie("   %s : gain brut=%r, chute brute=%r, mois gagnants bruts=%r" % (
                t["username"], l.get("gain"), l.get("peakToValley"),
                l.get("profitableMonthsPct")))
        if lignes:
            sortie("   Champs reçus : %s" % ", ".join(sorted(lignes[0].keys())))
    except Exception as exc:  # noqa: BLE001
        ok = False
        sortie("❌ Classement : %s" % exc)
    sortie("Résultat : %s" % ("les clés fonctionnent ✅" if ok else "problème ❌ (voir ci-dessus)"))
    return 0 if ok else 1


def main(argv=None, api=None, outils=None, client_ia=None, sortie=print):
    p = argparse.ArgumentParser(prog="python -m bot.main",
                                description="Bot de copy trading eToro (démo d'abord).")
    p.add_argument("--dry-run", action="store_true", help="simule sans passer d'ordre")
    p.add_argument("--once", action="store_true", help="un seul cycle complet")
    p.add_argument("--status", action="store_true", help="affiche l'état")
    p.add_argument("--stop", action="store_true", help="ferme les copies du bot")
    p.add_argument("--reset", action="store_true", help="réarme le bot après un arrêt")
    p.add_argument("--backtest", action="store_true", help="rejeu historique + Monte Carlo")
    p.add_argument("--chat", action="store_true", help="discuter avec le bot")
    p.add_argument("--test-api", action="store_true",
                   help="vérifie vos clés eToro (lecture seule, aucun ordre)")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--env", default=".env")
    a = p.parse_args(argv)

    try:
        cfg = charger_config(a.config, a.env)
    except ErreurConfig as exc:
        sortie("ERREUR DE CONFIGURATION : %s" % exc)
        return 2
    configurer_logs(chemin_data(cfg, "log"), console=not (a.status or a.chat))
    dossier_cmd = os.path.join(cfg["fichiers"]["dossier_data"], "commandes")
    log.info("Démarrage en mode %s%s", cfg["mode"].upper(), " (SIMULATION)" if a.dry_run else "")
    if cfg["mode"] == "real":
        log.warning("⚠️  ARGENT RÉEL : les deux verrous sont ouverts. Pertes possibles.")

    if a.status:
        afficher_statut(cfg, a.dry_run, sortie)
        return 0
    if a.reset:
        etat = Etat(chemin_data(cfg, "etat", a.dry_run))
        etat.reinitialiser_arret()
        etat.sauvegarder()
        from .chat import lire_commandes
        lire_commandes(dossier_cmd)  # oublie un ancien « stop » resté en attente
        sortie("Bot réarmé. La limite de perte de -5 % repart de zéro.")
        return 0
    if a.chat:
        from .chat import Chat, boucle_terminal
        from .ia import creer_client_ia
        chat = Chat(cfg, chemin_data(cfg, "etat", a.dry_run), chemin_data(cfg, "rapport"),
                    dossier_cmd, client_ia if client_ia is not None else creer_client_ia(cfg))
        boucle_terminal(chat, sortie=sortie)
        return 0

    sec = cfg["_secrets"]
    if api is None and not (sec["ETORO_API_KEY"] and sec["ETORO_USER_KEY"]):
        sortie("Clés eToro manquantes : copiez .env.example en .env et remplissez "
               "ETORO_API_KEY et ETORO_USER_KEY (voir README).")
        return 2

    if a.test_api:
        from .etoro_client import EtoroClient
        api = api or EtoroClient(sec["ETORO_API_KEY"], sec["ETORO_USER_KEY"], cfg["mode"],
                                 cfg["api"])
        return tester_api(api, cfg, sortie)

    if a.backtest:
        from .backtest import lancer_backtest
        from .etoro_client import EtoroClient
        api = api or EtoroClient(sec["ETORO_API_KEY"], sec["ETORO_USER_KEY"], cfg["mode"],
                                 cfg["api"])
        res = lancer_backtest(api, cfg, chemin_data(cfg, "backtest"))
        sortie("Backtest terminé : %s (gain total rejoué %+.1f %%)" % (
            chemin_data(cfg, "backtest"), 100 * res["rejeu"]["gain_total"]))
        return 0

    directeur = construire(cfg, a.dry_run, api, outils, client_ia)
    if a.stop:
        from .chat import deposer_commande
        # Si la boucle tourne déjà ailleurs, elle exécutera aussi cet arrêt.
        deposer_commande(dossier_cmd, "stop")
        directeur.synchroniser()
        directeur.fermer_tout("--stop")
        directeur.etat.declencher_arret("arrêt manuel (--stop)")
        directeur.etat.sauvegarder()
        sortie("Copies du bot fermées, bot arrêté. Relancez avec --reset.")
        return 0
    if a.once:
        ok = un_cycle(directeur, forcer_selection=True)
        sortie("Cycle terminé%s. Rapport : %s" % ("" if ok else " AVEC ERREUR (voir le log)",
                                                  chemin_data(cfg, "rapport")))
        return 0 if ok else 1

    # Boucle 24h/24 (+ Telegram si configuré)
    if cfg.get("chat", {}).get("telegram_actif") and sec.get("TELEGRAM_BOT_TOKEN") \
            and sec.get("TELEGRAM_CHAT_ID"):
        from .chat import Chat, Telegram
        chat = Chat(cfg, chemin_data(cfg, "etat", a.dry_run), chemin_data(cfg, "rapport"),
                    dossier_cmd, directeur.ia)
        Telegram(sec["TELEGRAM_BOT_TOKEN"], sec["TELEGRAM_CHAT_ID"], chat).demarrer()
        log.info("Telegram actif : vous pouvez parler au bot depuis votre téléphone")
    try:
        boucle(directeur, dossier_cmd)
    except KeyboardInterrupt:
        log.info("Arrêt demandé au clavier. Les copies restent ouvertes chez eToro.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
