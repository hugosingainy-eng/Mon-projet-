"""Commandes --once, --status, --stop, --reset, --dry-run, et le chat."""
import os

from bot.chat import Chat, Telegram, deposer_commande, executer_commandes, lire_commandes
from bot.main import main, un_cycle
from conftest import RACINE, bons_traders
from fausse_api import FausseAPI, FauxOutils


def config(tmp_path):
    conf = tmp_path / "config.yaml"
    texte = open(os.path.join(RACINE, "config.yaml"), encoding="utf-8").read()
    texte = texte.replace("dossier_data: data", "dossier_data: %s" % (tmp_path / "data"))
    texte = texte.replace("nb_simulations: 10000", "nb_simulations: 1000")
    conf.write_text(texte, encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("ETORO_API_KEY=a\nETORO_USER_KEY=b\n", encoding="utf-8")
    return ["--config", str(conf), "--env", str(env)]


def lancer(tmp_path, api, *args):
    sorties = []
    code = main(list(args) + config(tmp_path), api=api, outils=FauxOutils(), client_ia=None,
                sortie=sorties.append)
    return code, "\n".join(sorties)


def test_once_status_stop_reset(tmp_path):
    api = FausseAPI(bons_traders())
    code, _ = lancer(tmp_path, api, "--once")
    assert code == 0 and len(api.mirrors) == 3
    code, txt = lancer(tmp_path, api, "--status")
    assert "investi 200.00 $" in txt
    perso = api.ajouter_mirror_perso(4242)
    code, txt = lancer(tmp_path, api, "--stop")
    assert list(api.mirrors) == [perso]            # seule votre copie reste
    _, txt = lancer(tmp_path, api, "--status")
    assert "ARRÊT" in txt
    _, txt = lancer(tmp_path, api, "--once")
    assert list(api.mirrors) == [perso]            # arrêté : rien ne bouge
    lancer(tmp_path, api, "--reset")
    lancer(tmp_path, api, "--once")
    assert len(api.mirrors) == 4


def test_dry_run_once(tmp_path):
    api = FausseAPI(bons_traders())
    code, _ = lancer(tmp_path, api, "--dry-run", "--once")
    assert code == 0 and api.appels_ordres() == [] and api.mirrors == {}
    assert (tmp_path / "data" / "etat_dry_run.json").exists()
    assert not (tmp_path / "data" / "etat.json").exists()
    _, txt = lancer(tmp_path, api, "--status", "--dry-run")
    assert "investi 200.00 $" in txt


def test_cles_manquantes(tmp_path):
    args = config(tmp_path)
    (tmp_path / ".env").write_text("", encoding="utf-8")
    sorties = []
    assert main(["--once"] + args, sortie=sorties.append) == 2
    assert "Clés eToro manquantes" in sorties[0]


def test_erreur_passagere_ne_plante_pas_la_boucle(directeur, api):
    def panne():
        raise ConnectionError("réseau coupé")
    api.portefeuille = panne
    assert un_cycle(directeur) is False      # erreur journalisée, pas d'exception


def test_chat(tmp_path, directeur, aujourd_hui):
    directeur.selection(aujourd_hui)
    dossier = str(tmp_path / "cmd")
    chat = Chat(directeur.cfg, directeur.etat.chemin, directeur.chemin_rapport, dossier)
    assert "investi 200.00 $" in chat.repondre("Comment vont mes copies ?")
    assert "Je ne peux pas" in chat.repondre("augmente le budget à 5000")
    assert "Je ne peux pas" in chat.repondre("passe en argent réel")
    assert lire_commandes(dossier) == []
    assert "Répondez « oui »" in chat.repondre("arrête tout")
    assert "annulé" in chat.repondre("non")
    assert lire_commandes(dossier) == []
    chat.repondre("stop")
    chat.repondre("oui")
    chat.repondre("pause")
    executer_commandes(directeur, dossier)
    assert directeur.etat.arret_actif and directeur.etat.copies_ouvertes() == {}
    assert directeur.etat.data["pause"]


def test_commandes_inconnues_refusees(directeur, tmp_path):
    dossier = str(tmp_path / "cmd")
    deposer_commande(dossier, "augmenter_budget", montant=99999)
    deposer_commande(dossier, "reset")
    executer_commandes(directeur, dossier)
    assert directeur.cfg["budget"] == 600 and not directeur.etat.arret_actif


def test_telegram_ne_repond_qu_au_proprietaire(tmp_path, directeur):
    class Session:
        def __init__(self):
            self.envois = []

        def post(self, url, json=None, timeout=None):
            self.envois.append(json)
    chat = Chat(directeur.cfg, directeur.etat.chemin, directeur.chemin_rapport,
                str(tmp_path / "cmd"))
    s = Session()
    tg = Telegram("TOKEN", "123", chat, session=s)
    assert tg.traiter({"message": {"chat": {"id": 999}, "text": "stop"}}) is None
    assert s.envois == []
    assert "Mode" in tg.traiter({"message": {"chat": {"id": 123}, "text": "statut"}})
    assert s.envois[0]["chat_id"] == "123"
