"""Ligne de commande.

  python -m etoro_bot backtest --data yahoo         # tester la stratégie sur 3 ans
  python -m etoro_bot scan --mode paper --data yahoo   # un scan, sans ordre réel
  python -m etoro_bot run --mode demo               # trade sur le compte DÉMO eToro, lun->ven
  python -m etoro_bot status --mode demo            # état du portefeuille du bot
"""
from __future__ import annotations

import argparse
import os

from .config import BotConfig


def build(args):
    cfg = BotConfig()
    if getattr(args, "mode", None):
        cfg.mode = args.mode
    if getattr(args, "capital", None):
        cfg.risk.starting_capital = args.capital
    if getattr(args, "paths", None):
        cfg.sim.mc_paths = args.paths
    if getattr(args, "workers", None):
        cfg.sim.workers = args.workers
    if getattr(args, "symbols", None):
        syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        cfg.watchlist = {s: cfg.watchlist.get(s, "stock") for s in syms}
    client = None
    if cfg.mode == "demo" or args.data == "etoro":
        from .etoro_client import EtoroDemoClient

        client = EtoroDemoClient(cfg.api_key, cfg.user_key, cfg.base_url)
    from .data import make_source

    data_name = args.data or ("etoro" if cfg.mode == "demo" else "yahoo")
    return cfg, make_source(data_name, client), client


def main(argv=None):
    ap = argparse.ArgumentParser(prog="etoro_bot", description="Bot de trading multi-agents eToro (démo)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("backtest", "scan", "run", "status"):
        p = sub.add_parser(name)
        p.add_argument("--mode", choices=["paper", "demo"], default=None)
        p.add_argument("--data", choices=["etoro", "yahoo", "csv", "synthetic"], default=None)
        p.add_argument("--capital", type=float, default=None)
        p.add_argument("--paths", type=int, default=None, help="trajectoires Monte-Carlo par trade")
        p.add_argument("--workers", type=int, default=None, help="nombre de sous-agents en parallèle")
        p.add_argument("--symbols", default=None, help="ex: AAPL,MSFT,NVDA")
    args = ap.parse_args(argv)
    if args.cmd == "backtest" and args.mode is None:
        args.mode = "paper"
    cfg, source, client = build(args)

    if args.cmd == "backtest":
        if cfg.mode == "demo":
            raise SystemExit("Le backtest est toujours local (paper).")
        from .backtest import print_report, run_backtest

        data = source.load(list(cfg.watchlist), cfg.history_bars + 300)
        res = run_backtest(cfg, data)
        print_report(res)
        os.makedirs(cfg.log_dir, exist_ok=True)
        res["equity_curve"].to_csv(os.path.join(cfg.log_dir, "backtest_equity.csv"), header=["equity"])
        return

    from .bot import TradingBot

    bot = TradingBot(cfg, source, client)
    if args.cmd == "scan":
        bot.scan()
        bot.report()
    elif args.cmd == "status":
        bot.report()
    elif args.cmd == "run":
        bot.run_forever()


if __name__ == "__main__":
    main()
