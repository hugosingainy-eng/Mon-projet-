"""Pipeline complet du Directeur, budget, dry-run et copies personnelles."""
import json

from bot.agents.directeur import Directeur
from bot.etat import Etat
from conftest import bons_traders
from fausse_api import FausseAPI, FausseIA, FauxOutils


def test_pipeline_complet(directeur, api, aujourd_hui):
    r = directeur.selection(aujourd_hui)
    assert r["feu_vert"]
    copies = directeur.etat.copies_ouvertes()
    assert len(copies) == 3
    assert all(abs(c["investi"] - 200) < 0.01 for c in copies.values())
    assert sum(c["investi"] for c in copies.values()) <= 600
    assert len(api.mirrors) == 3
    rapport = open(directeur.chemin_rapport, encoding="utf-8").read()
    for titre in ("Climat", "Simulateur", "Avis de l'IA", "Traders copiés",
                  "grands investisseurs", "Congrès", "Alertes", "Raison de chaque rejet"):
        assert titre in rapport
    # Une deuxième sélection ne double pas les copies
    directeur.selection(aujourd_hui)
    assert len(directeur.etat.copies_ouvertes()) == 3
    assert sum(c["investi"] for c in directeur.etat.copies_ouvertes().values()) <= 600.01


def test_ia_veto_dans_le_pipeline(api, cfg, etat, tmp_path, aujourd_hui):
    ia = FausseIA('{"exposition_max": 1.0, "vetos": [{"username": "trader0", "raison": "x"}]}')
    d = Directeur(api, cfg, etat, client_ia=ia, chemin_rapport=str(tmp_path / "r.md"))
    d.selection(aujourd_hui)
    assert "trader0" not in [c["username"] for c in etat.copies_ouvertes().values()]
    assert ia.questions  # l'IA a bien reçu les rapports


def test_budget_trop_faible_reste_en_cash(api, cfg, etat, tmp_path, aujourd_hui):
    cfg["budget"] = 150
    d = Directeur(api, cfg, etat, chemin_rapport=str(tmp_path / "r.md"))
    r = d.selection(aujourd_hui)
    assert r["budget"]["nb_traders"] == 0
    assert etat.copies_ouvertes() == {}
    assert api.appels_ordres() == []


def test_budget_moyen_copie_moins_de_traders(api, cfg, etat, tmp_path, aujourd_hui):
    cfg["budget"] = 450
    d = Directeur(api, cfg, etat, chemin_rapport=str(tmp_path / "r.md"))
    d.selection(aujourd_hui)
    copies = etat.copies_ouvertes()
    assert len(copies) == 2
    assert all(abs(c["investi"] - 225) < 0.01 for c in copies.values())


def test_dry_run_n_envoie_aucun_ordre(api, cfg, tmp_path, aujourd_hui):
    from bot.config import chemin_data
    etat = Etat(chemin_data(cfg, "etat", dry_run=True))
    assert etat.chemin.endswith("etat_dry_run.json")
    d = Directeur(api, cfg, etat, dry_run=True, chemin_rapport=str(tmp_path / "r.md"))
    d.selection(aujourd_hui)
    assert api.appels_ordres() == []
    assert len(etat.copies_ouvertes()) == 3
    assert all(m.startswith("SIM-") for m in etat.copies_ouvertes())
    d.cycle_controle()  # les copies simulées ne sont pas prises pour des copies fermées
    assert len(etat.copies_ouvertes()) == 3
    assert not (tmp_path / "data" / "etat.json").exists()
    assert "SIMULATION" in open(tmp_path / "r.md", encoding="utf-8").read()


def test_copies_personnelles_jamais_touchees(cfg, etat, tmp_path, aujourd_hui):
    traders = bons_traders()
    api = FausseAPI(traders)
    perso = api.ajouter_mirror_perso(parent_cid=100, valeur=1000.0)   # trader0, copié par vous
    d = Directeur(api, cfg, etat, chemin_rapport=str(tmp_path / "r.md"))
    r = d.selection(aujourd_hui)
    assert "trader0" not in [c["username"] for c in etat.copies_ouvertes().values()]
    assert any(x["username"] == "trader0" and "vous-même" in x["raison"] for x in r["rejets"])
    d.fermer_tout("test")
    d.arret_urgence("test")
    assert perso in api.mirrors                       # toujours là
    assert all(a[1][0] != perso for a in api.appels if a[0] == "copie_fermer")
    assert all(a[1][0] != 100 for a in api.appels if a[0] == "copie_ordre")


