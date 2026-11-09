"""Agent 5 - Analyste IA (optionnel : actif seulement si une clé IA est présente).

L'IA lit les rapports de tous les agents et renvoie :
    {risque_marche, exposition_max (0.2 à 1.0), vetos[{username, raison}], resume}

RÈGLE ABSOLUE, appliquée ici par le code et non par l'IA :
l'IA peut seulement rendre le bot PLUS PRUDENT.
- son exposition ne peut que réduire celle décidée par le climat ;
- ses vetos ne peuvent que retirer des traders ;
- elle ne peut rien ajouter, ni augmenter un montant, ni lever un arrêt.
Si sa réponse est illisible ou en erreur, l'avis est neutre et le bot continue.
"""
import json
import logging

from ..ia import extraire_json

log = logging.getLogger("analyste_ia")

SYSTEME = (
    "Tu es l'analyste des risques d'un bot de copy trading eToro au profil PRUDENT. "
    "Tu reçois les rapports de ses agents. Tu peux chercher sur le web l'actualité "
    "récente des marchés et des traders. Ton rôle est uniquement de signaler des "
    "dangers : tu peux réduire l'exposition ou opposer un veto à un trader, jamais "
    "augmenter le risque. Réponds en français, avec UNIQUEMENT un objet JSON :\n"
    '{"risque_marche": "faible|moyen|eleve", "exposition_max": nombre entre 0.2 et 1.0, '
    '"vetos": [{"username": "...", "raison": "..."}], "resume": "3 phrases maximum"}'
)

NIVEAUX = ("faible", "moyen", "eleve")


def avis_neutre(raison="IA non consultée"):
    return {"risque_marche": "inconnu", "exposition_max": 1.0, "vetos": [],
            "resume": raison, "neutre": True}


def valider_avis(brut, cfg, usernames_connus):
    """Nettoie l'avis de l'IA. Tout ce qui est douteux est ignoré."""
    if not isinstance(brut, dict):
        return avis_neutre("Réponse de l'IA illisible : avis neutre")
    mini = float(cfg.get("ia", {}).get("exposition_min", 0.2))
    try:
        expo = float(brut.get("exposition_max", 1.0))
        if expo != expo:  # NaN
            raise ValueError
    except (TypeError, ValueError):
        expo = 1.0
    expo = min(1.0, max(mini, expo))  # bornée à [0.2 ; 1.0]
    vetos = []
    for v in brut.get("vetos") or []:
        if isinstance(v, dict) and v.get("username") in usernames_connus:
            vetos.append({"username": v["username"],
                          "raison": str(v.get("raison", "veto de l'IA"))[:300]})
    risque = str(brut.get("risque_marche", "inconnu")).lower()
    return {"risque_marche": risque if risque in NIVEAUX else "inconnu",
            "exposition_max": expo, "vetos": vetos,
            "resume": str(brut.get("resume", ""))[:1000], "neutre": False}


def consulter(client_ia, cfg, rapports, usernames_connus):
    """Interroge l'IA. Ne lève jamais d'exception : avis neutre en cas de souci."""
    if client_ia is None:
        return avis_neutre("IA désactivée (pas de clé)")
    message = ("Voici les rapports des agents (JSON). Donne ton avis.\n\n"
               + json.dumps(rapports, ensure_ascii=False, default=str)[:150_000])
    try:
        texte = client_ia.demander(SYSTEME, message,
                                   recherche=cfg.get("ia", {}).get("recherche_web", True),
                                   recherche_x=getattr(client_ia, "sait_chercher_sur_x", False))
    except Exception as exc:  # noqa: BLE001 - l'IA ne doit jamais bloquer le bot
        log.warning("Analyste IA en erreur (%s) : avis neutre", exc)
        return avis_neutre("IA en erreur : avis neutre")
    avis = valider_avis(extraire_json(texte), cfg, set(usernames_connus))
    log.info("Analyste IA : risque %s, exposition max %.0f %%, %d veto(s)",
             avis["risque_marche"], 100 * avis["exposition_max"], len(avis["vetos"]))
    return avis


def appliquer(avis, exposition_climat, candidats):
    """Applique l'avis : ne peut QUE réduire l'exposition et retirer des traders."""
    exposition = min(exposition_climat, avis.get("exposition_max", 1.0))
    exposition = min(exposition, exposition_climat)  # ceinture et bretelles
    veto = {v["username"]: v["raison"] for v in avis.get("vetos", [])}
    gardes, rejets = [], []
    for t in candidats:
        if t["username"] in veto:
            rejets.append({"username": t["username"], "agent": "Analyste IA",
                           "raison": "veto : " + veto[t["username"]]})
        else:
            gardes.append(t)
    return exposition, gardes, rejets


SYSTEME_ENQUETE = (
    "Tu enquêtes pour un bot de copy trading eToro PRUDENT. Des actualités "
    "inquiétantes touchent une grande partie du portefeuille d'un trader copié. "
    "Cherche sur le web (et sur X si tu peux) et dis s'il faut arrêter de le copier. "
    'Réponds UNIQUEMENT en JSON : {"couper": true/false, "raison": "..."}'
)


def enqueter(client_ia, trader, nouvelles):
    """Renvoie {"couper": bool, "raison": str}. Sans IA ou en erreur : on ne coupe pas
    (la Sentinelle et l'arrêt -5 % restent actifs)."""
    if client_ia is None:
        return {"couper": False, "raison": "IA désactivée"}
    message = json.dumps({"trader": trader, "nouvelles": nouvelles}, ensure_ascii=False,
                         default=str)[:60_000]
    try:
        brut = extraire_json(client_ia.demander(
            SYSTEME_ENQUETE, message, recherche=True,
            recherche_x=getattr(client_ia, "sait_chercher_sur_x", False)))
    except Exception as exc:  # noqa: BLE001
        log.warning("Enquête IA impossible (%s)", exc)
        return {"couper": False, "raison": "IA en erreur"}
    if not isinstance(brut, dict):
        return {"couper": False, "raison": "réponse illisible"}
    return {"couper": brut.get("couper") is True, "raison": str(brut.get("raison", ""))[:300]}
