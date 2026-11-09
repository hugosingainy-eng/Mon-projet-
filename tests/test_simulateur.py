"""Monte Carlo, feu vert et mise réduite."""
import numpy as np

from bot.agents import simulateur


def matrice(moyenne, ecart, jours=504, n=3, graine=1):
    rng = np.random.default_rng(graine)
    return rng.normal(moyenne, ecart, size=(jours, n))


def stats(m, montants=(200, 200, 200), budget=600, cfg=None):
    cfg = cfg or {"nb_simulations": 4000, "jours": 63, "taille_bloc": 20, "graine": 3}
    return simulateur.simuler(m, list(montants), budget, cfg, 0.05)


def test_bonne_contre_mauvaise_strategie():
    bonne = stats(matrice(0.0008, 0.004))
    mauvaise = stats(matrice(-0.0008, 0.012))
    assert bonne["chance_gain"] > 0.8 and bonne["risque_arret"] < 0.05
    assert mauvaise["chance_gain"] < 0.4 and mauvaise["risque_arret"] > 0.4
    assert bonne["pire_5"] <= bonne["mediane"] <= bonne["meilleur_5"]


def test_exposition_reduite_moins_d_arrets():
    m = matrice(0.0003, 0.012)
    plein = stats(m, (200, 200, 200))
    moitie = stats(m, (100, 100, 100))
    assert moitie["risque_arret"] < plein["risque_arret"]


def test_arret_applique_dans_les_simulations():
    m = np.full((100, 1), -0.01)      # -1 % par jour, toujours
    s = stats(m, (600,))
    assert s["risque_arret"] == 1.0
    assert s["pire_5"] >= -0.07       # on s'arrête vers -5 %, pas -47 %


def test_blocs_alignes_sur_les_memes_dates():
    # deux traders parfaitement opposés : ensemble, ils ne bougent pas
    r = np.random.default_rng(0).normal(0, 0.02, size=(300, 1))
    m = np.hstack([r, -r])
    s = stats(m, (300, 300))
    assert s["risque_arret"] < 0.2


def test_feu_vert_puis_mise_reduite(cfg):
    cfg["simulateur"]["nb_simulations"] = 3000
    # stratégie qui gagne en moyenne mais est trop volatile à pleine mise
    m = matrice(0.0025, 0.025)
    usernames = ["a", "b", "c"]
    mise, alloc, essais = simulateur.decider(
        m, lambda x: {u: 200 * x for u in usernames}, 600, cfg, usernames)
    assert essais[0]["feu_vert"] is False
    assert mise == 0.5
    assert all(abs(v - 200 * mise) < 1e-9 for v in alloc.values())


def test_feu_rouge(cfg):
    cfg["simulateur"]["nb_simulations"] = 2000
    m = matrice(-0.002, 0.01)
    mise, alloc, essais = simulateur.decider(m, lambda x: {"a": 200 * x, "b": 200 * x},
                                             600, cfg, ["a", "b"])
    assert mise is None and alloc == {} and len(essais) == 3


def test_aligner_dates():
    import datetime as dt
    d1, d2, d3 = (dt.date(2026, 1, i) for i in (1, 2, 3))
    m, dates = simulateur.aligner({"a": {d1: 0.01, d2: 0.02}, "b": {d2: -0.01, d3: 0.03}},
                                  ["a", "b"])
    assert dates == [d1, d2, d3]
    assert m.tolist() == [[0.01, 0.0], [0.02, -0.01], [0.0, 0.03]]


def test_historique_trop_court():
    s = stats(np.zeros((5, 3)))
    assert s["valide"] is False
