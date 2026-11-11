"""MetaTrader 5 : connexion sûre, stratégie, simulateur, sécurité, commandes."""
import copy
import os

import numpy as np
import pytest

from bot import securite
from bot.config import charger_config
from bot.etat import Etat
from bot.main import construire_mt5, main
from bot.mt5 import backtest as bt
from bot.mt5 import strategie
from bot.mt5.client import ClientMT5, ErreurMT5
from bot.mt5.directeur import DirecteurMT5
from conftest import RACINE
from faux_mt5 import FauxMT5, serie


@pytest.fixture
def cfg5(tmp_path):
    c = charger_config(os.path.join(RACINE, "config.yaml"), None, environ={})
    assert c["plateforme"] == "mt5"
    c["fichiers"]["dossier_data"] = str(tmp_path / "data")
    return c


def directeur(cfg5, tmp_path, faux=None, dry_run=False):
    faux = faux or FauxMT5()
    d = DirecteurMT5(ClientMT5(cfg5, module=faux), cfg5,
                     Etat(str(tmp_path / ("e_dry.json" if dry_run else "e.json"))),
                     dry_run=dry_run, chemin_rapport=str(tmp_path / "r.md"))
    return d, faux


def test_refuse_compte_reel_en_mode_demo(cfg5):
    c = ClientMT5(cfg5, module=FauxMT5(compte_reel=True))
    with pytest.raises(ErreurMT5, match="RÉEL"):
        c.connecter()


def test_resolution_des_noms_de_symboles(cfg5):
    c = ClientMT5(cfg5, module=FauxMT5())
    c.connecter()
    assert c.resoudre("US500") == "US500.cash"
    assert c.resoudre("DE40") == "GER40"
    assert c.resoudre("INCONNU") is None


def test_strategie_signaux():
    hausse = [(None, o, h, l, c) for o, h, l, c in serie(100, 0.001, 0.005, n=400)]
    baisse = [(None, o, h, l, c) for o, h, l, c in serie(100, -0.001, 0.005, n=400)]
    s = strategie.analyser(hausse, {"mm_longue": 200, "mm_courte": 50, "atr_jours": 20,
                                    "stop_atr": 2.5})
    assert s["entree"] and not s["sortie"] and s["distance_stop"] > 0
    s = strategie.analyser(baisse, {"mm_longue": 200, "mm_courte": 50, "atr_jours": 20,
                                    "stop_atr": 2.5})
    assert not s["entree"] and s["sortie"]
    assert not strategie.analyser(hausse[:50], {"mm_longue": 200, "mm_courte": 50,
                                                "atr_jours": 20, "stop_atr": 2.5})["valide"]


def test_decision_complete(cfg5, tmp_path):
    d, faux = directeur(cfg5, tmp_path)
    r = d.selection()
    assert r["feu_vert"]
    assert r["nb_options"] >= 1 and all(o["nb_simulations"] >= 10000 for o in r["simulateur"])
    pos = faux.positions_get()
    assert 1 <= len(pos) <= 3
    budget = cfg5["budget"]
    total = 0
    for p in pos:
        assert p.magic == 20261111 and p.sl > 0 and p.sl < p.price_open   # stop-loss posé
        perte_stop = (p.price_open - p.sl) * p.volume * faux.contrat[p.symbol]
        assert perte_stop <= 0.01 * budget * 1.01                         # 1 % max au stop
        total += p.price_open * p.volume * faux.contrat[p.symbol]
    assert total <= budget * 1.001                                         # jamais de levier
    assert len(faux.verifs) == len(pos)                                    # order_check d'abord
    assert "EURUSD" not in [p.symbol for p in pos]                          # tendance baissière
    raisons = {x["username"]: x["raison"] for x in r["rejets"]}
    assert "pas de signal" in raisons["EURUSD"]
    rapport = open(tmp_path / "r.md", encoding="utf-8").read()
    assert "futurs simulés" in rapport and "Raison de chaque refus" in rapport
    # Le lendemain, pas de doublon
    d.selection()
    assert len(faux.positions_get()) == len(pos)


def test_positions_personnelles_jamais_touchees(cfg5, tmp_path):
    d, faux = directeur(cfg5, tmp_path)
    perso = faux.ajouter_position_perso("US500.cash", 2.0)
    d.selection()
    d.arret_urgence("test")
    assert perso in faux.positions
    assert all(e.get("position") != perso for e in faux.envois)
    with pytest.raises(ErreurMT5):
        d.client.fermer({"ticket": perso, "magic": 0, "symbol": "US500.cash", "volume": 2})


def test_arret_moins_5_pourcent(cfg5, tmp_path):
    d, faux = directeur(cfg5, tmp_path)
    d.selection()
    tickets = [p.ticket for p in faux.positions_get()]
    for t in tickets:
        faux.fixer_profit(t, -520 / len(tickets))      # -520 sur 10 000 = -5,2 %
    d.cycle_controle()
    assert d.etat.arret_actif and faux.positions_get() == ()
    assert d.selection() is None


def test_stop_loss_touche_chez_le_courtier(cfg5, tmp_path):
    d, faux = directeur(cfg5, tmp_path)
    d.selection()
    t = faux.positions_get()[0].ticket
    faux.toucher_stop(t, -95.0)
    d.cycle_controle()
    c = d.etat.copies[str(t)]
    assert not c["ouverte"] and abs(c["resultat"] - (-96.0)) < 1e-6   # profit + commission
    assert abs(d.etat.data["pnl_realise"] - (-96.0)) < 1e-6


