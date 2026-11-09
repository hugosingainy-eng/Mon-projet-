"""Inspecteur, Diversification et climat de marché."""
from bot.agents import diversification, inspecteur, marche
from fausse_api import FausseAPI, fabrique_trader


def pos(iid, pct, achat=True, levier=1):
    return {"instrumentId": iid, "investmentPct": pct, "isBuy": achat, "leverage": levier}


def test_inspecteur(cfg):
    traders = [
        fabrique_trader("ok", 1),
        fabrique_trader("concentre", 2, positions=[pos(1, 50), pos(2, 25), pos(3, 25)]),
        fabrique_trader("levier", 3, positions=[pos(1, 30, levier=5), pos(2, 30, levier=2),
                                                pos(3, 20), pos(4, 20)]),
        fabrique_trader("vendeur", 4, positions=[pos(1, 30, achat=False),
                                                 pos(2, 30, achat=False),
                                                 pos(3, 20), pos(4, 20)]),
        fabrique_trader("vide", 5, positions=[]),
    ]
    api = FausseAPI(traders)
    cand = [{"username": t["row"]["username"]} for t in traders]
    gardes, rejets = inspecteur.inspecter(api, cfg, cand)
    assert [g["username"] for g in gardes] == ["ok"]
    assert gardes[0]["portefeuille"]["position_max"] == 0.2
    r = {x["username"]: x["raison"] for x in rejets}
    assert "seule position" in r["concentre"]
    assert "levier" in r["levier"]
    assert "découvert" in r["vendeur"]
    assert "vide" in r["vide"]


def test_diversification(cfg):
    def t(nom, poids):
        return {"username": nom, "portefeuille": {"poids": poids}}
    a = t("a", {1: 0.5, 2: 0.5})
    b = t("b", {1: 0.3, 3: 0.7})        # 30 % en commun avec a -> accepté
    c = t("c", {2: 0.45, 4: 0.55})      # 45 % en commun avec a -> refusé
    assert abs(diversification.recouvrement(a["portefeuille"]["poids"],
                                            c["portefeuille"]["poids"]) - 0.45) < 1e-9
    acceptes, rejets = diversification.diversifier([a, b, c], cfg)
    assert [x["username"] for x in acceptes] == ["a", "b"]
    assert rejets[0]["username"] == "c" and "45 %" in rejets[0]["raison"]
    # Une copie déjà détenue compte aussi
    acceptes, _ = diversification.diversifier([c], cfg, deja=[a])
    assert acceptes == []


def serie_calme():
    return [100 * (1.0004 ** i) for i in range(420)]


def serie_krach():
    s = serie_calme()[:380]
    for k in range(40):
        s.append(s[-1] * (0.985 if k % 3 else 1.02))
    return s


def test_climat_calme(cfg, etat):
    api = FausseAPI([], prix_indices={s: serie_calme() for s in ("SPX500", "NSDQ100", "GOLD",
                                                                "BTC")})
    r = marche.analyser_marche(api, cfg, etat)
    assert r["climat"] == "calme" and r["exposition"] == 1.0
    assert etat.data["marche"]["clotures"]["SPX500"] > 0


def test_climat_stress(cfg, etat):
    prix = {s: serie_calme() for s in ("SPX500", "GOLD", "BTC")}
    prix["NSDQ100"] = serie_krach()
    r = marche.analyser_marche(FausseAPI([], prix_indices=prix), cfg, etat)
    assert r["indices"]["NSDQ100"]["climat"] == "stress"
    assert r["climat"] == "stress" and r["exposition"] == 0.4


def test_or_et_bitcoin_ne_decident_pas(cfg, etat):
    prix = {s: serie_calme() for s in ("SPX500", "NSDQ100")}
    prix["GOLD"] = prix["BTC"] = serie_krach()
    r = marche.analyser_marche(FausseAPI([], prix_indices=prix), cfg, etat)
    assert r["indices"]["BTC"]["climat"] == "stress"
    assert r["climat"] == "calme"


def test_chute_du_jour_passe_en_stress(cfg, etat):
    api = FausseAPI([], prix_indices={s: serie_calme() for s in ("SPX500", "NSDQ100", "GOLD",
                                                                "BTC")})
    marche.analyser_marche(api, cfg, etat)
    cloture = etat.data["marche"]["clotures"]["SPX500"]
    api.cours_actuels = {"SPX500": cloture * 0.965, "NSDQ100": etat.data["marche"][
        "clotures"]["NSDQ100"]}
    climat, alerte = marche.controle_rapide(api, cfg, etat)
    assert climat == "stress" and alerte
    assert etat.data["exposition"] == 0.4
    # -1 % seulement : pas d'alerte
    etat.data["climat"] = "calme"
    api.cours_actuels = {"SPX500": cloture * 0.99}
    assert marche.controle_rapide(api, cfg, etat) == ("calme", False)
