"""Stratégies de trading (achat seulement, jamais de vente à découvert).

Le bot combine deux méthodes classiques de traders professionnels, sur les cours
de clôture JOURNALIERS :

1. TENDANCE (moyen terme)
   - entrée : cours > moyenne 200 j ET moyenne 50 j > moyenne 200 j ;
   - sortie : le cours repasse sous la moyenne 200 j.
2. CASSURE (court terme, pour les occasions de la semaine)
   - entrée : le cours dépasse son plus haut des 20 derniers jours, au-dessus de
     sa moyenne 50 j (le marché « casse » vers le haut avec de l'élan) ;
   - sortie : le cours passe sous son plus bas des 10 derniers jours.

Pour les deux :
- STOP-LOSS chez le courtier à 2,5 x l'ATR (la variation moyenne d'un jour) ;
- STOP SUIVEUR : chaque jour, le stop remonte sous le plus haut atteint
  (il ne descend jamais) : on coupe vite les pertes et on laisse courir les gains ;
- TAILLE : la perte au stop ne dépasse jamais le risque par trade (1 % du budget).

Aucune stratégie ne gagne à tous les coups : elles perdent souvent un peu, et
gagnent parfois beaucoup. Le bot ne garantit aucun gain.
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
    """Signaux pour un instrument, calculés UNIQUEMENT avec le passé fourni."""
    strategies = cs.get("strategies", ["tendance"])
    cl = [b[4] for b in bougies]
    mm_l = moyenne(cl, cs["mm_longue"])
    mm_c = moyenne(cl, cs["mm_courte"])
    a = atr(bougies, cs["atr_jours"])
    nb_cassure = int(cs.get("cassure_jours", 20))
    nb_sortie = int(cs.get("cassure_sortie_jours", 10))
    if mm_l is None or mm_c is None or not a or len(cl) < nb_cassure + 2:
        return {"valide": False, "raison": "historique trop court"}
    dernier = cl[-1]
    vol = a / dernier
    tendance = dernier > mm_l and mm_c > mm_l
    plus_haut = max(cl[-nb_cassure - 1:-1])
    cassure = dernier > plus_haut and dernier > mm_c
    elan = dernier / cl[-nb_cassure - 1] - 1           # variation sur 20 jours
    entree, nom, force = False, None, 0.0
    if "cassure" in strategies and cassure:
        entree, nom = True, "cassure"
        force = elan / vol if vol else 0.0
    if "tendance" in strategies and tendance:
        f = (dernier / mm_l - 1) / vol if vol else 0.0
        if not entree or f > force:
            entree, nom, force = True, "tendance", f
    if entree:
        raison = "tendance haussière" if nom == "tendance" else "cassure du plus haut 20 j"
    elif dernier < mm_l:
        raison = "sous la moyenne 200 j"
    elif mm_c <= mm_l:
        raison = "moyenne 50 j sous la 200 j"
    else:
        raison = "pas d'élan suffisant"
    plus_haut_recent = max(b[2] for b in bougies[-nb_cassure:])
    return {
        "valide": True,
        "dernier": dernier,
        "mm_longue": mm_l,
        "mm_courte": mm_c,
        "atr": a,
        "entree": entree,
        "strategie": nom,
        "sortie": dernier < mm_l,                                  # sortie « tendance »
        "sortie_cassure": dernier < min(cl[-nb_sortie - 1:-1]),    # sortie « cassure »
        "distance_stop": cs["stop_atr"] * a,
        "stop_suiveur": plus_haut_recent - cs["stop_atr"] * a,
        "elan_20j": elan,
        "force": force,
        "raison": raison,
    }


def doit_sortir(signal, strategie_position):
    """La position doit-elle être fermée selon SA stratégie ?"""
    if not signal.get("valide"):
        return False
    if strategie_position == "cassure":
        return bool(signal["sortie_cassure"])
    return bool(signal["sortie"])


def rendements(bougies):
    """dict date -> rendement journalier (décimal)."""
    out = {}
    for i in range(1, len(bougies)):
        p0, p1 = bougies[i - 1][4], bougies[i][4]
        if p0:
            out[bougies[i][0]] = p1 / p0 - 1
    return out