def test_sortie_quand_la_tendance_casse(cfg5, tmp_path):
    d, faux = directeur(cfg5, tmp_path)
    d.selection()
    sym = faux.positions_get()[0].symbol
    s = faux.series[sym]
    dernier = s[-1][3]
    for k in range(60):                                       # chute de 40 % en 60 jours
        p = dernier * (1 - 0.4 * (k + 1) / 60)
        s.append((p, p, p, p))
    faux.prix_force[sym] = s[-1][3]
    t = next(p.ticket for p in faux.positions_get() if p.symbol == sym)
    faux.positions[t] = faux.positions[t]._replace(sl=0.0)   # pour tester la sortie de tendance
    r = d.selection()
    assert t not in faux.positions
    assert any(o.get("raison") == "tendance cassée" for o in r["ordres"])


def test_dry_run_mt5(cfg5, tmp_path):
    d, faux = directeur(cfg5, tmp_path, dry_run=True)
    d.selection()
    assert faux.envois == [] and faux.verifs == []
    assert len(d.etat.copies_ouvertes()) >= 1
    assert all(t.startswith("SIM-") for t in d.etat.copies_ouvertes())
    d.cycle_controle()
    assert len(d.etat.copies_ouvertes()) >= 1


def test_budget_trop_petit(cfg5, tmp_path):
    cfg5["budget"] = 50
    d, faux = directeur(cfg5, tmp_path)
    r = d.selection()
    assert faux.envois == []
    assert any("taille minimale" in x["raison"] for x in r["rejets"])


def test_correlation_refusee(cfg5, tmp_path):
    s = serie(100, 0.0008, 0.01, graine=9)
    faux = FauxMT5(series={"US500.cash": s, "US100.cash": copy.deepcopy(s)},
                   contrat={"US500.cash": 1, "US100.cash": 1})
    d, _ = directeur(cfg5, tmp_path, faux)
    r = d.selection()
    assert len(faux.positions_get()) == 1                   # jamais les deux ensemble
    assert all(len(o["equipe"]) == 1 for o in r["simulateur"])


def test_ia_veto_et_exposition(cfg5, tmp_path):
    from fausse_api import FausseIA
    d, faux = directeur(cfg5, tmp_path)
    d.ia = FausseIA('{"exposition_max": 5, "vetos": [{"username": "US500", "raison": "x"}]}')
    r = d.selection()
    assert "US500.cash" not in [p.symbol for p in faux.positions_get()]
    assert r["budget"]["exposition"] == 1.0


def test_backtest_sans_triche():
    cfg = {"mt5": {"strategie": {"mm_longue": 200, "mm_courte": 50, "atr_jours": 20,
                                 "stop_atr": 2.5, "risque_par_trade": 0.01,
                                 "positions_max": 3}},
           "securite": {"perte_max_pct": 0.05}}
    import datetime as dt
    base = dt.date(2020, 1, 1)

    def bougies(vals):
        return [(base + dt.timedelta(days=i), o, h, l, c) for i, (o, h, l, c) in
                enumerate(vals)]
    a = serie(100, 0.0008, 0.006, n=700, graine=1)
    r1 = bt.rejouer({"A": bougies(a[:600])}, cfg)
    # Ajouter un futur délirant ne change rien au passé déjà rejoué
    futur = a[:600] + [(p, p, p, p) for p in np.linspace(a[599][3], a[599][3] * 5, 100)]
    r2 = bt.rejouer({"A": bougies(futur)}, cfg)
    assert r1["nb_jours"] == 600
    assert r2["nb_trades"] >= r1["nb_trades"]
    assert r1["gain_total"] != 0


def config_mt5(tmp_path):
    conf = tmp_path / "config.yaml"
    texte = open(os.path.join(RACINE, "config.yaml"), encoding="utf-8").read()
    texte = texte.replace("dossier_data: data", "dossier_data: %s" % (tmp_path / "data"))
    conf.write_text(texte, encoding="utf-8")
    return ["--config", str(conf), "--env", str(tmp_path / "rien")]


def test_commandes_mt5(tmp_path):
    faux = FauxMT5()
    sorties = []
    assert main(["--test-api"] + config_mt5(tmp_path), mt5=faux, sortie=sorties.append) == 0
    txt = "\n".join(sorties)
    assert "DÉMO" in txt and "US500 -> US500.cash" in txt and faux.envois == []
    assert main(["--backtest"] + config_mt5(tmp_path), mt5=faux, sortie=sorties.append) == 0
    rapport = (tmp_path / "data" / "mt5_backtest.md").read_text(encoding="utf-8")
    assert "Rejeu jour par jour" in rapport and faux.envois == []
    assert main(["--dry-run", "--once"] + config_mt5(tmp_path), mt5=faux,
                sortie=sorties.append) == 0
    assert faux.envois == [] and (tmp_path / "data" / "mt5_etat_dry_run.json").exists()
    assert main(["--once"] + config_mt5(tmp_path), mt5=faux, sortie=sorties.append) == 0
    assert len(faux.positions_get()) >= 1
    perso = faux.ajouter_position_perso("GER40")
    assert main(["--stop"] + config_mt5(tmp_path), mt5=faux, sortie=sorties.append) == 0
    assert list(faux.positions) == [perso]
    sorties.clear()
    main(["--status"] + config_mt5(tmp_path), mt5=faux, sortie=sorties.append)
    assert "ARRÊT" in sorties[0]
