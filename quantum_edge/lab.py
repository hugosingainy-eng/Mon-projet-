"""Strategy research laboratory: runs N genuine, distinct strategy configurations.

Search methods: grid, random, Bayesian (Optuna TPE) and evolutionary (genetic algorithm).
Anti-overfitting protocol:
* the optimizers (Bayesian / evolutionary) only ever see the TRAIN-segment objective;
* the validation segment decides whether a configuration generalizes;
* the test segment is never used for tuning, only for the final verdict;
* ranking uses the weakest segment's Sharpe × stability, not the best historical return;
* a PASS is still only a candidate: it must then survive a forward test on live prices."""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import threading
import time
from dataclasses import dataclass

import numpy as np
from sqlalchemy import func, select

from . import backtest
from .config import Settings
from .db import Database, LabExperiment, utcnow
from .instruments import BY_SYMBOL, UNIVERSE, Instrument, annualization
from .strategies import COMMON_SPACE, FAMILIES, NEEDS_BENCH, Data, space_for

GRID_DEFAULTS = {"stop_atr": 2.0, "rr": 2.0, "trail": False, "max_hold": 48, "size": 0.25,
                 "regime": "none", "vol": "none", "short": True}


@dataclass
class Dataset:
    inst: Instrument
    timeframe: str
    data: Data
    cost: float
    ann: int


def config_hash(family: str, params: dict, instrument: str, timeframe: str) -> str:
    blob = json.dumps([family, sorted(params.items()), instrument, timeframe], default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:14]


