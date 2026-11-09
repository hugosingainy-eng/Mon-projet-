"""Agent 2 — Analyste technique multi-unités de temps (5m, 15m, 1h, 4h, journalier).

Un indicateur isolé ne suffit jamais : la confirmation exige plusieurs preuves
indépendantes (tendance, momentum, volume / clôture, structure) et l'absence de
signal contraire sur les unités de temps supérieures.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from .base import OPPOSE, SUPPORT, UNAVAILABLE, Agent

TFS = ("5m", "15m", "1h", "4h", "1d")


def tf_snapshot(df: pd.DataFrame, intraday: bool) -> dict:
    c = df["close"]
    e9, e21, e50 = ind.ema(c, 9).iloc[-1], ind.ema(c, 21).iloc[-1], ind.ema(c, 50).iloc[-1]
    e200 = ind.ema(c, 200).iloc[-1] if len(c) >= 200 else np.nan
    m = ind.macd(c).iloc[-1]
    bb = ind.bollinger(c).iloc[-1]
    last = float(c.iloc[-1])
    trend = 1 if last > e21 > e50 else -1 if last < e21 < e50 else 0
    snap = {
        "close": last, "ema9": e9, "ema21": e21, "ema50": e50, "ema200": e200,
        "sma20": float(ind.sma(c, 20).iloc[-1]), "rsi14": float(ind.rsi(c, 14).iloc[-1]),
        "macd_hist": float(m["hist"]), "bb_pos": float((last - bb["lower"]) / (bb["upper"] - bb["lower"]))
        if bb["upper"] > bb["lower"] else 0.5, "atr": float(ind.atr(df, 14).iloc[-1]),
        "adx": float(ind.adx(df).iloc[-1]), "trend": trend,
    }
    if intraday and df["volume"].sum() > 0:
        snap["vwap"] = float(ind.vwap(df).iloc[-1])
        snap["above_vwap"] = bool(last > snap["vwap"])
    return {k: (round(v, 6) if isinstance(v, float) and np.isfinite(v) else v) for k, v in snap.items()}


class TechnicalAgent(Agent):
    name = "2_technical"
    role = "Analyste technique"

    def analyze(self, symbol: str, daily: pd.DataFrame, intraday: dict, require_intraday: bool):
        snaps = {"1d": tf_snapshot(daily, False)}
        missing = []
        for tf in ("4h", "1h", "15m", "5m"):
            df = intraday.get(tf)
            if df is None or len(df) < 60:
                missing.append(tf)
                continue
            snaps[tf] = tf_snapshot(df, tf in ("5m", "15m"))
        sup, res = ind.support_resistance(daily)
        candles = ind.candle_patterns(daily)
        vol_ratio = float(daily["volume"].iloc[-1] / daily["volume"].iloc[-21:-1].mean()) \
            if daily["volume"].iloc[-21:-1].mean() > 0 else np.nan
        d = snaps["1d"]
        evidence = {
            "tendance journalière haussière": d["trend"] == 1,
            "momentum MACD positif": d["macd_hist"] > 0,
            "RSI non suracheté (<75)": d["rsi14"] < 75,
            "clôture forte ou volume en hausse": candles.get("strong_close", False) or (vol_ratio or 0) > 1.2,
            "tendance réelle (ADX > 18)": (d["adx"] or 0) > 18,
        }
        bearish_higher_tf = [tf for tf in ("4h", "1h") if tf in snaps and snaps[tf]["trend"] == -1]
        resistance_close = bool(np.isfinite(res) and (res - d["close"]) < 0.5 * d["atr"])
        n_ev = sum(evidence.values())
        details = {"timeframes": snaps, "missing_timeframes": missing, "support": sup, "resistance": res,
                   "candles": candles, "volume_ratio": vol_ratio, "evidence": evidence,
                   "bearish_higher_timeframes": bearish_higher_tf, "resistance_within_half_atr": resistance_close}
        if require_intraday and ("1h" in missing or "4h" in missing):
            return self.report(symbol, UNAVAILABLE, f"données intraday indisponibles ({', '.join(missing)}) : "
                               "confirmation multi-unités impossible", None, daily.index[-1], **details)
        if bearish_higher_tf:
            return self.report(symbol, OPPOSE, f"tendance baissière en {', '.join(bearish_higher_tf)}", 0.7,
                               daily.index[-1], **details)
        if n_ev < 3:
            return self.report(symbol, OPPOSE, f"seulement {n_ev}/5 preuves techniques", 0.6, daily.index[-1],
                               **details)
        conf = 0.4 + 0.1 * n_ev - (0.15 if resistance_close else 0.0)
        return self.report(symbol, SUPPORT, f"{n_ev}/5 preuves techniques"
                           + (" (résistance proche)" if resistance_close else ""), round(min(conf, 0.9), 2),
                           daily.index[-1], **details)
