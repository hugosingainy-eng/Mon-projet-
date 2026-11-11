"""Outils communs aux tests. Aucun test n'accède au réseau."""
import os
import socket
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.agents.directeur import Directeur  # noqa: E402
from bot.config import charger_config  # noqa: E402
from bot.etat import Etat  # noqa: E402
from fausse_api import AUJOURD_HUI, FausseAPI, fabrique_trader  # noqa: E402


@pytest.fixture(autouse=True)
def pas_de_reseau(monkeypatch):
    """Toute tentative de connexion réseau fait échouer le test."""
    def interdit(*a, **k):
        raise RuntimeError("Accès réseau interdit pendant les tests")
    monkeypatch.setattr(socket.socket, "connect", interdit)
    monkeypatch.setattr(socket, "create_connection", interdit)


@pytest.fixture
def cfg(tmp_path):
    c = charger_config(os.path.join(RACINE, "config.yaml"), None, environ={})
    c["plateforme"] = "etoro"
    c["budget"] = 600
    c["fichiers"]["dossier_data"] = str(tmp_path / "data")
    c["simulateur"]["nb_simulations"] = 2000
    c["renseignement"]["dossier_pack"] = os.path.join(RACINE, "vendor", "trader-skill")
    return c


@pytest.fixture
def etat(tmp_path):
    return Etat(str(tmp_path / "data" / "etat.json"))


def bons_traders(n=5):
    return [fabrique_trader("trader%d" % i, 100 + i, graine=i) for i in range(n)]


@pytest.fixture
def api():
    return FausseAPI(bons_traders())


@pytest.fixture
def directeur(api, cfg, etat, tmp_path):
    return Directeur(api, cfg, etat, client_ia=None, outils=None, dry_run=False,
                     chemin_rapport=str(tmp_path / "data" / "rapport.md"),
                     chemin_cache=str(tmp_path / "data" / "cache.json"))


@pytest.fixture
def aujourd_hui():
    return AUJOURD_HUI
