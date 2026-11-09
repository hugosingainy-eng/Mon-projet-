"""Bibliothèque versionnée des stratégies (reproductibilité et promotion contrôlée).

* Chaque recherche est enregistrée : research/strategy_library/runs/<date>_<hash>.json
* Le fichier `production.json` liste les stratégies autorisées à trader.
* Règles de promotion :
  - une stratégie expérimentale n'entre en production que si elle passe TOUS les critères ;
  - une stratégie de production qui échoue à une nouvelle validation est RETIRÉE
    (réduction du risque) ;
  - les paramètres d'une stratégie de production ne changent que si la nouvelle
    configuration passe tous les critères ;
  - des résultats obtenus sur données simulées ne sont jamais promus.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..strategies.base import StrategySpec

VERSION = "1.0.0"


class StrategyLibrary:
    def __init__(self, root: Path, simulated: bool = False):
        """simulated=True : bibliothèque séparée (production_SIMULATED.json) pour
        tester tout le pipeline hors ligne. Elle n'est jamais utilisée avec de vraies données."""
        self.simulated = simulated
        self.root = Path(root) / "strategy_library"
        (self.root / "runs").mkdir(parents=True, exist_ok=True)
        self.prod_path = self.root / ("production_SIMULATED.json" if simulated else "production.json")

    def save_run(self, result: dict) -> Path:
        blob = json.dumps(result, sort_keys=True, default=str)
        h = hashlib.sha1(blob.encode()).hexdigest()[:10]
        stamp = result["created"].replace(":", "").replace("-", "")[:15]
        p = self.root / "runs" / f"{stamp}_{h}.json"
        result["run_id"] = p.stem
        result["code_version"] = VERSION
        p.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return p

    def production(self) -> dict:
        if self.prod_path.exists():
            return json.loads(self.prod_path.read_text(encoding="utf-8"))
        return {"strategies": {}, "history": []}

    def promote(self, result: dict) -> list[str]:
        """Met à jour la production selon les règles ci-dessus. Retourne le journal."""
        prod = self.production()
        changes = []
        if bool(result.get("simulated_data")) != self.simulated:
            changes.append("type de données incompatible avec cette bibliothèque : aucune promotion")
            return changes
        for rep in result["leaderboard"]:
            fam = rep["family"]
            current = prod["strategies"].get(fam)
            ok = rep.get("eligible") or (self.simulated and "chosen_spec" in rep and not rep.get("failed"))
            if ok:
                if not current or current["spec"]["id"] != rep["chosen_spec"]["id"]:
                    changes.append(f"PROMUE : {rep['chosen_spec']['label']}")
                prod["strategies"][fam] = {
                    "spec": rep["chosen_spec"], "allowed_regimes": rep["allowed_regimes"],
                    "wf_metrics": rep["metrics"]["walk_forward"], "score": rep["score"],
                    "run_id": result.get("run_id"), "validated_at": result["created"],
                }
            elif current:
                changes.append(f"RETIRÉE (échec de re-validation) : {fam} -> {rep.get('failed')}")
                prod["strategies"].pop(fam)
        prod["history"].append({"run_id": result.get("run_id"), "at": result["created"], "changes": changes})
        self.prod_path.write_text(json.dumps(prod, indent=2, default=str), encoding="utf-8")
        return changes

    def production_specs(self) -> list[tuple[StrategySpec, dict]]:
        out = []
        for fam, entry in self.production()["strategies"].items():
            sp = entry["spec"]
            spec = StrategySpec(sp["family"], tuple(sorted(sp["params"].items())))
            out.append((spec, entry))
        return out

    def latest_run(self) -> dict | None:
        runs = sorted((self.root / "runs").glob("*.json"))
        return json.loads(runs[-1].read_text(encoding="utf-8")) if runs else None
