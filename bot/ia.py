"""Accès à une IA : Claude (Anthropic) ou Grok (xAI), au choix dans config.yaml.

L'IA ne donne que des AVIS. Ce module ne décide jamais rien : c'est le
code des agents qui filtre ces avis pour qu'ils ne puissent que rendre
le bot plus prudent.
"""
import json
import logging
import re

import requests

log = logging.getLogger("ia")


class ErreurIA(Exception):
    pass


class ClientIA:
    nom = "ia"
    sait_chercher_sur_x = False

    def demander(self, systeme, message, recherche=True, recherche_x=False):
        raise NotImplementedError


class ClientClaude(ClientIA):
    """Claude via le SDK officiel `anthropic` (Messages API + recherche web serveur)."""
    nom = "claude"

    def __init__(self, cle, cfg_ia, client=None):
        import anthropic  # importé ici : le bot marche sans ce paquet si l'IA est coupée
        self.anthropic = anthropic
        self.modele = cfg_ia.get("modele_claude", "claude-opus-5-5")
        self.effort = cfg_ia.get("effort", "medium")
        self.max_recherches = int(cfg_ia.get("max_recherches", 5))
        self.client = client or anthropic.Anthropic(
            api_key=cle, timeout=float(cfg_ia.get("timeout_secondes", 300)), max_retries=2)

    def demander(self, systeme, message, recherche=True, recherche_x=False):
        params = {
            "model": self.modele,
            "max_tokens": 16000,
            "system": systeme,
            "output_config": {"effort": self.effort},
            "messages": [{"role": "user", "content": message}],
        }
        if recherche:
            params["tools"] = [{"type": "web_search_20260209", "name": "web_search",
                                "max_uses": self.max_recherches}]
        if self.modele.startswith(("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")):
            # Si un filtre de sécurité refuse, l'API relance sur un autre modèle.
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        try:
            for _ in range(4):
                if "betas" in params:
                    rep = self.client.beta.messages.create(**params)
                else:
                    rep = self.client.messages.create(**params)
                if rep.stop_reason == "pause_turn":
                    # La recherche web a fait une pause : on relance pour qu'elle finisse.
                    params["messages"] = params["messages"] + [
                        {"role": "assistant", "content": rep.content}]
                    continue
                break
        except self.anthropic.APIStatusError as exc:
            raise ErreurIA("Claude a répondu une erreur %s" % exc.status_code) from exc
        except self.anthropic.APIConnectionError as exc:
            raise ErreurIA("Claude injoignable (réseau)") from exc
        if rep.stop_reason == "refusal":
            raise ErreurIA("Claude a refusé de répondre")
        texte = "".join(getattr(b, "text", "") for b in rep.content
                        if getattr(b, "type", "") == "text")
        if not texte.strip():
            raise ErreurIA("Réponse vide de Claude (%s)" % rep.stop_reason)
        return texte


class ClientGrok(ClientIA):
    """Grok via l'API xAI (https://api.x.ai). Format à vérifier sur docs.x.ai.

    Utilise l'API « responses » avec les outils serveur web_search et x_search
    (recherche sur X/Twitter).
    """
    nom = "grok"
    sait_chercher_sur_x = True

    def __init__(self, cle, cfg_ia, session=None):
        self.cle = cle
        self.modele = cfg_ia.get("modele_grok", "grok-4")
        self.timeout = float(cfg_ia.get("timeout_secondes", 300))
        self.url = cfg_ia.get("url_grok", "https://api.x.ai/v1/responses")
        self.session = session or requests.Session()

    def demander(self, systeme, message, recherche=True, recherche_x=False):
        outils = []
        if recherche:
            outils.append({"type": "web_search"})
        if recherche_x:
            outils.append({"type": "x_search"})
        corps = {"model": self.modele,
                 "input": [{"role": "system", "content": systeme},
                           {"role": "user", "content": message}]}
        if outils:
            corps["tools"] = outils
        try:
            rep = self.session.post(self.url, json=corps, timeout=self.timeout,
                                    headers={"Authorization": "Bearer " + self.cle})
        except requests.RequestException as exc:
            raise ErreurIA("Grok injoignable (%s)" % exc) from exc
        if rep.status_code >= 400:
            raise ErreurIA("Grok a répondu une erreur %s : %s" % (rep.status_code,
                                                                  rep.text[:200]))
        try:
            data = rep.json()
        except ValueError as exc:
            raise ErreurIA("Réponse Grok illisible") from exc
        texte = texte_grok(data)
        if not texte.strip():
            raise ErreurIA("Réponse vide de Grok")
        return texte


def texte_grok(data):
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    morceaux = []
    for item in data.get("output", []) or []:
        for c in item.get("content", []) or []:
            if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                morceaux.append(c.get("text", ""))
    if morceaux:
        return "".join(morceaux)
    for ch in data.get("choices", []) or []:  # format « chat completions »
        msg = ch.get("message") or {}
        if isinstance(msg.get("content"), str):
            morceaux.append(msg["content"])
    return "".join(morceaux)


def creer_client_ia(cfg):
    """Renvoie un ClientIA, ou None si l'IA est désactivée (pas de clé)."""
    cfg_ia = cfg.get("ia", {})
    fournisseur = str(cfg_ia.get("fournisseur", "claude")).lower()
    sec = cfg.get("_secrets", {})
    try:
        if fournisseur == "grok":
            if not sec.get("XAI_API_KEY"):
                log.info("IA Grok désactivée : pas de XAI_API_KEY dans .env")
                return None
            return ClientGrok(sec["XAI_API_KEY"], cfg_ia)
        if not sec.get("ANTHROPIC_API_KEY"):
            log.info("IA Claude désactivée : pas de ANTHROPIC_API_KEY dans .env")
            return None
        return ClientClaude(sec["ANTHROPIC_API_KEY"], cfg_ia)
    except ImportError:
        log.warning("Paquet 'anthropic' absent : IA désactivée (pip install anthropic)")
        return None


def extraire_json(texte):
    """Trouve le premier objet JSON dans un texte (la réponse de l'IA)."""
    if not texte:
        return None
    bloc = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texte, re.S)
    candidats = [bloc.group(1)] if bloc else []
    debut = texte.find("{")
    fin = texte.rfind("}")
    if debut != -1 and fin > debut:
        candidats.append(texte[debut:fin + 1])
    for c in candidats:
        try:
            v = json.loads(c)
            if isinstance(v, dict):
                return v
        except ValueError:
            continue
    return None
