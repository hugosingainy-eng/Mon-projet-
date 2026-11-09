"""Rapport en français écrit après chaque sélection : data/rapport.md."""
import os


def _pct(v):
    return "—" if v is None else "%+.1f %%" % (100 * v)


def _p(v):
    return "—" if v is None else "%.0f %%" % (100 * v)


def ecrire_rapport(r, chemin):
    L = []
    titre = "Rapport du bot eToro - %s" % r["date"]
    L += ["# " + titre, ""]
    mode = "DÉMO (argent fictif)" if r["mode"] == "demo" else "ARGENT RÉEL"
    if r.get("dry_run"):
        mode += " - SIMULATION (--dry-run) : aucun ordre envoyé"
    L += ["**Mode :** " + mode, ""]
    L += ["> Rappel : aucun bot ne garantit des gains. Les simulations rejouent le passé, "
          "elles ne prédisent pas l'avenir.", ""]

    b = r.get("budget", {})
    L += ["## Climat et budget", "",
          "- Climat du marché : **%s**" % b.get("climat", "?"),
          "- Exposition retenue : **%s** du capital (%.2f $ sur %.2f $)" % (
              _p(b.get("exposition")), b.get("montant_expose", 0), b.get("capital", 0)),
          "- Nombre de traders visé : %s (part de %.2f $ chacun)" % (b.get("nb_traders"),
                                                                    b.get("part", 0)),
          "- Résultat total du bot (réalisé + latent) : **%+.2f $**" % r.get("pnl_total", 0),
          ""]

    L += ["## Simulateur (Monte Carlo)", ""]
    essais = r.get("simulateur") or []
    if not essais:
        L += ["Aucune simulation (pas d'équipe à tester).", ""]
    else:
        L += ["**%d options examinées, %s futurs simulés au total** (au moins 10 000 par "
              "option) avant de passer le moindre ordre." % (
                  r.get("nb_options", len(essais)),
                  "{:,}".format(r.get("nb_futurs", 0)).replace(",", " ")), "",
              "Les 10 meilleures options :", "",
              "| Équipe | Mise | Chances de gagner | Risque d'arrêt -5 % | Médiane | "
              "Pire 5 % | Meilleur 5 % | Verdict |", "|---|---|---|---|---|---|---|---|"]
        for e in essais[:10]:
            equipe = ", ".join(e.get("equipe") or []) or "—"
            if not e.get("valide"):
                L.append("| %s | %s | — | — | — | — | — | %s |" % (
                    equipe, _p(e.get("mise")), e.get("raison", "invalide")))
                continue
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                equipe, _p(e["mise"]), _p(e["chance_gain"]), _p(e["risque_arret"]),
                _pct(e["mediane"]), _pct(e["pire_5"]), _pct(e["meilleur_5"]),
                "FEU VERT" if e.get("feu_vert") else "refusé"))
        L.append("")
        if r.get("feu_vert"):
            L.append("**Décision :** feu vert pour %s." % ", ".join(r.get("equipe_proposee", [])))
        else:
            L.append("**Décision :** feu rouge, aucune nouvelle copie.")
        L.append("")

    ia = r.get("ia") or {}
    L += ["## Avis de l'IA", "",
          "- Risque marché : %s" % ia.get("risque_marche", "—"),
          "- Exposition maximale conseillée : %s" % _p(ia.get("exposition_max")),
          "- Vetos : %s" % (", ".join("%s (%s)" % (v["username"], v["raison"])
                                      for v in ia.get("vetos", [])) or "aucun"),
          "- Résumé : %s" % (ia.get("resume") or "—"),
          "", "_L'IA ne peut que rendre le bot plus prudent._", ""]

    L += ["## Traders copiés", ""]
    copies = r.get("copies") or []
    if copies:
        L += ["| Trader | Investi | Valeur | Résultat |", "|---|---|---|---|"]
        for c in copies:
            L.append("| %s | %.2f $ | %.2f $ | %+.2f $ |" % (c["username"], c["investi"],
                                                            c["valeur"],
                                                            c["valeur"] - c["investi"]))
    else:
        L.append("Aucune copie ouverte (le bot reste en cash).")
    L.append("")
    if r.get("ordres"):
        L += ["### Ordres de ce cycle", ""]
        for o in r["ordres"]:
            details = ", ".join("%s: %s" % (k, v) for k, v in o.items() if k != "type")
            L.append("- %s - %s" % (o["type"], details))
        L.append("")

    ren = r.get("renseignement") or {}
    L += ["## Favoris des grands investisseurs", ""]
    if ren.get("favoris"):
        for u, ticks in ren["favoris"].items():
            L.append("- %s détient aussi : %s" % (u, ", ".join(ticks)))
    else:
        L.append("Aucun recoupement (ou outil indisponible).")
    L += ["", "## Congrès américain (30 derniers jours)", ""]
    if ren.get("congres"):
        L += ["| Action | Achats | Ventes |", "|---|---|---|"]
        for t, c in ren["congres"].items():
            L.append("| %s | %d | %d |" % (t, c["achats"], c["ventes"]))
    else:
        L.append("Aucune donnée (ou outil indisponible).")
    L += ["", "## Alertes", ""]
    if ren.get("actualites"):
        for t, items in ren["actualites"].items():
            for it in items:
                L.append("- Actualité %s (%s) : %s" % (t, ", ".join(it.get("tags") or []),
                                                       it.get("titre")))
    for cible, a in (ren.get("x") or {}).items():
        L.append("- X / %s (%s) : %s" % (cible, a["gravite"], a["resume"]))
    for a in r.get("alertes") or []:
        L.append("- %s : %s" % (a["date"], a["texte"]))
    for n in ren.get("notes") or []:
        L.append("- Note : " + n)
    L.append("")

    L += ["## Raison de chaque rejet", ""]
    rejets = r.get("rejets") or []
    if rejets:
        L += ["| Trader | Agent | Raison |", "|---|---|---|"]
        for x in rejets:
            L.append("| %s | %s | %s |" % (x["username"], x["agent"],
                                           str(x["raison"]).replace("|", "/")))
    else:
        L.append("Aucun rejet.")
    L.append("")
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return chemin
