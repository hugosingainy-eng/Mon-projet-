"""Agent 7 - Renseignement : trois agents construits sur le pack open source
trader-skill (https://github.com/Jakeschincariol/trader-skill, licence MIT),
copié dans vendor/trader-skill.

Les scripts sont lancés en sous-processus isolé (`python -I`) avec `--json`.
Si un outil échoue, on l'écrit dans le log et le bot continue sans lui.

- Grands Investisseurs : 13F de grands fonds -> bonus de score (jusqu'à +30 %).
- Congrès : achats/ventes des élus US sur 30 jours -> information pour l'IA.
- Actualités : nouvelles « risk » ou « legal » -> malus de score, et enquête IA.
"""
import datetime as dt
import json
import logging
import os
import subprocess
import sys
import time

log = logging.getLogger("renseignement")


class Outils:
    """Lance les scripts du pack. Remplaçable par un faux dans les tests."""

    def __init__(self, cfg, dossier_travail="data/renseignement"):
        cr = cfg.get("renseignement", {})
        self.pack = os.path.abspath(cr.get("dossier_pack", "vendor/trader-skill"))
        self.timeout = float(cr.get("timeout_secondes", 180))
        self.travail = os.path.abspath(dossier_travail)
        self.env = dict(os.environ)
        ua = cfg.get("_secrets", {}).get("SEC_USER_AGENT")
        if ua:
            self.env["SEC_USER_AGENT"] = ua

    def lancer(self, script, *args):
        """Renvoie le JSON produit par le script, ou None si échec."""
        chemin = os.path.join(self.pack, script)
        if not os.path.isfile(chemin):
            log.warning("Outil introuvable : %s", chemin)
            return None
        os.makedirs(self.travail, exist_ok=True)
        cmd = [sys.executable, "-I", chemin] + [str(a) for a in args]
        try:
            res = subprocess.run(cmd, cwd=self.travail, env=self.env, capture_output=True,
                                 text=True, timeout=self.timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("Outil %s en échec (%s)", script, exc)
            return None
        sortie = (res.stdout or "").strip()
        if not sortie:
            log.warning("Outil %s : aucune sortie (code %s) %s", script, res.returncode,
                        (res.stderr or "")[-300:])
            return None
        try:
            return json.loads(sortie)
        except ValueError:
            log.warning("Outil %s : sortie non JSON (code %s)", script, res.returncode)
            return None


# --- Grands Investisseurs (13F) ---------------------------------------------
def favoris_grands_investisseurs(outils, cfg, chemin_cache, maintenant=None):
    """dict ticker -> {"fonds": [noms], "poids": somme des % des 13F (décimal)}.

    Cache de 7 jours dans data/. Renvoie {} si tout échoue.
    """
    cg = cfg["renseignement"]["grands_investisseurs"]
    if not cg.get("actif", True):
        return {}
    maintenant = maintenant or time.time()
    try:
        with open(chemin_cache, encoding="utf-8") as fh:
            cache = json.load(fh)
        if maintenant - cache.get("date", 0) < cg.get("cache_jours", 7) * 86400:
            return cache.get("favoris", {})
    except (OSError, ValueError):
        pass
    if not cfg.get("_secrets", {}).get("SEC_USER_AGENT"):
        log.warning("Grands Investisseurs : SEC_USER_AGENT manquant dans .env, outil ignoré")
        return {}
    favoris = {}
    for nom, cik in cg["ciks"].items():
        data = outils.lancer("trader-copycat/edgar13f.py", "holdings", cik, "--json",
                             "--combine", "--top", cg.get("top", 25))
        if not isinstance(data, dict):
            continue
        for p in data.get("positions", []) or []:
            tick = (p.get("ticker") or "").upper()
            if not tick:
                continue
            f = favoris.setdefault(tick, {"fonds": [], "poids": 0.0})
            f["fonds"].append(nom)
            f["poids"] += float(p.get("pct_of_13f") or 0) / 100.0
    if favoris:
        os.makedirs(os.path.dirname(os.path.abspath(chemin_cache)), exist_ok=True)
        with open(chemin_cache, "w", encoding="utf-8") as fh:
            json.dump({"date": maintenant, "favoris": favoris}, fh)
    return favoris


def bonus_grands_investisseurs(poids_par_ticker, favoris, cfg):
    """Part du portefeuille du trader dans les favoris -> bonus de 0 à +30 %."""
    if not favoris or not poids_par_ticker:
        return 0.0, []
    communs = [t for t in poids_par_ticker if t.upper() in favoris]
    part = sum(poids_par_ticker[t] for t in communs)
    bonus = min(1.0, part) * cfg["renseignement"]["grands_investisseurs"]["bonus_max"]
    return bonus, communs


# --- Congrès ------------------------------------------------------------------
def achats_congres(outils, cfg, aujourd_hui=None):
    """dict ticker -> {"achats": n, "ventes": n} sur les 30 derniers jours."""
    cc = cfg["renseignement"]["congres"]
    if not cc.get("actif", True):
        return {}
    aujourd_hui = aujourd_hui or dt.date.today()
    depuis = (aujourd_hui - dt.timedelta(days=cc.get("jours", 30))).isoformat()
    index = outils.lancer("trader-pelosi/ptr.py", "index", "--since", depuis, "--json",
                          "--limit", cc.get("max_documents", 25))
    if not isinstance(index, list):
        return {}
    compte = {}
    for f in index[:cc.get("max_documents", 25)]:
        if f.get("type") not in (None, "P"):
            continue
        rapport = outils.lancer("trader-pelosi/ptr.py", "fetch", f.get("doc_id"),
                                "--year", f.get("year", aujourd_hui.year), "--json")
        if not isinstance(rapport, dict):
            continue
        for r in rapport.get("rows", []) or []:
            tick = (r.get("ticker") or "").upper()
            if not tick:
                continue
            c = compte.setdefault(tick, {"achats": 0, "ventes": 0})
            typ = str(r.get("type") or "").upper()
            if typ.startswith("P"):
                c["achats"] += 1
            elif typ.startswith("S"):
                c["ventes"] += 1
    return compte


# --- Actualités -------------------------------------------------------------
def actualites_risquees(outils, cfg, tickers):
    """dict ticker -> liste de titres étiquetés « risk » ou « legal »."""
    ca = cfg["renseignement"]["actualites"]
    if not ca.get("actif", True) or not tickers:
        return {}
    tickers = sorted({t.upper() for t in tickers if t})[:ca.get("max_tickers", 40)]
    data = outils.lancer("trader-news/news.py", "--tickers", *tickers, "--hours",
                         ca.get("heures", 48), "--json", "--dry-run")
    if not isinstance(data, dict):
        return {}
    tags_risque = set(ca.get("tags_risque", ["risk", "legal"]))
    out = {}
    for it in data.get("items", []) or []:
        if not tags_risque & set(it.get("tags") or []):
            continue
        touches = set(it.get("touches") or []) | ({it["ticker"]} if it.get("ticker") else set())
        for t in touches:
            out.setdefault(t.upper(), []).append({"titre": it.get("title"),
                                                  "tags": it.get("tags"),
                                                  "lien": it.get("link")})
    return out


def part_touchee(poids_par_ticker, nouvelles):
    return sum(w for t, w in poids_par_ticker.items() if t.upper() in nouvelles)


def malus_actualites(poids_par_ticker, nouvelles, cfg):
    part = part_touchee(poids_par_ticker, nouvelles)
    return min(1.0, part) * cfg["renseignement"]["actualites"]["malus_max"], part
