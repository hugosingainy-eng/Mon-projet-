"""Agent 2 - Inspecteur (chaque semaine).

Ouvre le portefeuille en direct de chaque candidat et écarte ceux qui ont :
- plus de 35 % sur une seule position ;
- plus de 30 % de positions à levier ;
- plus de 30 % de ventes à découvert.
"""
import logging

from ..donnees import analyser_portefeuille_live

log = logging.getLogger("inspecteur")


def juger(analyse, cfg_i):
    if analyse["nb_positions"] == 0:
        return "portefeuille en direct vide ou illisible"
    if analyse["position_max"] > cfg_i["position_max"]:
        return "%.0f %% sur une seule position (> %.0f %%)" % (
            100 * analyse["position_max"], 100 * cfg_i["position_max"])
    if analyse["part_levier"] > cfg_i["levier_max"]:
        return "%.0f %% du portefeuille à levier (> %.0f %%)" % (
            100 * analyse["part_levier"], 100 * cfg_i["levier_max"])
    if analyse["part_decouvert"] > cfg_i["vente_decouvert_max"]:
        return "%.0f %% en ventes à découvert (> %.0f %%)" % (
            100 * analyse["part_decouvert"], 100 * cfg_i["vente_decouvert_max"])
    return None


def inspecter(api, cfg, candidats):
    """Renvoie (gardés, rejets). Ajoute 'portefeuille' à chaque candidat gardé."""
    cfg_i = cfg["inspecteur"]
    gardes, rejets = [], []
    for t in candidats:
        try:
            analyse = analyser_portefeuille_live(api.portefeuille_live(t["username"]), cfg)
            raison = juger(analyse, cfg_i)
        except Exception as exc:  # noqa: BLE001
            analyse, raison = None, "portefeuille indisponible (%s)" % exc
        if raison:
            rejets.append({"username": t["username"], "agent": "Inspecteur", "raison": raison})
            continue
        t["portefeuille"] = analyse
        gardes.append(t)
    log.info("Inspecteur : %d gardés, %d écartés", len(gardes), len(rejets))
    return gardes, rejets
