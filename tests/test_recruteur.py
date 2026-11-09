"""Filtres prudents et classement du Recruteur."""
import datetime as dt

from bot.agents import recruteur
from fausse_api import AUJOURD_HUI, FausseAPI, fabrique_trader


def recruter(traders, cfg, etat=None):
    return recruteur.recruter(FausseAPI(traders), cfg, etat, AUJOURD_HUI)


def raison(rejets, nom):
    return next(r["raison"] for r in rejets if r["username"] == nom)


def test_filtres_du_classement(cfg):
    traders = [
        fabrique_trader("ok", 1),
        fabrique_trader("risque", 2, row={"riskScore": 5}),
        fabrique_trader("pic", 3, row={"maxMonthlyRiskScore": 6}),
        fabrique_trader("petitgain", 4, row={"gain": 0.05}),
        fabrique_trader("tropbeau", 5, row={"gain": 2.0}),
        fabrique_trader("chute", 6, row={"peakToValley": -25.0}),
        fabrique_trader("mois", 7, row={"profitableMonthsPct": 50.0}),
        fabrique_trader("copieurs", 8, row={"copiers": 100}),
        fabrique_trader("trades", 9, row={"trades": 10}),
        fabrique_trader("smart", 10, row={"type": "SmartPortfolio"}),
    ]
    candidats, rejets = recruter(traders, cfg)
    assert [c["username"] for c in candidats] == ["ok"]
    assert "risque" in raison(rejets, "risque")
    assert "pic" in raison(rejets, "pic")
    assert "gain" in raison(rejets, "petitgain")
    assert "trop beau" in raison(rejets, "tropbeau")
    assert "chute" in raison(rejets, "chute")
    assert "mois gagnants" in raison(rejets, "mois")
    assert "copieurs" in raison(rejets, "copieurs")
    assert "trades" in raison(rejets, "trades")
    assert "Smart" in raison(rejets, "smart")


def test_classement_par_score(cfg):
    # score = gain / max(chute, 3 %) x mois gagnants
    a = fabrique_trader("a", 1, row={"gain": 0.20, "peakToValley": -10.0})      # 2.0 x 0.7
    b = fabrique_trader("b", 2, row={"gain": 0.30, "peakToValley": -5.0})       # 6.0 x 0.7
    c = fabrique_trader("c", 3, row={"gain": 0.10, "peakToValley": -1.0})       # 0.1/0.03
    candidats, _ = recruter([a, b, c], cfg)
    assert [t["username"] for t in candidats] == ["b", "c", "a"]
    assert abs(candidats[1]["score"] - 0.10 / 0.03 * 0.7) < 1e-9  # plancher 3 %


def test_verification_detaillee(cfg):
    mauvais_mois = [{"timestamp": "2026-%02d-01" % m, "gain": 2.0} for m in range(1, 13)]
    mauvais_mois[5]["gain"] = -9.0
    court = [{"timestamp": "2026-%02d-01" % m, "gain": 2.0} for m in range(1, 9)]
    vieux = (AUJOURD_HUI - dt.timedelta(days=30)).isoformat()
    traders = [
        fabrique_trader("ok", 1),
        fabrique_trader("piremois", 2, monthly=mauvais_mois),
        fabrique_trader("court", 3, monthly=court),
        fabrique_trader("levier", 4, tradeinfo={"highLeveragePct": 15.0}),
        fabrique_trader("copieur", 5, tradeinfo={"copyInvestmentPct": 80.0}),
        fabrique_trader("dilettante", 6, tradeinfo={"activeWeeksPct": 50.0}),
        fabrique_trader("dormeur", 7, tradeinfo={"lastActivity": vieux}),
    ]
    candidats, rejets = recruter(traders, cfg)
    assert [c["username"] for c in candidats] == ["ok"]
    assert "-9.0" in raison(rejets, "piremois")
    assert "historique" in raison(rejets, "court")
    assert "levier" in raison(rejets, "levier")
    assert "copie" in raison(rejets, "copieur")
    assert "semaines" in raison(rejets, "dilettante")
    assert "inactif" in raison(rejets, "dormeur")


def test_seulement_les_15_premiers_verifies(cfg):
    traders = [fabrique_trader("t%02d" % i, i + 1, row={"gain": 0.10 + i * 0.01})
               for i in range(20)]
    api = FausseAPI(traders)
    candidats, rejets = recruteur.recruter(api, cfg, None, AUJOURD_HUI)
    assert len(candidats) == 15
    assert sum(1 for a in api.appels if a[0] == "gains") == 15
    assert sum(1 for r in rejets if r["raison"].startswith("hors des")) == 5


def test_trader_banni_ignore(cfg, etat):
    etat.bannir("ok", 8, "test")
    candidats, rejets = recruter([fabrique_trader("ok", 1)], cfg, etat)
    assert candidats == []
    assert "banni" in rejets[0]["raison"]
