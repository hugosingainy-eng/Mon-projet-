"""--backtest pour MetaTrader 5 : SANS AUCUN ORDRE.

1. Rejeu jour par jour de la stratégie de tendance sur l'historique fourni par
   MetaTrader 5. Chaque jour, la décision n'utilise QUE les jours précédents
   (aucune triche sur l'avenir). Stop-loss, sortie sous la moyenne 200 jours,
   3 positions au plus, 1 % de risque par position, arrêt à -5 %.
2. Monte Carlo sur 1 mois, 3 mois et 1 an avec les signaux du jour.

Limites : les frais réels (écart achat/vente, swaps de nuit) ne sont comptés
qu'approximativement, et un historique passé ne garantit pas l'avenir.
"""
import datetime as dt
import logging
import os

import numpy as np

from .. import securite
from ..agents import simulateur
from . import strategie

log = logging.getLogger("backtest_mt5")


def rejouer(series, cfg, frais=0.0002):
    """series : dict nom -> liste de bougies (date, o, h, l, c), triées.

    Renvoie les statistiques. Valeur de départ = 1.0 (= le budget).
    """
    cs = cfg["mt5"]["strategie"]
    perte_max = securite.perte_max(cfg)
    dates = sorted(set().union(*[{b[0] for b in s} for s in series.values()]))
    index = {n: {b[0]: i for i, b in enumerate(s)} for n, s in series.items()}
    valeur, pic, chute_max, base = 1.0, 1.0, 0.0, 1.0
    positions = {}   # nom -> {"poids", "stop", "entree"}
    arrets, journal, nb_trades = [], [], 0
    pause_jusqu = None
    debut = cs["mm_longue"] + cs["atr_jours"] + 1
    for jour in dates:
        rendement = 0.0
        # 1. Résultat de la journée pour les positions ouvertes (décidées la veille)
        for n in list(positions):
            i = index[n].get(jour)
            if i is None or i == 0:
                continue
            p = positions[n]
            _, o, h, low, c = series[n][i]
            prec = series[n][i - 1][4]
            if low <= p["stop"]:
                sortie = min(o, p["stop"])          # stop touché (ou écart à l'ouverture)
                rendement += p["poids"] * (sortie / prec - 1) - p["poids"] * frais
                del positions[n]
                nb_trades += 1
            else:
                rendement += p["poids"] * (c / prec - 1)
        valeur *= 1 + rendement
        pic = max(pic, valeur)
        chute_max = max(chute_max, 1 - valeur / pic)
        # 2. Arrêt -5 % depuis le dernier réarmement
        if valeur / base - 1 <= -perte_max and positions is not None:
            if positions:
                arrets.append(jour.isoformat())
            for n, p in positions.items():
                valeur -= p["poids"] * frais * valeur
            positions = {}
            base = valeur
            pause_jusqu = jour + dt.timedelta(days=30)   # on suppose un --reset un mois après
        # 3. Décisions de fin de journée, avec les données JUSQU'À ce jour inclus
        if pause_jusqu and jour < pause_jusqu:
            journal.append((jour, valeur))
            continue
        for n in list(positions):
            i = index[n].get(jour)
            if i is None:
                continue
            sig = strategie.analyser(series[n][:i + 1], cs)
            if sig.get("valide") and sig["sortie"]:
                valeur -= positions[n]["poids"] * frais * valeur
                del positions[n]
                nb_trades += 1
        candidats = []
        for n, s in series.items():
            i = index[n].get(jour)
            if n in positions or i is None or i < debut:
                continue
            sig = strategie.analyser(s[:i + 1], cs)       # <- jamais de données futures
            if sig.get("valide") and sig["entree"]:
                candidats.append((sig["force"], n, sig))
        candidats.sort(reverse=True)
        for _, n, sig in candidats[:max(0, cs["positions_max"] - len(positions))]:
            poids = min(cs["risque_par_trade"] / (sig["distance_stop"] / sig["dernier"]),
                        1.0 / cs["positions_max"])
            positions[n] = {"poids": poids, "stop": sig["dernier"] - sig["distance_stop"],
                            "entree": sig["dernier"]}
            valeur -= poids * frais * valeur
            nb_trades += 1
        journal.append((jour, valeur))
    mois = {}
    for jour, v in journal:
        mois[(jour.year, jour.month)] = v
    vals = [1.0] + list(mois.values())
    rend_mois = [vals[i] / vals[i - 1] - 1 for i in range(1, len(vals))]
    annees = len(journal) / 252 if journal else 0
    return {
        "nb_jours": len(journal),
        "gain_total": valeur - 1,
        "gain_par_an": (valeur ** (1 / annees) - 1) if annees > 0 and valeur > 0 else 0.0,
        "mois_gagnants": (sum(1 for r in rend_mois if r > 0) / len(rend_mois))
        if rend_mois else 0.0,
        "plus_forte_baisse": chute_max,
        "jours_arret": arrets,
        "nb_trades": nb_trades,
        "debut": journal[0][0].isoformat() if journal else None,
        "fin": journal[-1][0].isoformat() if journal else None,
    }


