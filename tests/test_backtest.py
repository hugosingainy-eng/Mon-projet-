"""Backtest : aucune triche sur l'avenir, et la commande --backtest."""
import datetime as dt

from bot import backtest
from bot.main import main
from conftest import RACINE, bons_traders
from fausse_api import FausseAPI, FauxOutils
import os


def mois(n, debut=dt.date(2022, 1, 1)):
    out, d = [], debut
    for _ in range(n):
        out.append(d)
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return out


def test_choix_ne_voit_pas_l_avenir(cfg):
    m = mois(30)
    regulier = [(d, 0.02) for d in m]
    # « devin » : mauvais passé, futur extraordinaire
    devin = [(d, -0.03 if i < 20 else 0.40) for i, d in enumerate(m)]
    hist = {"regulier": regulier, "devin": devin}
    assert backtest.choisir(hist, m[20], cfg) == ["regulier"]
    # Changer l'avenir ne change pas le choix d'aujourd'hui
    hist2 = {"regulier": regulier[:20] + [(d, -0.5) for d in m[20:]], "devin": devin}
    assert backtest.choisir(hist2, m[20], cfg) == backtest.choisir(hist, m[20], cfg)


def test_rejeu_resultats(cfg):
    m = mois(36)
    hist = {"a": [(d, 0.01) for d in m], "b": [(d, 0.02) for d in m]}
    r = backtest.rejouer(hist, cfg)
    assert r["nb_mois"] == 36
    # pendant 12 mois personne n'a assez d'historique : cash
    assert all(not d["traders"] for d in r["detail"][:12])
    assert abs(r["gain_total"] - (1.015 ** 24 - 1)) < 1e-9
    assert r["mois_gagnants"] == 1.0 and r["mois_arret"] == []


def test_rejeu_arret_moins_5(cfg):
    m = mois(20)
    serie = [(d, 0.02) for d in m[:14]] + [(m[14], -0.10)] + [(d, 0.0) for d in m[15:]]
    r = backtest.rejouer({"a": serie}, cfg)
    assert r["mois_arret"] == [m[14].isoformat()]
    assert r["plus_forte_baisse"] > 0.099


def test_commande_backtest(cfg, tmp_path):
    conf = tmp_path / "config.yaml"
    texte = open(os.path.join(RACINE, "config.yaml"), encoding="utf-8").read()
    texte = texte.replace("dossier_data: data", "dossier_data: %s" % (tmp_path / "data"))
    texte = texte.replace("plateforme: mt5", "plateforme: etoro")
    texte = texte.replace("budget: 10000", "budget: 600")
    texte = texte.replace("nb_simulations: 10000", "nb_simulations: 500")
    conf.write_text(texte, encoding="utf-8")
    api = FausseAPI(bons_traders())
    sorties = []
    code = main(["--backtest", "--config", str(conf), "--env", str(tmp_path / "rien")],
                api=api, outils=FauxOutils(), sortie=sorties.append)
    assert code == 0
    rapport = (tmp_path / "data" / "backtest.md").read_text(encoding="utf-8")
    assert "Rejeu mois par mois" in rapport and "Biais du survivant" in rapport
    assert "1 an" in rapport and "3 mois" in rapport and "1 mois" in rapport
    assert api.appels_ordres() == []          # aucun ordre