class Lab:
    def __init__(self, settings: Settings, db: Database, hub):
        self.s, self.db, self.hub = settings, db, hub
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.on_finish = None            # callback(run_id)
        st = self.db.get("lab_status")
        if st and st.get("running"):     # interrupted by a restart
            st.update(running=False, phase="interrupted", message="interrupted by restart")
            self.db.set("lab_status", st)

    # --- status -----------------------------------------------------------------------
    def status(self) -> dict:
        st = self.db.get("lab_status") or {"running": False, "target": self.s.lab_target, "completed": 0,
                                           "passed": 0, "phase": "idle", "last_run_at": None,
                                           "message": "", "run_id": 0}
        st["progress_pct"] = round(100 * st["completed"] / st["target"], 2) if st["target"] else 0.0
        return st

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, target: int | None = None) -> bool:
        if self.is_running():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._safe_run, args=(target or self.s.lab_target,),
                                        name="lab", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop.set()

    def _safe_run(self, target: int):
        try:
            self.run(target)
        except Exception as e:
            self.db.incident("error", "strategy_optimizer", f"lab run failed: {type(e).__name__}: {e}")
            st = self.status()
            st.update(running=False, phase="failed", message=f"{type(e).__name__}: {e}"[:200])
            self.db.set("lab_status", st)

    # --- data -------------------------------------------------------------------------
    def load_datasets(self, st: dict) -> list[Dataset]:
        out = []
        insts = [i for i in UNIVERSE if i.tradable]
        for n, inst in enumerate(insts):
            if self._stop.is_set():
                break
            for tf in self.s.lab_timeframes:
                st["message"] = f"loading history {inst.symbol} {tf} ({n + 1}/{len(insts)})"
                self.db.set("lab_status", st)
                try:
                    bars = self.s.lab_crypto_bars if inst.provider == "ccxt" else 100000
                    df = self.hub.candles(inst, tf, bars=bars, max_age=6 * 3600)
                    if len(df) < self.s.lab_min_bars:
                        continue
                    bench = None
                    if inst.benchmark:
                        bdf = self.hub.candles(BY_SYMBOL[inst.benchmark], tf, bars=bars, max_age=6 * 3600)
                        bench = bdf["close"] if len(bdf) else None
                    out.append(Dataset(inst, tf, Data(df, bench),
                                       self.s.cost_per_side(inst.asset_class, inst.quote_ccy),
                                       annualization(inst.asset_class)))
                except Exception as e:
                    self.db.incident("warning", "strategy_optimizer",
                                     f"history unavailable for {inst.symbol} {tf}: {type(e).__name__}: {e}")
        return out

    # --- one experiment ---------------------------------------------------------------
    def experiment(self, ds: Dataset, family: str, params: dict, method: str, run_id: int):
        tr = backtest.run(family, ds.data, params, ds.cost)
        ev = backtest.evaluate(tr, ds.data, params["size"], ds.ann, self.s.lab_train, self.s.lab_val,
                               self.s.lab_min_trades_train, self.s.lab_min_trades_oos, ds.cost)
        f = ev["full"]
        row = LabExperiment(
            id=f"{run_id}-{config_hash(family, params, ds.inst.symbol, ds.timeframe)}", run_id=run_id,
            created_at=utcnow(), family=family, params=params, instrument=ds.inst.symbol,
            timeframe=ds.timeframe, method=method,
            period_start=ds.data.ts[0].to_pydatetime(), period_end=ds.data.ts[-1].to_pydatetime(),
            bars=ds.data.n, trades=f["trades"], net_return=f["ret"], max_drawdown=f["dd"],
            sharpe=f["sharpe"], sortino=f["sortino"], profit_factor=f["pf"], win_rate=f["win"],
            avg_trade=f["avg"], segments=ev["segments"], stability=ev["stability"],
            cost_pct=ev["cost_pct"], evaluation=ev["evaluation"], score=ev["score"])
        return row, ev["train_objective"]

    # --- main loop --------------------------------------------------------------------
    def run(self, target: int) -> int:
        run_id = int(self.db.get("lab_run_id", 0)) + 1
        self.db.set("lab_run_id", run_id)
        rng = random.Random(self.s.lab_seed + run_id)
        st = {"running": True, "target": target, "completed": 0, "passed": 0, "phase": "loading data",
              "last_run_at": utcnow().isoformat(), "message": "", "run_id": run_id}
        self.db.set("lab_status", st)
        datasets = self.load_datasets(st)
        cells = [(ds, fam) for ds in datasets for fam in FAMILIES
                 if fam not in NEEDS_BENCH or ds.data.bench is not None]
        if not cells:
            st.update(running=False, phase="no data",
                      message="no historical data could be loaded; no experiments were run")
            self.db.set("lab_status", st)
            self.db.incident("error", "strategy_optimizer", st["message"])
            return run_id

        seen: set[str] = set()
        pending: list[LabExperiment] = []
        cell_best: dict[int, list] = {i: [] for i in range(len(cells))}   # (objective, params)
        last_flush = time.monotonic()

        def flush(force=False):
            nonlocal pending, last_flush
            if pending and (force or len(pending) >= 200 or time.monotonic() - last_flush > 3):
                with self.db.session() as s:
                    s.add_all(pending)
                pending = []
                last_flush = time.monotonic()
                self.db.set("lab_status", st)

        def do(ci: int, params: dict, method: str) -> float | None:
            ds, fam = cells[ci]
            key = config_hash(fam, params, ds.inst.symbol, ds.timeframe)
            if key in seen:
                return None
            seen.add(key)
            row, obj = self.experiment(ds, fam, params, method, run_id)
            pending.append(row)
            st["completed"] += 1
            st["passed"] += row.evaluation == "PASS"
            cell_best[ci].append((obj, params))
            flush()
            return obj

        def done() -> bool:
            return st["completed"] >= target or self._stop.is_set()

        # ---- phase 1: grid ------------------------------------------------------------
        explore = int(target * 0.6)
        per_cell = max(2, explore // len(cells))
        st["phase"] = "grid search"
        for ci, (ds, fam) in enumerate(cells):
            if st["completed"] >= explore // 2 or done():
                break
            keys = list(FAMILIES[fam][1])
            grid = list(itertools.product(*(FAMILIES[fam][1][k] for k in keys)))
            take = max(1, per_cell // 2)
            stride = max(1, len(grid) // take)
            offset = rng.randrange(stride)
            for combo in grid[offset::stride][:take]:
                do(ci, {**dict(zip(keys, combo)), **GRID_DEFAULTS}, "grid")
            st["message"] = f"{fam} on {ds.inst.symbol} {ds.timeframe}"
        # ---- phase 2: random ----------------------------------------------------------
        st["phase"] = "random search"
        guard = 0
        while st["completed"] < explore and not done() and guard < explore * 20:
            guard += 1
            ci = rng.randrange(len(cells))
            sp = space_for(cells[ci][1])
            do(ci, {k: rng.choice(v) for k, v in sp.items()}, "random")
        # ---- rank cells by their best TRAIN objective --------------------------------
        ranked = sorted(range(len(cells)), key=lambda i: max((o for o, _ in cell_best[i]), default=-9),
                        reverse=True)
        remaining = target - st["completed"]
        trials = 40
        n_top = max(1, min(len(ranked), remaining // (2 * trials) or 1))
        top = ranked[:n_top]
        # ---- phase 3: Bayesian optimization (Optuna TPE) -----------------------------
        st["phase"] = "bayesian optimization"
        bayes_goal = st["completed"] + remaining // 2
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        rounds = 0
        while st["completed"] < bayes_goal and not done() and rounds < 5:
            rounds += 1
            for ci in top:
                if st["completed"] >= bayes_goal or done():
                    break
                ds, fam = cells[ci]
                sp = space_for(fam)
                study = optuna.create_study(direction="maximize",
                                            sampler=optuna.samplers.TPESampler(seed=rng.randrange(1 << 30)))
                for obj, params in sorted(cell_best[ci], key=lambda x: -x[0])[:10]:   # warm start
                    study.add_trial(optuna.trial.create_trial(
                        params=params, value=obj,
                        distributions={k: optuna.distributions.CategoricalDistribution(v) for k, v in sp.items()}))
                made = attempts = 0
                while made < trials and attempts < trials * 4 and st["completed"] < bayes_goal and not done():
                    attempts += 1
                    t = study.ask()
                    params = {k: t.suggest_categorical(k, v) for k, v in sp.items()}
                    obj = do(ci, params, "bayesian")
                    if obj is None:
                        study.tell(t, state=optuna.trial.TrialState.PRUNED)
                    else:
                        study.tell(t, obj)
                        made += 1
                st["message"] = f"TPE {fam} on {ds.inst.symbol} {ds.timeframe}"
        # ---- phase 4: evolutionary (genetic algorithm) -------------------------------
        st["phase"] = "evolutionary search"
        rounds = 0
        while not done() and rounds < 50:
            rounds += 1
            for ci in top:
                if done():
                    break
                ds, fam = cells[ci]
                sp = space_for(fam)
                pop = [p for _, p in sorted(cell_best[ci], key=lambda x: -x[0])[:8]]
                while len(pop) < 8:
                    pop.append({k: rng.choice(v) for k, v in sp.items()})
                for _gen in range(4):
                    children = []
                    for _ in range(10):
                        a, b = rng.sample(pop, 2)
                        child = {k: (a if rng.random() < 0.5 else b)[k] for k in sp}      # crossover
                        for k in sp:
                            if rng.random() < 0.15:                                       # mutation
                                child[k] = rng.choice(sp[k])
                        children.append(child)
                    scored = []
                    for ch in children:
                        if done():
                            break
                        obj = do(ci, ch, "evolutionary")
                        if obj is not None:
                            scored.append((obj, ch))
                    best = sorted(cell_best[ci], key=lambda x: -x[0])[:8]                 # selection
                    pop = [p for _, p in best]
                st["message"] = f"GA {fam} on {ds.inst.symbol} {ds.timeframe}"
        # ---- top-up with random search if the smart phases ran out of new configurations
        st["phase"] = "random search (top-up)"
        guard = 0
        while not done() and guard < target * 20:
            guard += 1
            ci = rng.randrange(len(cells))
            sp = space_for(cells[ci][1])
            do(ci, {k: rng.choice(v) for k, v in sp.items()}, "random")

        flush(force=True)
        st.update(running=False, phase="stopped" if self._stop.is_set() else "complete",
                  message=f"{st['completed']} experiments on {len(datasets)} datasets, {st['passed']} passed")
        self.db.set("lab_status", st)
        if self.on_finish and not self._stop.is_set():
            self.on_finish(run_id)
        return run_id

    # --- results ----------------------------------------------------------------------
    def total(self) -> int:
        with self.db.session() as s:
            return s.scalar(select(func.count()).select_from(LabExperiment)) or 0

    def candidates(self, run_id: int) -> list[LabExperiment]:
        """Best PASS configurations of a run, at most N per instrument."""
        with self.db.session() as s:
            rows = s.scalars(select(LabExperiment).where(
                LabExperiment.run_id == run_id, LabExperiment.evaluation == "PASS")
                .order_by(LabExperiment.score.desc()).limit(500)).all()
        out, per, fams = [], {}, set()
        for r in rows:
            if per.get(r.instrument, 0) >= self.s.lab_deploy_per_instrument or (r.instrument, r.family) in fams:
                continue                     # diversify: one configuration per family per instrument
            fams.add((r.instrument, r.family))
            per[r.instrument] = per.get(r.instrument, 0) + 1
            out.append(r)
            if len(out) >= self.s.lab_deploy_top:
                break
        return out
