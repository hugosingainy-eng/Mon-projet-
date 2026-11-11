"""Capital.com : connexion, sécurité, décision, commandes (faux serveur, sans réseau)."""
import os

import pytest

from bot.capital.client import ClientCapital, ErreurCapital
from bot.config import charger_config
from bot.etat import Etat
from bot.main import main
from bot.mt5.directeur import DirecteurMT5
from conftest import RACINE
from faux_capital import FauxCapital

SECRETS = {"CAPITAL_API_KEY": "cle", "CAPITAL_IDENTIFIER": "moi@exemple.fr",
           "CAPITAL_PASSWORD": "secret"}


@pytest.fixture
def cfgc(tmp_path):
    c = charger_config(os.path.join(RACINE, "config.yaml"), None, environ=SECRETS)
    assert c["plateforme"] == "capital"
    c["fichiers"]["dossier_data"] = str(tmp_path / "data")
    return c


def client(cfgc, faux):
    c = ClientCapital(cfgc, session=faux)
    c.dormir = lambda s: None
    return c


def directeur(cfgc, tmp_path, faux=None, dry_run=False):
    faux = faux or FauxCapital()
    d = DirecteurMT5(client(cfgc, faux), cfgc, Etat(str(tmp_path / "e.json")), dry_run=dry_run,
                     chemin_rapport=str(tmp_path / "r.md"))
    return d, faux


def test_connexion_demo_et_jetons(cfgc):
    faux = FauxCapital()
    c = client(cfgc, faux)
    c.connecter()
    assert "demo-api-capital" in faux.url and faux.sessions == 1
    assert c.compte()["balance"] == 10000.0
    faux.expirer_session = True                 # session expirée après 10 min
    c.compte()
    assert faux.sessions == 2                   # reconnexion automatique


def test_mauvais_mot_de_passe(cfgc):
    cfgc["_secrets"]["CAPITAL_PASSWORD"] = "faux"
    with pytest.raises(ErreurCapital, match="refusée"):
        client(cfgc, FauxCapital()).connecter()


def test_identifiants_manquants(cfgc):
    cfgc["_secrets"]["CAPITAL_API_KEY"] = ""
    with pytest.raises(ErreurCapital, match="manquants"):
        client(cfgc, FauxCapital()).connecter()


def test_bougies_et_conversion_devise(cfgc):
    c = client(cfgc, FauxCapital())
    c.connecter()
    b = c.bougies("US500", 300)
    assert len(b) == 300 and b[0][0] < b[-1][0]
    # 1 point de US500 (USD) vaut 1 / EURUSD en euros
    bid, ask = c.prix("EURUSD")
    assert abs(c.valeur_mouvement("US500", 1, 100, 101) - 1 / ((bid + ask) / 2)) < 1e-9


def test_decision_complete(cfgc, tmp_path):
    d, faux = directeur(cfgc, tmp_path)
    r = d.selection()
    assert r["feu_vert"] and r["plateforme"] == "Capital.com"
    assert all(o["nb_simulations"] >= 10000 for o in r["simulateur"])
    assert 1 <= len(faux.ordres) <= 3
    for o in faux.ordres:
        assert o["direction"] == "BUY" and o["stopLevel"] > 0            # toujours un stop
    assert set(d.etat.copies_ouvertes()) == set(faux.positions)
    d.selection()
    assert len(faux.ordres) == len(d.etat.copies_ouvertes())             # pas de doublon


def test_positions_personnelles(cfgc, tmp_path):
    faux = FauxCapital()
    perso = faux.position_perso("US500")
    d, _ = directeur(cfgc, tmp_path, faux)
    r = d.selection()
    assert all(o["epic"] != "US500" for o in faux.ordres)
    assert any("position à vous" in x["raison"] for x in r["rejets"])
    d.arret_urgence("test")
    assert perso in faux.positions and perso not in faux.fermetures
    with pytest.raises(ErreurCapital):
        d.client.fermer({"ticket": perso})


def test_arret_moins_5(cfgc, tmp_path):
    d, faux = directeur(cfgc, tmp_path)
    d.selection()
    deals = list(faux.positions)
    for deal in deals:
        # upl en USD, converti en EUR (~ /1.0) : -600 au total sur 10 000
        faux.fixer_upl(deal, -600 / len(deals))
    d.cycle_controle()
    assert d.etat.arret_actif and faux.positions == {}


def test_stop_touche_estimation_prudente(cfgc, tmp_path):
    d, faux = directeur(cfgc, tmp_path)
    d.selection()
    deal = next(iter(faux.positions))
    c = d.etat.copies[deal]
    faux.toucher_stop(deal)
    d.cycle_controle()
    attendu = d.client.valeur_mouvement(c["symbole"], c["volume"], c["prix_entree"], c["stop"])
    assert not d.etat.copies[deal]["ouverte"]
    assert abs(d.etat.copies[deal]["resultat"] - attendu) < 1e-6 and attendu < 0


def test_solde_plus_petit_que_le_budget(cfgc, tmp_path):
    d, faux = directeur(cfgc, tmp_path, FauxCapital(solde=1000.0))
    r = d.selection()
    assert r["budget"]["capital"] == 1000.0
    expose = sum(c["investi"] for c in d.etat.copies_ouvertes().values())
    assert expose <= 1000.0 + 1e-6


def config(tmp_path, demo=True):
    conf = tmp_path / "config.yaml"
    texte = open(os.path.join(RACINE, "config.yaml"), encoding="utf-8").read()
    texte = texte.replace("dossier_data: data", "dossier_data: %s" % (tmp_path / "data"))
    conf.write_text(texte, encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("".join("%s=%s\n" % kv for kv in SECRETS.items()), encoding="utf-8")
    return ["--config", str(conf), "--env", str(env)]


def test_commandes_capital(tmp_path):
    faux = FauxCapital()
    sorties = []

    def lancer(*args):
        sorties.clear()
        code = main(list(args) + config(tmp_path), capital_session=faux, sortie=sorties.append)
        return code, "\n".join(sorties)
    code, txt = lancer("--test-api")
    assert code == 0 and "Capital.com" in txt and "US500 -> US500" in txt and faux.ordres == []
    code, txt = lancer("--dry-run", "--once")
    assert code == 0 and faux.ordres == []
    assert (tmp_path / "data" / "capital_etat_dry_run.json").exists()
    code, _ = lancer("--backtest")
    assert code == 0 and (tmp_path / "data" / "capital_backtest.md").exists()
    assert faux.ordres == []
    code, _ = lancer("--once")
    assert code == 0 and len(faux.ordres) >= 1
    perso = faux.position_perso("GOLD")
    lancer("--stop")
    assert list(faux.positions) == [perso]
    _, txt = lancer("--status")
    assert "ARRÊT" in txt


def test_mauvais_identifiants_message_clair(tmp_path):
    faux = FauxCapital()
    args = config(tmp_path)
    (tmp_path / ".env").write_text("CAPITAL_API_KEY=x\nCAPITAL_IDENTIFIER=y\nCAPITAL_PASSWORD=z\n",
                                   encoding="utf-8")
    sorties = []
    assert main(["--test-api"] + args, capital_session=faux, sortie=sorties.append) == 1
    assert "refusée" in "\n".join(sorties) or "Connexion" in "\n".join(sorties)
