"""--backtest : deux tests, SANS AUCUN ORDRE.

1. Rejeu mois par mois des dernières années sur les 80 traders les plus copiés.
   À chaque mois, le bot ne voit QUE les 12 mois précédents (pas de triche sur
   l'avenir). Il choisit 3 traders avec les mêmes filtres que le Recruteur
   (ceux qui se calculent à partir de l'historique mensuel), puis on regarde
   ce qu'ils ont fait le mois suivant.
2. Monte Carlo sur 1 mois, 3 mois et 1 an avec la sélection du jour.

ATTENTION au biais du survivant : les traders qui ont disparu (comptes fermés,
grosses pertes) ne sont pas dans les données. Le passé affiché est donc plus
beau que la réalité.
"""
import datetime as dt
import logging
import math

import numpy as np

from .agents import diversification, inspecteur, recruteur, simulateur
from .donnees import gains_mensuels, normaliser_trader, rendements_journaliers
from . import securite

log = logging.getLogger("backtest")


def stats_12_mois(mensuels):
    """Statistiques calculées seulement à partir de la liste fournie."""
    g = [x for _, x in mensuels]
    valeur, pic, chute = 1.0, 1.0, 0.0
    for x in g:
        valeur *= 1 + x
        pic = max(pic, valeur)
        chute = max(chute, 1 - valeur / pic)
    return {"gain": valeur - 1, "chute": chute,
            "mois_gagnants": sum(1 for x in g if x > 0) / len(g) if g else 0.0,
            "pire_mois": min(g) if g else 0.0, "nb_mois": len(g)}


def choisir(historiques, mois, cfg):
    """Sélection au début de `mois`, avec uniquement les données AVANT `mois`.

    historiques : dict username -> liste triée de (date, gain mensuel décimal).
    """
    cr = cfg["recruteur"]
    nb = cfg["copie"]["nb_traders"]
    retenus = []
    for u, serie in historiques.items():
        passe = [(d, g) for d, g in serie if d < mois][-12:]   # <- pas d'avenir
        if len(passe) < cr["mois_historique_min"]:
            continue
        s = stats_12_mois(passe)
        if not (cr["gain_min"] <= s["gain"] <= cr["gain_max"]):
            continue
        if s["chute"] > cr["chute_max"] or s["mois_gagnants"] < cr["mois_gagnants_min"]:
            continue
        if s["pire_mois"] < cr["pire_mois_min"]:
            continue
        sc = s["gain"] / max(s["chute"], cr["chute_plancher_score"]) * s["mois_gagnants"]
        retenus.append((sc, u))
    retenus.sort(reverse=True)
    return [u for _, u in retenus[:nb]]


def rejouer(historiques, cfg, debut=None, fin=None):
    """Rejeu mensuel. Renvoie les résultats et le détail mois par mois."""
    mois_tous = sorted({d for serie in historiques.values() for d, _ in serie})
    if debut:
        mois_tous = [m for m in mois_tous if m >= debut]
    if fin:
        mois_tous = [m for m in mois_tous if m <= fin]
    perte_max = securite.perte_max(cfg)
    valeur, pic, chute_max = 1.0, 1.0, 0.0
    base_arret = 1.0  # valeur au dernier réarmement
    detail, arrets = [], []
    arrete = False
    for m in mois_tous:
        if arrete:  # après un arrêt, on suppose un --reset le mois suivant
            arrete = False
            base_arret = valeur
        choix = choisir(historiques, m, cfg)
        rend = []
        for u in choix:
            g = dict(historiques[u]).get(m)
            rend.append(g if g is not None else 0.0)
        r = float(np.mean(rend)) if rend else 0.0
        valeur_fin = valeur * (1 + r)
        # Arrêt -5 % : mesuré depuis le dernier réarmement, au pas mensuel
        if valeur_fin / base_arret - 1 <= -perte_max:
            arrets.append(m.isoformat())
            arrete = True
        valeur = valeur_fin
        pic = max(pic, valeur)
        chute_max = max(chute_max, 1 - valeur / pic)
        detail.append({"mois": m.isoformat(), "traders": choix, "rendement": r,
                       "valeur": valeur})
    actifs = [d for d in detail if d["traders"]]
    annees = len(detail) / 12 if detail else 0
    return {
        "nb_mois": len(detail),
        "gain_total": valeur - 1,
        "gain_par_an": (valeur ** (1 / annees) - 1) if annees > 0 and valeur > 0 else 0.0,
        "mois_gagnants": (sum(1 for d in actifs if d["rendement"] > 0) / len(actifs))
        if actifs else 0.0,
        "plus_forte_baisse": chute_max,
        "mois_arret": arrets,
        "detail": detail,
    }