def test_renseignement_bonus_et_malus(api, cfg, etat, tmp_path, aujourd_hui):
    cfg["_secrets"]["SEC_USER_AGENT"] = "Test test@example.com"
    # trader1 détient TCK1010..TCK1014 ; trader2 détient TCK1020..
    outils = FauxOutils({
        "trader-copycat/edgar13f.py": {"positions": [{"ticker": "TCK1010", "pct_of_13f": 10},
                                                     {"ticker": "TCK1011", "pct_of_13f": 5}]},
        "trader-pelosi/ptr.py": lambda *a: ([{"doc_id": "1", "type": "P", "year": 2026}]
                                            if a[0] == "index" else
                                            {"rows": [{"ticker": "TCK1010", "type": "P"}]}),
        "trader-news/news.py": {"items": [
            {"ticker": "TCK1020", "touches": ["TCK1020", "TCK1021", "TCK1022"],
             "tags": ["legal"], "title": "Procès"},
            {"ticker": "TCK1030", "tags": ["earnings"], "title": "Résultats"}]},
    })
    d = Directeur(api, cfg, etat, outils=outils, chemin_rapport=str(tmp_path / "r.md"))
    r = d.selection(aujourd_hui)
    ren = r["renseignement"]
    assert ren["favoris"]["trader1"] == ["TCK1010", "TCK1011"]
    assert ren["congres"]["TCK1010"] == {"achats": 1, "ventes": 0}
    assert "TCK1020" in ren["actualites"] and "TCK1030" not in ren["actualites"]
    rapport = open(tmp_path / "r.md", encoding="utf-8").read()
    assert "trader1 détient aussi : TCK1010, TCK1011" in rapport
    assert "Procès" in rapport


def test_outil_en_panne_ne_bloque_pas(api, cfg, etat, tmp_path, aujourd_hui):
    cfg["_secrets"]["SEC_USER_AGENT"] = "Test test@example.com"
    outils = FauxOutils({"trader-copycat/edgar13f.py": RuntimeError("SEC en panne"),
                         "trader-pelosi/ptr.py": None,
                         "trader-news/news.py": "pas du json"})
    d = Directeur(api, cfg, etat, outils=outils, chemin_rapport=str(tmp_path / "r.md"))
    r = d.selection(aujourd_hui)
    assert r["feu_vert"] and len(etat.copies_ouvertes()) == 3
    assert any("indisponible" in n for n in r["renseignement"]["notes"])


def test_calcul_bonus_et_malus(cfg):
    from bot.agents import renseignement as rs
    poids = {"AAPL": 0.4, "KO": 0.3, "XOM": 0.3}
    bonus, communs = rs.bonus_grands_investisseurs(poids, {"AAPL": {}, "KO": {}}, cfg)
    assert abs(bonus - 0.7 * 0.30) < 1e-9 and sorted(communs) == ["AAPL", "KO"]
    assert rs.bonus_grands_investisseurs({"AAPL": 1.0}, {"AAPL": {}}, cfg)[0] == 0.30  # plafond
    malus, part = rs.malus_actualites(poids, {"XOM": [{"titre": "x"}]}, cfg)
    assert abs(part - 0.3) < 1e-9 and abs(malus - 0.3 * 0.30) < 1e-9
    assert rs.bonus_grands_investisseurs(poids, {}, cfg) == (0.0, [])


def test_bonus_change_le_classement(api, cfg, etat, tmp_path, aujourd_hui):
    """Un trader moins bien noté passe devant grâce aux grands investisseurs,
    un autre recule à cause des actualités."""
    cfg["_secrets"]["SEC_USER_AGENT"] = "Test test@example.com"
    tick4 = [{"ticker": "TCK%d" % (1040 + i), "pct_of_13f": 4} for i in range(5)]
    outils = FauxOutils({"trader-copycat/edgar13f.py": {"positions": tick4},
                         "trader-pelosi/ptr.py": [],
                         "trader-news/news.py": {"items": [
                             {"ticker": "TCK1000", "touches": ["TCK1000", "TCK1001", "TCK1002"],
                              "tags": ["risk"], "title": "Faillite"}]}})
    d = Directeur(api, cfg, etat, outils=outils)
    candidats = [{"username": "trader%d" % i, "score": 1.0 + i * 0.01,
                  "portefeuille": {"poids": {(100 + i) * 10 + k: 0.2 for k in range(5)}}}
                 for i in range(5)]
    d._renseignement(candidats, aujourd_hui)
    par = {c["username"]: c for c in candidats}
    assert abs(par["trader4"]["bonus_gi"] - 0.30) < 1e-9
    assert abs(par["trader0"]["malus_news"] - 0.6 * 0.30) < 1e-9
    assert par["trader4"]["score"] > par["trader3"]["score"] * 1.25
    assert par["trader0"]["score"] < 1.0
