"""Agent 6 - Sentinelle (à chaque contrôle et chaque jour).

Coupe une copie :
- qui perd 8 % de ce qu'elle a reçu (à chaque contrôle) ;
- dont le trader change de comportement (chaque jour) : risque supérieur au
  maximum + 1, levier moyen qui double, ou grosse chute du jour.
Le trader coupé est banni 8 semaines (c'est le Directeur qui exécute).
"""
import datetime as dt
import logging

from ..donnees import analyser_portefeuille_live, rendements_journaliers, stats_tradeinfo

log = logging.getLogger("sentinelle")


def controle_pertes(etat, cfg):
    """Copies qui perdent trop. Renvoie une liste de décisions de coupure."""
    seuil = cfg["sentinelle"]["perte_copie_max"]
    decisions = []
    for mid, c in etat.copies_ouvertes().items():
        if c["investi"] <= 0:
            continue
        perte = c["derniere_valeur"] / c["investi"] - 1
        if perte <= -seuil:
            decisions.append({"mirror_id": mid, "username": c["username"],
                              "raison": "la copie perd %.1f %% (limite -%.0f %%)" % (
                                  100 * perte, 100 * seuil)})
    return decisions


def controle_comportement(api, etat, cfg, aujourd_hui=None):
    """Contrôle quotidien du comportement des traders copiés."""
    cs = cfg["sentinelle"]
    risque_limite = cfg["recruteur"]["risque_max"] + cs.get("marge_risque", 1)
    aujourd_hui = aujourd_hui or dt.date.today()
    refs = etat.data.get("references_traders", {})
    decisions = []
    for mid, c in etat.copies_ouvertes().items():
        u = c["username"]
        raison = None
        try:
            s = stats_tradeinfo(api.trade_info(u, cfg["recruteur"].get("periode")), cfg)
            if s["risque"] is not None and s["risque"] > risque_limite:
                raison = "risque monté à %.0f (limite %d)" % (s["risque"], risque_limite)
            if not raison:
                live = analyser_portefeuille_live(api.portefeuille_live(u), cfg)
                ref = (refs.get(u) or {}).get("levier_moyen")
                if ref and live["nb_positions"] and live["levier_moyen"] >= cs[
                        "facteur_levier"] * ref and live["levier_moyen"] > 1.0:
                    raison = "levier moyen passé de %.1f à %.1f" % (ref, live["levier_moyen"])
            if not raison:
                debut = (aujourd_hui - dt.timedelta(days=5)).isoformat()
                jours = rendements_journaliers(
                    api.gains_journaliers(u, debut, aujourd_hui.isoformat()), cfg)
                if jours:
                    dernier = jours[max(jours)]
                    if dernier <= cs["chute_jour_max"]:
                        raison = "chute de %.1f %% en une journée" % (100 * dernier)
        except Exception as exc:  # noqa: BLE001 - une donnée manquante n'est pas une alerte
            log.warning("Sentinelle : contrôle de %s impossible (%s)", u, exc)
            continue
        if raison:
            decisions.append({"mirror_id": mid, "username": u,
                              "raison": "changement de comportement : " + raison})
    return decisions
