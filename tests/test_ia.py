"""L'IA ne peut QUE rendre le bot plus prudent."""
import json

from bot.agents import analyste_ia
from bot.ia import extraire_json, texte_grok
from fausse_api import FausseIA

CANDIDATS = [{"username": "a"}, {"username": "b"}]


def avis(cfg, reponse=None, erreur=None):
    return analyste_ia.consulter(FausseIA(reponse or "{}", erreur), cfg, {"x": 1}, ["a", "b"])


def test_ia_ne_peut_pas_augmenter_exposition(cfg):
    a = avis(cfg, json.dumps({"risque_marche": "faible", "exposition_max": 5.0, "vetos": []}))
    assert a["exposition_max"] == 1.0
    expo, gardes, _ = analyste_ia.appliquer(a, 0.7, CANDIDATS)
    assert expo == 0.7          # le climat disait 70 % : l'IA ne peut pas monter à 100 %
    assert len(gardes) == 2


def test_ia_peut_reduire(cfg):
    a = avis(cfg, 'Voici : ```json\n{"risque_marche": "eleve", "exposition_max": 0.3, '
                  '"vetos": [{"username": "b", "raison": "scandale"}], "resume": "prudence"}\n```')
    expo, gardes, rejets = analyste_ia.appliquer(a, 1.0, CANDIDATS)
    assert expo == 0.3
    assert [g["username"] for g in gardes] == ["a"]
    assert "scandale" in rejets[0]["raison"]


def test_exposition_bornee_a_20_pourcent(cfg):
    a = avis(cfg, '{"exposition_max": 0.01}')
    assert a["exposition_max"] == 0.2


def test_vetos_inconnus_ignores_et_pas_d_ajout(cfg):
    a = avis(cfg, json.dumps({"exposition_max": 0.9, "vetos": [{"username": "inconnu"}],
                              "ajouter": ["inconnu"], "budget": 99999}))
    assert a["vetos"] == []
    expo, gardes, _ = analyste_ia.appliquer(a, 1.0, CANDIDATS)
    assert [g["username"] for g in gardes] == ["a", "b"] and expo == 0.9


def test_reponse_illisible_ou_erreur_donne_avis_neutre(cfg):
    for a in (avis(cfg, "je ne sais pas"), avis(cfg, '{"exposition_max": "beaucoup"}'),
              avis(cfg, erreur=RuntimeError("panne")),
              analyste_ia.consulter(None, cfg, {}, ["a"])):
        assert a["exposition_max"] == 1.0 and a["vetos"] == []
    expo, gardes, _ = analyste_ia.appliquer(avis(cfg, "???"), 0.4, CANDIDATS)
    assert expo == 0.4 and len(gardes) == 2


def test_enquete_ne_coupe_que_sur_true_explicite(cfg):
    assert analyste_ia.enqueter(FausseIA('{"couper": "oui"}'), "a", {})["couper"] is False
    assert analyste_ia.enqueter(FausseIA('{"couper": true, "raison": "fraude"}'), "a",
                                {})["couper"] is True
    assert analyste_ia.enqueter(None, "a", {})["couper"] is False


def test_extraire_json_et_grok():
    assert extraire_json('bla {"a": 1} bla') == {"a": 1}
    assert extraire_json("rien") is None
    assert texte_grok({"output": [{"type": "message", "content": [
        {"type": "output_text", "text": "salut"}]}]}) == "salut"
    assert texte_grok({"choices": [{"message": {"content": "ok"}}]}) == "ok"


def test_client_claude_parametres_et_pause(cfg):
    """Vérifie l'appel au SDK Anthropic sans réseau (faux client)."""
    from types import SimpleNamespace as NS
    from bot.ia import ClientClaude

    appels = []

    class Messages:
        def create(self, **params):
            appels.append(params)
            if len(appels) == 1:
                return NS(stop_reason="pause_turn", content=[NS(type="server_tool_use")])
            return NS(stop_reason="end_turn", content=[NS(type="text", text='{"a": 1}')])

    faux = NS(beta=NS(messages=Messages()), messages=Messages())
    c = ClientClaude("cle", cfg["ia"], client=faux)
    assert c.demander("sys", "question") == '{"a": 1}'
    p = appels[0]
    assert p["model"] == "claude-opus-5-5"
    assert p["tools"][0]["type"] == "web_search_20260209"
    assert p["fallbacks"] == "default"
    assert len(appels[1]["messages"]) == 2   # relance après pause_turn


def test_client_claude_refus(cfg):
    from types import SimpleNamespace as NS
    import pytest
    from bot.ia import ClientClaude, ErreurIA

    class Messages:
        def create(self, **params):
            return NS(stop_reason="refusal", content=[])
    c = ClientClaude("cle", cfg["ia"], client=NS(beta=NS(messages=Messages())))
    with pytest.raises(ErreurIA):
        c.demander("sys", "q")


def test_creer_client_ia_sans_cle(cfg):
    from bot.ia import creer_client_ia
    assert creer_client_ia(cfg) is None
    cfg["ia"]["fournisseur"] = "grok"
    assert creer_client_ia(cfg) is None
    cfg["_secrets"]["XAI_API_KEY"] = "x"
    assert creer_client_ia(cfg).nom == "grok"
