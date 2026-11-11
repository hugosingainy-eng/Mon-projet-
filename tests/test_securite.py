"""Sentinelle, arrêt à -5 %, copies fermées hors du bot, verrou argent réel."""
import pytest

from bot import securite
from bot.config import ErreurConfig, charger_config
from conftest import RACINE
import os


def ouvrir(directeur, aujourd_hui):
    directeur.selection(aujourd_hui)
    return directeur.etat.copies_ouvertes()


def test_sentinelle_coupe_et_bannit(directeur, api, aujourd_hui):
    copies = ouvrir(directeur, aujourd_hui)
    mid, c = next(iter(copies.items()))
    api.fixer_valeur(mid, 200 * 0.91)          # -9 % sur cette copie
    directeur.cycle_controle()
    assert not directeur.etat.copies[mid]["ouverte"]
    assert int(mid) not in api.mirrors
    assert directeur.etat.est_banni(c["username"])
    # Banni : il n'est plus recruté à la sélection suivante
    directeur.selection(aujourd_hui)
    assert c["username"] not in [x["username"] for x in directeur.etat.copies_ouvertes().values()]


def test_sentinelle_ne_coupe_pas_a_moins_7(directeur, api, aujourd_hui):
    copies = ouvrir(directeur, aujourd_hui)
    mid = next(iter(copies))
    api.fixer_valeur(mid, 200 * 0.93)
    directeur.cycle_controle()
    assert directeur.etat.copies[mid]["ouverte"]


def test_sentinelle_changement_de_comportement(directeur, api, aujourd_hui):
    copies = ouvrir(directeur, aujourd_hui)
    noms = [c["username"] for c in copies.values()]
    api.traders[noms[0]]["tradeinfo"]["riskScore"] = 6          # > 4 + 1
    api.traders[noms[1]]["positions"] = [
        {"instrumentId": 1, "investmentPct": 100, "isBuy": True, "leverage": 3}]  # levier x3
    api.traders[noms[2]]["daily"][aujourd_hui.isoformat()] = -7.0  # -7 % aujourd'hui
    from bot.agents import sentinelle
    decisions = sentinelle.controle_comportement(api, directeur.etat, directeur.cfg, aujourd_hui)
    raisons = {d["username"]: d["raison"] for d in decisions}
    assert "risque" in raisons[noms[0]]
    assert "levier" in raisons[noms[1]]
    assert "chute" in raisons[noms[2]]


def test_arret_a_moins_5_pourcent(directeur, api, aujourd_hui):
    copies = ouvrir(directeur, aujourd_hui)
    # chaque copie perd 5,5 % -> -33 $ au total = -5,5 % du budget (Sentinelle à -8 % ne bouge pas)
    for mid in copies:
        api.fixer_valeur(mid, 200 * 0.945)
    directeur.cycle_controle()
    assert directeur.etat.arret_actif
    assert directeur.etat.copies_ouvertes() == {}
    assert api.mirrors == {}
    # Tant qu'on n'a pas fait --reset, plus rien ne se passe
    nb = len(api.appels)
    directeur.cycle_controle()
    assert directeur.selection(aujourd_hui) is None
    assert len(api.appels) == nb
    with pytest.raises(securite.RefusSecurite):
        securite.verifier_ajout(directeur.cfg, directeur.etat, 10)
    directeur.etat.reinitialiser_arret()
    assert not directeur.etat.arret_actif


def test_perte_juste_sous_la_limite(directeur, api, aujourd_hui):
    copies = ouvrir(directeur, aujourd_hui)
    for mid in copies:
        api.fixer_valeur(mid, 200 * 0.96)   # -24 $ = -4 %
    directeur.cycle_controle()
    assert not directeur.etat.arret_actif


def test_copie_fermee_hors_du_bot_compte_dans_les_pertes(directeur, api, aujourd_hui):
    copies = ouvrir(directeur, aujourd_hui)
    m1, m2, m3 = list(copies)
    api.fixer_valeur(m1, 180.0)              # -20 $
    directeur.cycle_controle()               # la Sentinelle coupe (-10 %)
    api.fixer_valeur(m2, 186.0)              # -14 $ (dernière valeur connue)
    directeur.synchroniser()
    del api.mirrors[int(m2)]                 # vous fermez la copie dans l'appli eToro
    directeur.cycle_controle()
    e = directeur.etat
    assert not e.copies[m2]["ouverte"]
    assert e.copies[m2]["raison_fermeture"] == "fermée hors du bot"
    assert abs(e.data["pnl_realise"] - (-34.0)) < 0.01   # -20 -14 : la perte reste comptée
    # Encore une perte et l'arrêt -5 % (30 $) est atteint : la perte -34 $ suffit déjà
    assert e.arret_actif


def test_le_bot_refuse_de_fermer_une_copie_qui_n_est_pas_a_lui(directeur, api):
    perso = api.ajouter_mirror_perso(999)
    with pytest.raises(securite.RefusSecurite):
        directeur.fermer(str(perso), "test")
    with pytest.raises(securite.RefusSecurite):
        directeur.ajuster(str(perso), -50)
    assert perso in api.mirrors


def test_budget_jamais_depasse(directeur, aujourd_hui):
    ouvrir(directeur, aujourd_hui)
    with pytest.raises(securite.RefusSecurite):
        securite.verifier_ajout(directeur.cfg, directeur.etat, 1)


def test_perte_max_plafonnee_a_5_pourcent(cfg):
    cfg["securite"]["perte_max_pct"] = 0.5
    assert securite.perte_max(cfg) == 0.05


def test_nb_et_part():
    assert securite.nb_et_part(600, 3, 200) == (3, 200)
    assert securite.nb_et_part(420, 3, 200) == (2, 210)
    assert securite.nb_et_part(240, 3, 200) == (1, 240)
    assert securite.nb_et_part(150, 3, 200) == (0, 0.0)


def test_double_verrou_argent_reel(tmp_path):
    conf = tmp_path / "c.yaml"
    conf.write_text(open(os.path.join(RACINE, "config.yaml"), encoding="utf-8").read()
                    .replace("\nmode: demo", "\nmode: real"), encoding="utf-8")
    with pytest.raises(ErreurConfig):
        charger_config(str(conf), None, environ={})
    with pytest.raises(ErreurConfig):
        charger_config(str(conf), None, environ={"I_ACCEPT_REAL_MONEY_RISK": "non"})
    env = tmp_path / ".env"
    env.write_text("I_ACCEPT_REAL_MONEY_RISK=oui\n", encoding="utf-8")
    assert charger_config(str(conf), str(env), environ={})["mode"] == "real"
    # Le verrou .env seul ne suffit pas à passer en réel
    assert charger_config(os.path.join(RACINE, "config.yaml"), str(env),
                          environ={})["mode"] == "demo"


def test_stress_reduit_les_copies(directeur, api, aujourd_hui):
    ouvrir(directeur, aujourd_hui)
    clot = directeur.etat.data["marche"]["clotures"]
    api.cours_actuels = {"SPX500": clot["SPX500"] * 0.96, "NSDQ100": clot["NSDQ100"]}
    directeur.cycle_controle()
    assert directeur.etat.data["climat"] == "stress"
    copies = directeur.etat.copies_ouvertes()
    assert len(copies) == 1                       # 40 % de 600 $ = 240 $ -> un seul trader
    assert sum(c["investi"] for c in copies.values()) <= 240.01
