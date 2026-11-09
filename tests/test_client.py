"""Client HTTP eToro : en-têtes, chemins démo, limites et 429."""
import pytest

from bot.etoro_client import ErreurAPI, ErreurPassagere, EtoroClient, LimiteurDebit


class Rep:
    def __init__(self, statut=200, corps=None, entetes=None):
        self.status_code = statut
        self._corps = corps if corps is not None else {}
        self.headers = entetes or {}
        self.content = b"x"
        self.text = str(self._corps)

    def json(self):
        return self._corps


class FausseSession:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.requetes = []

    def request(self, methode, url, params=None, json=None, headers=None, timeout=None):
        self.requetes.append({"methode": methode, "url": url, "params": params, "json": json,
                              "headers": headers})
        return self.reponses.pop(0)


def client(reponses, mode="demo"):
    pauses = []
    s = FausseSession(reponses)
    c = EtoroClient("cle", "user", mode, {"pause_min_secondes": 0, "backoff_base_secondes": 1},
                    session=s, dormir=pauses.append)
    return c, s, pauses


def test_entetes_et_request_id_neuf():
    c, s, _ = client([Rep(corps={"clientPortfolio": {"credit": 1}}), Rep(corps={})])
    assert c.portefeuille() == {"credit": 1}
    c.portefeuille()
    h1, h2 = s.requetes[0]["headers"], s.requetes[1]["headers"]
    assert h1["x-api-key"] == "cle" and h1["x-user-key"] == "user"
    assert h1["x-request-id"] != h2["x-request-id"]
    assert s.requetes[0]["url"].endswith("/api/v1/trading/info/demo/pnl")


def test_chemins_copie_demo_et_reel():
    c, s, _ = client([Rep(corps={"isSuccess": True})] * 2)
    c.copie_eligibilite(1, 200)
    c.copie_fermer(5, "abc")
    assert s.requetes[0]["url"].endswith("/api/v2/trading/copy/demo/eligibility")
    assert s.requetes[1]["json"] == {"mirrorID": 5, "unregisterType": "Close",
                                     "clientRequestID": "abc"}
    c, s, _ = client([Rep(corps={})], mode="real")
    c.copie_ordre(1, 200, "ref")
    assert s.requetes[0]["url"].endswith("/api/v2/trading/copy")
    assert s.requetes[0]["json"] == {"parentCID": 1, "amount": 200, "referenceID": "ref"}


def test_reference_trop_longue():
    c, _, _ = client([])
    with pytest.raises(ErreurAPI):
        c.copie_ordre(1, 200, "x" * 36)


def test_429_respecte_retry_after():
    c, s, pauses = client([Rep(429, entetes={"Retry-After": "7"}), Rep(corps={"items": [1]})])
    assert c.classement() == [1]
    assert 7 in pauses
    assert s.requetes[0]["params"]["pageSize"] == 100


def test_erreurs_passageres_puis_abandon():
    c, _, pauses = client([Rep(503)] * 5)
    with pytest.raises(ErreurPassagere):
        c.portefeuille()
    assert pauses == [1, 2, 4, 8, 16]  # backoff exponentiel


def test_404_suivi_ordre_et_400():
    c, _, _ = client([Rep(404), Rep(400, corps={"error": "non"})])
    assert c.copie_suivi("ref") is None
    with pytest.raises(ErreurAPI):
        c.portefeuille()


def test_limiteur_de_debit():
    t = [0.0]
    attentes = []

    def dormir(s):
        attentes.append(s)
        t[0] += s
    lim = LimiteurDebit(3, pause_min=1.0, horloge=lambda: t[0], dormir=dormir)
    for _ in range(4):
        lim.attendre()
    assert attentes[:2] == [1.0, 1.0]
    assert attentes[-1] > 50   # 4e appel dans la même minute : on attend


def test_cles_obligatoires():
    with pytest.raises(ErreurAPI):
        EtoroClient("", "", "demo")
