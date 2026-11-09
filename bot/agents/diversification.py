"""Agent 3 - Diversification (chaque semaine).

Refuse deux traders qui ont plus de 40 % de leur portefeuille en commun.
Recouvrement = somme, instrument par instrument, du plus petit des deux poids.
"""
import logging

log = logging.getLogger("diversification")


def recouvrement(poids_a, poids_b):
    return sum(min(w, poids_b.get(iid, 0.0)) for iid, w in poids_a.items())


def compatibles(a, b, cfg):
    """True si deux traders ont au plus 40 % de portefeuille en commun."""
    seuil = cfg["diversification"]["recouvrement_max"]
    return recouvrement((a.get("portefeuille") or {}).get("poids", {}),
                        (b.get("portefeuille") or {}).get("poids", {})) <= seuil


def diversifier(candidats, cfg, deja=None, entre_eux=True):
    """Sélection gloutonne dans l'ordre du score.

    `deja` : traders déjà gardés (copies actuelles), comparés en priorité.
    `entre_eux=False` : on ne compare qu'avec `deja` (le Simulateur vérifie ensuite
    chaque paire dans chaque équipe possible).
    Renvoie (acceptés, rejets).
    """
    seuil = cfg["diversification"]["recouvrement_max"]
    choisis = list(deja or [])
    acceptes, rejets = [], []
    for t in candidats:
        poids = (t.get("portefeuille") or {}).get("poids", {})
        conflit = None
        for autre in choisis:
            if autre["username"] == t["username"]:
                continue
            r = recouvrement(poids, (autre.get("portefeuille") or {}).get("poids", {}))
            if r > seuil:
                conflit = (autre["username"], r)
                break
        if conflit:
            rejets.append({"username": t["username"], "agent": "Diversification",
                           "raison": "%.0f %% en commun avec %s (> %.0f %%)" % (
                               100 * conflit[1], conflit[0], 100 * seuil)})
            continue
        if entre_eux:
            choisis.append(t)
        acceptes.append(t)
    return acceptes, rejets
