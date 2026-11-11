"""Agent 8 - Simulateur (avant chaque investissement).

Monte Carlo : 10 000 futurs possibles sur 63 jours de bourse. On rejoue, par
blocs de 20 jours (« block bootstrap »), les vrais rendements journaliers des
traders choisis sur 2 ans, alignés sur les mêmes dates (pour garder le fait
que les traders gagnent ou perdent souvent en même temps). L'arrêt à -5 % du
budget total est appliqué dans chaque futur.

Feu vert seulement si : chances de gagner >= 60 % ET risque d'arrêt <= 20 %.
Sinon on réessaie avec une mise de 75 %, puis 50 %. Sinon : aucune nouvelle copie.

Limite : le passé ne garantit pas l'avenir. Le Monte Carlo ne fait que
remélanger ce qui est déjà arrivé.
"""
import itertools
import logging

import numpy as np

log = logging.getLogger("simulateur")

# Codé en dur : jamais moins de 10 000 futurs simulés par option examinée.
NB_MIN_SIMULATIONS = 10000


def aligner(rendements_par_trader, usernames, max_jours=None):
    """Matrice (jours x traders) sur l'union des dates ; jour manquant = 0 %."""
    dates = sorted(set().union(*[set(rendements_par_trader.get(u, {})) for u in usernames]))
    if max_jours:
        dates = dates[-max_jours:]
    if not dates:
        return np.zeros((0, len(usernames))), []
    m = np.array([[rendements_par_trader.get(u, {}).get(d, 0.0) for u in usernames]
                  for d in dates], dtype=float)
    return np.clip(m, -0.95, 10.0), dates