def lancer_backtest(api, cfg, chemin="data/backtest.md", aujourd_hui=None):
    aujourd_hui = aujourd_hui or dt.date.today()
    cb = cfg["backtest"]
    # --- 1. Rejeu mensuel ---------------------------------------------
    lignes = []
    page = 1
    while len(lignes) < cb["nb_traders"]:
        lot = api.classement(page=page, taille=100, periode=cfg["recruteur"]["periode"],
                             sort="-copiers")
        if not lot:
            break
        lignes += lot
        if len(lot) < 100:
            break
        page += 1
    traders = [normaliser_trader(l, cfg) for l in lignes[:cb["nb_traders"]]]
    historiques = {}
    for t in traders:
        try:
            historiques[t["username"]] = gains_mensuels(api.gains(t["username"]), cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning("Historique de %s indisponible (%s)", t["username"], exc)
    debut = dt.date(aujourd_hui.year - int(cb["annees"]), aujourd_hui.month, 1)
    rejeu = rejouer(historiques, cfg, debut=debut)

    # --- 2. Monte Carlo avec la sélection du jour ---------------------
    mc = {}
    equipe = []
    try:
        candidats, _ = recruteur.recruter(api, cfg, None, aujourd_hui)
        candidats, _ = inspecteur.inspecter(api, cfg, candidats)
        candidats, _ = diversification.diversifier(candidats, cfg)
        n, part = securite.nb_et_part(float(cfg["budget"]), cfg["copie"]["nb_traders"],
                                      cfg["copie"]["montant_min_copie"])
        equipe = [t["username"] for t in candidats[:n]]
        if equipe:
            jours = cfg["simulateur"]["historique_jours"]
            d0 = (aujourd_hui - dt.timedelta(days=int(jours * 1.5))).isoformat()
            rend = {u: rendements_journaliers(api.gains_journaliers(u, d0,
                                                                    aujourd_hui.isoformat()), cfg)
                    for u in equipe}
            matrice, _ = simulateur.aligner(rend, equipe, jours)
            for nom, h in cb["horizons_jours"].items():
                mc[nom] = simulateur.simuler(matrice, [part] * len(equipe),
                                             float(cfg["budget"]), cfg["simulateur"],
                                             securite.perte_max(cfg), jours=h)
    except Exception as exc:  # noqa: BLE001
        log.warning("Monte Carlo du backtest impossible (%s)", exc)
        mc["erreur"] = {"valide": False, "raison": str(exc)}
    ecrire(chemin, rejeu, mc, equipe, len(historiques))
    return {"rejeu": rejeu, "monte_carlo": mc, "equipe": equipe}


def _p(v):
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else "%+.1f %%" % (100 * v)


def ecrire(chemin, rejeu, mc, equipe, nb_traders):
    L = ["# Backtest du bot eToro", "",
         "> **Aucun ordre n'a été passé.** Aucun bot ne garantit des gains : ces chiffres "
         "décrivent le passé, pas l'avenir.", "",
         "## 1. Rejeu mois par mois", "",
         "Traders étudiés : %d parmi les plus copiés. À chaque mois, le bot ne voit que "
         "les 12 mois précédents." % nb_traders, "",
         "- Mois rejoués : %d" % rejeu["nb_mois"],
         "- Gain total : **%s**" % _p(rejeu["gain_total"]),
         "- Gain par an : **%s**" % _p(rejeu["gain_par_an"]),
         "- Mois gagnants : %.0f %%" % (100 * rejeu["mois_gagnants"]),
         "- Plus forte baisse : %s" % _p(-rejeu["plus_forte_baisse"]),
         "- Mois où l'arrêt -5 %% se déclenche : %s" % (", ".join(rejeu["mois_arret"]) or "aucun"),
         "",
         "### ⚠️ Biais à connaître", "",
         "- **Biais du survivant** : les traders qui ont disparu (comptes fermés, grosses "
         "pertes) ne sont PAS dans les données. Le résultat réel aurait été moins bon.",
         "- Pas à pas mensuel : une chute pendant le mois peut déclencher l'arrêt -5 % "
         "plus tôt dans la réalité.",
         "- Le risque eToro, le portefeuille en direct, le climat de marché, l'IA et les "
         "frais ne sont pas rejoués (pas d'historique disponible).", "",
         "| Mois | Traders choisis | Rendement |", "|---|---|---|"]
    for d in rejeu["detail"][-36:]:
        L.append("| %s | %s | %s |" % (d["mois"], ", ".join(d["traders"]) or "cash",
                                        _p(d["rendement"])))
    L += ["", "## 2. Monte Carlo avec la sélection du jour", "",
          "Équipe : %s" % (", ".join(equipe) or "aucune (personne ne passe les filtres)"), ""]
    if mc:
        L += ["| Horizon | Chances de gagner | Risque d'arrêt | Médiane | Pire 5 % | "
              "Meilleur 5 % |", "|---|---|---|---|---|---|"]
        for nom, s in mc.items():
            if not s.get("valide"):
                L.append("| %s | %s | | | | |" % (nom, s.get("raison", "invalide")))
            else:
                L.append("| %s | %.0f %% | %.0f %% | %s | %s | %s |" % (
                    nom, 100 * s["chance_gain"], 100 * s["risque_arret"], _p(s["mediane"]),
                    _p(s["pire_5"]), _p(s["meilleur_5"])))
    L.append("")
    import os
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return chemin