def lancer_backtest_mt5(client, cfg, chemin="data/mt5_backtest.md"):
    client.connecter()
    cs = cfg["mt5"]["strategie"]
    series, notes = {}, []
    for nom in cs["instruments"]:
        sym = client.resoudre(nom)
        if not sym:
            notes.append("%s introuvable chez ce courtier" % nom)
            continue
        try:
            series[nom] = client.bougies(sym, cfg["backtest"].get("jours_mt5", 2500))
        except Exception as exc:  # noqa: BLE001
            notes.append("%s : %s" % (nom, exc))
    rejeu = rejouer(series, cfg) if series else {"gain_total": 0.0, "nb_jours": 0}
    # Monte Carlo avec les signaux du jour
    mc, equipe = {}, []
    budget = float(cfg["budget"])
    sig = {n: strategie.analyser(s, cs) for n, s in series.items()}
    actifs = sorted([n for n, x in sig.items() if x.get("valide") and x["entree"]],
                    key=lambda n: -sig[n]["force"])[:cs["positions_max"]]
    if actifs:
        equipe = actifs
        rend = {n: strategie.rendements(series[n]) for n in actifs}
        matrice, _ = simulateur.aligner(rend, actifs, cfg["simulateur"]["historique_jours"])
        montants = [budget * min(cs["risque_par_trade"] / (sig[n]["distance_stop"] /
                                                           sig[n]["dernier"]),
                                 1.0 / cs["positions_max"]) for n in actifs]
        for nom, h in cfg["backtest"]["horizons_jours"].items():
            mc[nom] = simulateur.simuler(matrice, montants, budget, cfg["simulateur"],
                                         securite.perte_max(cfg), jours=h)
    ecrire(chemin, rejeu, mc, equipe, notes)
    return {"rejeu": rejeu, "monte_carlo": mc, "equipe": equipe}


def _p(v):
    return "—" if v is None else "%+.1f %%" % (100 * v)


def ecrire(chemin, rejeu, mc, equipe, notes):
    L = ["# Backtest du bot MetaTrader 5", "",
         "> **Aucun ordre n'a été passé.** Aucun bot ne garantit des gains : ces chiffres "
         "décrivent le passé, pas l'avenir.", "",
         "## 1. Rejeu jour par jour de la stratégie", "",
         "Période : %s → %s. Chaque jour, le bot ne voit que les jours précédents." % (
             rejeu.get("debut"), rejeu.get("fin")), "",
         "- Gain total : **%s**" % _p(rejeu.get("gain_total")),
         "- Gain par an : **%s**" % _p(rejeu.get("gain_par_an")),
         "- Mois gagnants : %.0f %%" % (100 * rejeu.get("mois_gagnants", 0)),
         "- Plus forte baisse : %s" % _p(-rejeu.get("plus_forte_baisse", 0)),
         "- Nombre de trades : %s" % rejeu.get("nb_trades", 0),
         "- Jours où l'arrêt -5 %% se déclenche : %s" % (
             ", ".join(rejeu.get("jours_arret", [])) or "aucun"), "",
         "### ⚠️ Limites", "",
         "- Frais estimés (0,02 % par trade) : les vrais écarts et les frais de nuit peuvent "
         "être plus élevés.",
         "- Un stop-loss peut être exécuté plus bas que prévu en cas de « gap ».",
         "- Le climat de marché et l'IA ne sont pas rejoués.", ""]
    if notes:
        L += ["Notes : " + " ; ".join(notes), ""]
    L += ["## 2. Monte Carlo avec les signaux du jour", "",
          "Instruments : %s" % (", ".join(equipe) or "aucun signal d'achat aujourd'hui"), ""]
    if mc:
        L += ["| Horizon | Chances de gagner | Risque d'arrêt | Médiane | Pire 5 % | "
              "Meilleur 5 % |", "|---|---|---|---|---|---|"]
        for nom, s in mc.items():
            if s.get("valide"):
                L.append("| %s | %.0f %% | %.0f %% | %s | %s | %s |" % (
                    nom, 100 * s["chance_gain"], 100 * s["risque_arret"], _p(s["mediane"]),
                    _p(s["pire_5"]), _p(s["meilleur_5"])))
    L.append("")
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return chemin