def simuler(matrice, montants, budget, cfg_s, perte_max_pct=0.05, nb=None, jours=None,
            graine=None):
    """Simule. `montants` : argent placé sur chaque trader (même ordre que la matrice).

    Renvoie un dict de statistiques en fraction du budget.
    """
    nb = max(int(nb or cfg_s.get("nb_simulations", NB_MIN_SIMULATIONS)), NB_MIN_SIMULATIONS)
    jours = int(jours or cfg_s.get("jours", 63))
    bloc = int(cfg_s.get("taille_bloc", 20))
    rng = np.random.default_rng(cfg_s.get("graine") if graine is None else graine)
    montants = np.asarray(montants, dtype=float)
    T = matrice.shape[0]
    if T < bloc or montants.sum() <= 0:
        return {"valide": False, "raison": "historique trop court (%d jours)" % T}
    nb_blocs = -(-jours // bloc)
    debuts = rng.integers(0, T - bloc + 1, size=(nb, nb_blocs))
    idx = (debuts[:, :, None] + np.arange(bloc)[None, None, :]).reshape(nb, -1)[:, :jours]
    chemins = matrice[idx]                              # (nb, jours, traders)
    valeurs = montants * np.cumprod(1.0 + chemins, axis=1)
    pnl = valeurs.sum(axis=2) - montants.sum()          # (nb, jours)
    seuil = -perte_max_pct * budget
    touche = pnl <= seuil
    arrete = touche.any(axis=1)
    premier = np.where(arrete, touche.argmax(axis=1), jours - 1)
    final = pnl[np.arange(nb), premier]                 # au moment de l'arrêt s'il y en a un
    final_pct = final / budget
    return {
        "valide": True,
        "nb_simulations": nb,
        "jours": jours,
        "chance_gain": float((final > 0).mean()),
        "risque_arret": float(arrete.mean()),
        "mediane": float(np.median(final_pct)),
        "pire_5": float(np.percentile(final_pct, 5)),
        "meilleur_5": float(np.percentile(final_pct, 95)),
        "investi": float(montants.sum()),
    }


def feu_vert(stats, cfg_s):
    return bool(stats.get("valide")) and stats["chance_gain"] >= cfg_s["chance_gain_min"] \
        and stats["risque_arret"] <= cfg_s["risque_arret_max"]


def decider(matrice, allocation_pour, budget, cfg, usernames):
    """Essaie les mises 100 %, 75 %, 50 %.

    `allocation_pour(mise)` -> dict username -> montant (déjà conforme aux
    limites du budget et du minimum eToro). Renvoie (mise retenue ou None,
    allocation, liste des essais).
    """
    cfg_s = cfg["simulateur"]
    perte = cfg["securite"]["perte_max_pct"]
    essais = []
    for mise in cfg_s.get("mises_essayees", [1.0, 0.75, 0.5]):
        alloc = allocation_pour(mise)
        if not alloc:
            essais.append({"mise": mise, "valide": False,
                           "raison": "montants sous le minimum eToro"})
            continue
        colonnes = [usernames.index(u) for u in alloc]
        montants = [alloc[u] for u in alloc]
        stats = simuler(matrice[:, colonnes], montants, budget, cfg_s, perte)
        stats["mise"] = mise
        stats["feu_vert"] = feu_vert(stats, cfg_s)
        essais.append(stats)
        if stats["feu_vert"]:
            log.info("Simulateur : FEU VERT à %.0f %% (gain %.0f %%, arrêt %.0f %%)",
                     100 * mise, 100 * stats["chance_gain"], 100 * stats["risque_arret"])
            return mise, alloc, essais
    log.info("Simulateur : feu ROUGE, aucune nouvelle copie")
    return None, {}, essais


def options_possibles(gardes, nouveaux, n_max, compatibles):
    """Toutes les équipes possibles : les copies gardées + 0 à n places de nouveaux,
    en respectant la Diversification entre chaque paire."""
    places = max(0, n_max - len(gardes))
    vues = []
    for k in range(min(places, len(nouveaux)), -1, -1):
        for combo in itertools.combinations(nouveaux, k):
            equipe = list(gardes) + list(combo)
            if not equipe:
                continue
            ok = all(compatibles(a, b) for a, b in itertools.combinations(equipe, 2))
            if ok:
                vues.append(equipe)
    return vues


def explorer(equipes, matrice, usernames, allocation_pour, budget, cfg):
    """Examine CHAQUE équipe possible à CHAQUE mise (100 %, 75 %, 50 %), avec au moins
    10 000 futurs simulés à chaque fois, sur les mêmes tirages (comparaison équitable).

    Parmi les options qui ont le feu vert, on garde la plus grosse mise, puis celle
    dont le « pire 5 % » est le moins mauvais (profil prudent), puis la meilleure
    chance de gagner. Renvoie (meilleure option ou None, liste de toutes les options).
    """
    cfg_s = cfg["simulateur"]
    perte = cfg["securite"]["perte_max_pct"]
    examinees = []
    for equipe in equipes:
        noms = [t["username"] for t in equipe]
        for mise in cfg_s.get("mises_essayees", [1.0, 0.75, 0.5]):
            alloc = allocation_pour(equipe, mise)
            if not alloc:
                continue
            colonnes = [usernames.index(u) for u in alloc]
            stats = simuler(matrice[:, colonnes], [alloc[u] for u in alloc], budget, cfg_s,
                            perte)
            stats.update({"mise": mise, "equipe": list(alloc), "allocation": alloc,
                          "feu_vert": feu_vert(stats, cfg_s), "proposee": noms})
            examinees.append(stats)
    vertes = [o for o in examinees if o["feu_vert"]]
    total = sum(o.get("nb_simulations", 0) for o in examinees)
    if not vertes:
        log.info("Simulateur : %d options examinées (%d futurs simulés), aucune n'a le "
                 "feu vert", len(examinees), total)
        return None, examinees
    if cfg_s.get("choix") == "rendement":
        # Profil dynamique : le meilleur gain médian, puis la meilleure chance de gagner
        meilleure = max(vertes, key=lambda o: (round(o["mediane"], 6), o["chance_gain"],
                                               -o["risque_arret"]))
    else:
        # Profil prudent : la plus grosse mise sûre, puis le « pire 5 % » le moins mauvais
        meilleure = max(vertes, key=lambda o: (o["mise"], o["pire_5"], o["chance_gain"]))
    log.info("Simulateur : %d options examinées (%d futurs simulés). Choix : %s à %.0f %% "
             "(gain %.0f %%, arrêt %.0f %%)", len(examinees), total,
             ", ".join(meilleure["equipe"]), 100 * meilleure["mise"],
             100 * meilleure["chance_gain"], 100 * meilleure["risque_arret"])
    return meilleure, examinees
