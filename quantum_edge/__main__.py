"""Command line:  python -m quantum_edge [serve|selfcheck|stop|backup [file]|restore [file]]"""
from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

from .config import load_settings


def _pidfile(settings) -> Path:
    return Path(settings.db_path).parent / "quantum_edge.pid"


def serve():
    import uvicorn
    from .api import create_app
    settings = load_settings()
    app = create_app(settings)
    pid = _pidfile(settings)
    pid.parent.mkdir(parents=True, exist_ok=True)
    pid.write_text(str(os.getpid()))
    print(f"Quantum Edge AI (PAPER TRADING ONLY) — dashboard: http://{settings.host}:{settings.port}")
    try:
        uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
    finally:
        pid.unlink(missing_ok=True)


def stop():
    """Stops the application process. The experiment state is kept and resumes at next start."""
    pid = _pidfile(load_settings())
    if not pid.exists():
        print("not running (no pid file)")
        return
    try:
        os.kill(int(pid.read_text()), signal.SIGTERM)
        print("stop signal sent; the experiment will resume from the database at next start")
    except (ProcessLookupError, OSError) as e:
        print(f"process not found ({e})")
    pid.unlink(missing_ok=True)


def selfcheck() -> int:
    """Checks every live data source from THIS computer. Nothing is traded."""
    from .data.ccxt_provider import CcxtProvider
    from .data.yahoo_provider import YahooProvider
    from .instruments import BY_SYMBOL, UNIVERSE
    s = load_settings()
    failures = 0

    def check(label, fn):
        nonlocal failures
        try:
            print(f"[ OK ] {label}: {fn()}")
        except Exception as e:
            failures += 1
            print(f"[FAIL] {label}: {type(e).__name__}: {e}")

    cx, yh = CcxtProvider(s.crypto_exchanges, s.crypto_history_exchanges), YahooProvider()
    cryptos = [i for i in UNIVERSE if i.provider == "ccxt"]

    def crypto_quotes():
        q = cx.quotes(cryptos)
        missing = [i.symbol for i in cryptos if i.symbol not in q]
        return f"{len(q)}/{len(cryptos)} quotes" + (f" (not listed: {', '.join(missing)})" if missing else "")
    check(f"crypto quotes via {s.crypto_exchanges}", crypto_quotes)
    check("crypto 15m history BTC/EUR", lambda: (lambda d: f"{len(d)} bars from {d.attrs.get('source')}")(cx.history(BY_SYMBOL['BTC/EUR'], '15m', 12000)))
    check("crypto order book BTC/EUR", lambda: cx.order_book(BY_SYMBOL["BTC/EUR"]))
    check("funding rate BTC (optional)", lambda: cx.funding_rate("BTC") if cx.funding_rate("BTC") is not None else "not accessible (optional)")
    others = [i for i in UNIVERSE if i.provider == "yahoo"]

    def yahoo_quotes():
        q = yh.quotes(others)
        return f"{len(q)}/{len(others)} quotes (closed markets return their last session)"
    check("Yahoo quotes (stocks, ETFs, forex, indices, futures)", yahoo_quotes)
    check("Yahoo 15m history NVDA", lambda: f"{len(yh.history(BY_SYMBOL['NVDA'], '15m', 100000))} bars")
    check("Yahoo 1h history EURUSD", lambda: f"{len(yh.history(BY_SYMBOL['EURUSD'], '1h', 100000))} bars")
    check("Yahoo batched 1h history", lambda: f"{len(yh.history_many(others[:8], '1h'))}/8 instruments")
    check("Yahoo news NVDA", lambda: f"{len(yh.news(BY_SYMBOL['NVDA']))} headlines")
    print("\nAll data sources reachable." if not failures else f"\n{failures} check(s) failed — see above.")
    return 1 if failures else 0


def backup_cmd(path: str):
    from .backup import save
    from .db import Database
    print("backup written to", save(Database(load_settings().db_path), path))


def restore_cmd(path: str):
    from .backup import restore
    from .db import Database
    print(restore(Database(load_settings().db_path), path))


def main():
    for stream in (sys.stdout, sys.stderr):      # never crash on a console that lacks a character
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "serve":
        serve()
    elif cmd == "stop":
        stop()
    elif cmd == "selfcheck":
        sys.exit(selfcheck())
    elif cmd in ("backup", "restore"):
        path = sys.argv[2] if len(sys.argv) > 2 else "backup/state.json"
        backup_cmd(path) if cmd == "backup" else restore_cmd(path)
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
