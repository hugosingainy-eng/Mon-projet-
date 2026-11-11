"""Stratégie prudente « suivi de tendance » (achat seulement, jamais de vente à découvert).

Règles, sur les cours de clôture JOURNALIERS :
- ENTRÉE possible si le cours est au-dessus de sa moyenne 200 jours ET que la
  moyenne 50 jours est au-dessus de la moyenne 200 jours (tendance haussière).
- STOP-LOSS placé chez le courtier à 2,5 x l'ATR (la variation moyenne d'un jour).
- SORTIE si le cours repasse sous sa moyenne 200 jours (tendance cassée).
- TAILLE : la perte au stop ne dépasse jamais 1 % du budget par position.

Ce n'est pas une « recette magique » : c'est une règle simple, connue et
testable, qui coupe les pertes et limite le nombre de trades (moins de frais).
"""


def moyenne(valeurs, n):
    if len(valeurs) < n:
        return None
    return sum(valeurs[-n:]) / n


def atr(bougies, n=20):
    """Average True Range : la variation moyenne d'une journée (en prix)."""
    if len(bougies) < n + 1:
        return None
    vrais = []
    for i in range(len(bougies) - n, len(bougies)):
        _, _, haut, bas, _ = bougies[i]
        cloture_prec = bougies[i - 1][4]
        vrais.append(max(haut - bas, abs(haut - cloture_prec), abs(bas - cloture_prec)))
    return sum(vrais) / n


def analyser(bougies, cs):
    """Renvoie l'état du signal pour un instrument (uniquement à partir du passé fourni)."""
    cl = [b[4] for b in bougies]
    mm_l = moyenne(cl, cs["mm_longue"])
    mm_c = moyenne(cl, cs["mm_courte"])
    a = atr(bougies, cs["atr_jours"])
    if mm_l is None or mm_c is None or not a:
        return {"valide": False, "raison": "historique trop court"}
    dernier = cl[-1]
    tendance = dernier > mm_l and mm_c > mm_l
    return {
        "valide": True,
        "dernier": dernier,
        "mm_longue": mm_l,
        "mm_courte": mm_c,
        "atr": a,
        "entree": tendance,
        "sortie": dernier < mm_l,
        "distance_stop": cs["stop_atr"] * a,
        "force": (dernier / mm_l - 1) / (a / dernier) if a else 0.0,  # tendance / volatilité
        "raison": ("tendance haussière" if tendance else
                   "sous la moyenne 200 j" if dernier < mm_l else "moyenne 50 j sous la 200 j"),
    }


def rendements(bougies):
    """dict date -> rendement journalier (décimal)."""
    out = {}
    for i in range(1, len(bougies)):
        p0, p1 = bougies[i - 1][4], bougies[i][4]
        if p0:
            out[bougies[i][0]] = p1 / p0 - 1
    return out
