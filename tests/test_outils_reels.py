"""Le lanceur de scripts trader-skill, avec de faux scripts (sans réseau)."""
import os

from bot.agents.renseignement import Outils, achats_congres, actualites_risquees
from bot.agents import veille_x
from fausse_api import FausseIA


def faux_pack(tmp_path, scripts):
    for chemin, code in scripts.items():
        f = tmp_path / "pack" / chemin
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(code, encoding="utf-8")
    return str(tmp_path / "pack")


def test_lancement_en_sous_processus(tmp_path, cfg):
    cfg["renseignement"]["dossier_pack"] = faux_pack(tmp_path, {
        "trader-news/news.py": (
            "import json, sys\n"
            "assert sys.flags.isolated == 1  # lancé avec python -I\n"
            "assert '--json' in sys.argv and '--dry-run' in sys.argv\n"
            "print(json.dumps({'items': [{'ticker': 'AAPL', 'tags': ['risk'], "
            "'title': 'Rappel produit', 'touches': ['AAPL']}]}))\n"),
        "trader-pelosi/ptr.py": "import sys\nsys.exit(3)\n",
    })
    outils = Outils(cfg, str(tmp_path / "travail"))
    assert actualites_risquees(outils, cfg, ["aapl"]) == {
        "AAPL": [{"titre": "Rappel produit", "tags": ["risk"], "lien": None}]}
    assert achats_congres(outils, cfg) == {}           # script en échec : on continue
    assert outils.lancer("inexistant.py") is None


def test_vrai_pack_present(cfg):
    pack = cfg["renseignement"]["dossier_pack"]
    for s in ("trader-copycat/edgar13f.py", "trader-pelosi/ptr.py", "trader-news/news.py",
              "LICENSE"):
        assert os.path.isfile(os.path.join(pack, s)), s


def test_veille_x_seulement_avec_grok(cfg):
    ia_claude = FausseIA('{"alertes": [{"cible": "t1", "gravite": "forte", "resume": "x"}]}')
    assert veille_x.veiller(ia_claude, cfg, ["t1"], ["AAPL"]) == {}
    grok = FausseIA('{"alertes": [{"cible": "t1", "gravite": "forte", "resume": "fraude"}]}',
                    x=True)
    alertes = veille_x.veiller(grok, cfg, ["t1"], ["AAPL"])
    assert alertes["t1"]["gravite"] == "forte" and grok.questions[0][2] is True
    assert veille_x.malus_x("t1", {}, alertes, cfg) == 0.20
    assert veille_x.malus_x("t2", {"AAPL": 1.0}, alertes, cfg) == 0.0
    assert veille_x.veiller(FausseIA(erreur=RuntimeError("x"), x=True), cfg, ["t1"], []) == {}
