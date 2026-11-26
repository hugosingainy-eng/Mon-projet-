"""Instrument universe. `tradable` is separate from "has price data": raw indices and futures
are monitored only (an index cannot be bought, and one futures contract is far larger than the
portfolio); their liquid ETF proxies are what the paper broker may trade."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Instrument:
    symbol: str          # internal id, e.g. "BTC/EUR", "NVDA", "EURUSD"
    name: str
    asset_class: str     # crypto | equity | etf | forex | index | commodity
    provider: str        # "ccxt" | "yahoo"
    provider_symbol: str
    quote_ccy: str
    tradable: bool = True
    session: str = "us"  # 24x7 | us | eu | fx | futures
    benchmark: str | None = None   # for relative-strength / pairs
    note: str = ""


def _eq(sym, name, bench="SPY"):
    return Instrument(sym, name, "equity", "yahoo", sym, "USD", True, "us", bench)


def _etf(sym, name, bench="SPY"):
    return Instrument(sym, name, "etf", "yahoo", sym, "USD", True, "us", bench)


def _fx(pair, quote):
    return Instrument(pair, f"{pair[:3]}/{pair[3:]}", "forex", "yahoo", f"{pair}=X", quote, True, "fx",
                      None if pair == "EURUSD" else "EURUSD")


def _crypto(base, name):
    sym = f"{base}/EUR"
    return Instrument(sym, name, "crypto", "ccxt", sym, "EUR", True, "24x7",
                      None if base == "BTC" else "BTC/EUR")


def _crypto_usdt(base, name):
    """Crypto quoted in the USDT stable coin (deeper books than the EUR pair); P&L is
    converted to EUR with the exchange's own USDT/EUR market."""
    sym = f"{base}/USDT"
    return Instrument(sym, name, "crypto", "ccxt", sym, "USDT", True, "24x7", "BTC/EUR")


def _watch(sym, name, cls, ysym, ccy, session, note):
    return Instrument(sym, name, cls, "yahoo", ysym, ccy, False, session, None, note)


UNIVERSE: list[Instrument] = [
    # crypto (EUR pairs: no currency conversion for an EUR account)
    _crypto("BTC", "Bitcoin"), _crypto("ETH", "Ethereum"), _crypto("SOL", "Solana"),
    _crypto("BNB", "BNB"), _crypto("XRP", "XRP"), _crypto("DOGE", "Dogecoin"),
    _crypto("LINK", "Chainlink"), _crypto("AVAX", "Avalanche"), _crypto("ADA", "Cardano"),
    _crypto("LTC", "Litecoin"),
    # further EUR pairs; any that no reachable venue lists simply has no data and is never traded
    _crypto("DOT", "Polkadot"), _crypto("ATOM", "Cosmos"), _crypto("UNI", "Uniswap"), _crypto("TRX", "TRON"),
    _crypto("SHIB", "Shiba Inu"), _crypto("NEAR", "NEAR Protocol"), _crypto("AAVE", "Aave"),
    _crypto("XLM", "Stellar"), _crypto("BCH", "Bitcoin Cash"), _crypto("ALGO", "Algorand"),
    _crypto("SUI", "Sui"), _crypto("POL", "Polygon"),
    # liquid USDT-quoted coins (third run) and the conversion rate they need
    _crypto_usdt("ZEC", "Zcash"), _crypto_usdt("HYPE", "Hyperliquid"), _crypto_usdt("PEPE", "Pepe"),
    _crypto_usdt("OKB", "OKB"), _crypto_usdt("WLD", "Worldcoin"), _crypto_usdt("TAO", "Bittensor"),
    _crypto_usdt("FIL", "Filecoin"), _crypto_usdt("ARB", "Arbitrum"),
    Instrument("USDT/EUR", "Tether / euro", "crypto", "ccxt", "USDT/EUR", "EUR", False, "24x7", None,
               "conversion rate for USDT-quoted pairs; not traded"),
    # equities
    _eq("NVDA", "NVIDIA"), _eq("TSLA", "Tesla"), _eq("AAPL", "Apple"), _eq("MSFT", "Microsoft"),
    _eq("AMZN", "Amazon"), _eq("META", "Meta"), _eq("GOOGL", "Alphabet"), _eq("AMD", "AMD"),
    _eq("PLTR", "Palantir"), _eq("COIN", "Coinbase"), _eq("AVGO", "Broadcom"), _eq("NFLX", "Netflix"),
    _eq("JPM", "JPMorgan"), _eq("MU", "Micron"),
    # food, beverages and consumer staples
    _eq("KO", "Coca-Cola"), _eq("PEP", "PepsiCo"), _eq("MCD", "McDonald's"), _eq("MDLZ", "Mondelez"),
    _eq("GIS", "General Mills"), _eq("KHC", "Kraft Heinz"), _eq("SBUX", "Starbucks"), _eq("PG", "Procter & Gamble"),
    _eq("WMT", "Walmart"), _eq("COST", "Costco"),
    # health care
    _eq("JNJ", "Johnson & Johnson"), _eq("LLY", "Eli Lilly"), _eq("UNH", "UnitedHealth"), _eq("PFE", "Pfizer"),
    # energy and industry
    _eq("XOM", "Exxon Mobil"), _eq("CVX", "Chevron"), _eq("CAT", "Caterpillar"), _eq("BA", "Boeing"),
    _eq("GE", "GE Aerospace"),
    # finance and payments
    _eq("BAC", "Bank of America"), _eq("GS", "Goldman Sachs"), _eq("V", "Visa"), _eq("MA", "Mastercard"),
    # consumer, media and other technology
    _eq("NKE", "Nike"), _eq("DIS", "Disney"), _eq("HD", "Home Depot"), _eq("UBER", "Uber"),
    _eq("ORCL", "Oracle"), _eq("CRM", "Salesforce"), _eq("INTC", "Intel"), _eq("SHOP", "Shopify"),
    _eq("MSTR", "Strategy (MicroStrategy)"),
    # themes asked for by the owner (26 Nov 2026) -------------------------------------------
    # space
    _eq("RKLB", "Rocket Lab"), _eq("ASTS", "AST SpaceMobile"), _eq("LUNR", "Intuitive Machines"),
    # defence, weapons and drones (military software: PLTR above)
    _eq("LMT", "Lockheed Martin"), _eq("RTX", "RTX"), _eq("NOC", "Northrop Grumman"),
    _eq("GD", "General Dynamics"), _eq("LHX", "L3Harris"), _eq("AVAV", "AeroVironment (drones)"),
    _eq("KTOS", "Kratos (drones)"), _etf("ITA", "US aerospace & defence ETF"),
    # AI chips
    _eq("TSM", "TSMC"), _etf("SMH", "Semiconductor ETF"),
    # electricity, nuclear and gas
    _etf("XLU", "US utilities (electricity) ETF"), _eq("NEE", "NextEra Energy"), _eq("VST", "Vistra"),
    _eq("CEG", "Constellation Energy (nuclear)"), _eq("CCJ", "Cameco (uranium)"), _eq("OKLO", "Oklo (nuclear)"),
    _etf("URA", "Uranium ETF"), _eq("LNG", "Cheniere Energy (gas)"), _eq("EQT", "EQT (gas)"),
    _etf("XLE", "US energy (oil & gas) ETF"),
    # data centres: where AI runs
    _eq("EQIX", "Equinix (data centres)"), _eq("DLR", "Digital Realty (data centres)"),
    _eq("VRT", "Vertiv (data-centre power & cooling)"),
    # France (CAC 40 proxy)
    _etf("EWQ", "France (CAC 40 proxy) ETF"),
    # index / commodity exposure through tradable ETFs
    Instrument("SPY", "S&P 500 ETF", "etf", "yahoo", "SPY", "USD", True, "us", "QQQ"),
    _etf("QQQ", "Nasdaq 100 ETF"), _etf("DIA", "Dow Jones ETF"), _etf("EWG", "Germany (DAX proxy) ETF"),
    _etf("FEZ", "Euro Stoxx 50 ETF"), _etf("GLD", "Gold ETF"), _etf("SLV", "Silver ETF"),
    _etf("USO", "Crude oil ETF"), _etf("UNG", "Natural gas ETF"), _etf("CPER", "Copper ETF"),
    # forex
    _fx("EURUSD", "USD"), _fx("GBPUSD", "USD"), _fx("USDJPY", "JPY"), _fx("EURGBP", "GBP"),
    _fx("USDCHF", "CHF"), _fx("AUDUSD", "USD"), _fx("USDCAD", "CAD"),
    # monitored only (not tradable)
    _watch("NANC", "ETF copying trades of Democratic members of Congress", "etf", "NANC", "USD", "us",
           "too thinly traded to trade: watched as an indicator"),
    _watch("GOP", "ETF copying trades of Republican members of Congress", "etf", "GOP", "USD", "us",
           "too thinly traded to trade: watched as an indicator"),
    _watch("^FCHI", "CAC 40 index", "index", "^FCHI", "EUR", "eu", "index: monitor only, trade EWQ"),
    _watch("^GSPC", "S&P 500 index", "index", "^GSPC", "USD", "us", "index: monitor only, trade SPY"),
    _watch("^NDX", "Nasdaq 100 index", "index", "^NDX", "USD", "us", "index: monitor only, trade QQQ"),
    _watch("^DJI", "Dow Jones index", "index", "^DJI", "USD", "us", "index: monitor only, trade DIA"),
    _watch("^GDAXI", "DAX index", "index", "^GDAXI", "EUR", "eu", "index: monitor only"),
    _watch("^STOXX50E", "Euro Stoxx 50 index", "index", "^STOXX50E", "EUR", "eu", "index: monitor only"),
    _watch("GC=F", "Gold futures", "commodity", "GC=F", "USD", "futures", "contract size exceeds portfolio"),
    _watch("SI=F", "Silver futures", "commodity", "SI=F", "USD", "futures", "contract size exceeds portfolio"),
    _watch("CL=F", "WTI crude futures", "commodity", "CL=F", "USD", "futures", "contract size exceeds portfolio"),
    _watch("NG=F", "Natural gas futures", "commodity", "NG=F", "USD", "futures", "contract size exceeds portfolio"),
    _watch("HG=F", "Copper futures", "commodity", "HG=F", "USD", "futures", "contract size exceeds portfolio"),
]

BY_SYMBOL: dict[str, Instrument] = {i.symbol: i for i in UNIVERSE}

_NY = ZoneInfo("America/New_York")
_BERLIN = ZoneInfo("Europe/Berlin")


def is_market_open(inst: Instrument, now: datetime | None = None) -> bool:
    """Regular trading hours. Exchange holidays are not modelled here; on a holiday no fresh
    quote arrives, and the stale-data check blocks trading."""
    now = now or datetime.now(timezone.utc)
    s = inst.session
    if s == "24x7":
        return True
    if s == "fx":
        wd, t = now.weekday(), now.time()
        if wd == 5:
            return False
        if wd == 6:
            return t >= time(22, 0)
        if wd == 4:
            return t < time(22, 0)
        return True
    if s == "futures":
        wd, t = now.weekday(), now.time()
        if wd == 5 or (wd == 6 and t < time(23, 0)) or (wd == 4 and t >= time(22, 0)):
            return False
        return True
    local = now.astimezone(_NY if s == "us" else _BERLIN)
    if local.weekday() >= 5:
        return False
    if s == "us":
        return time(9, 30) <= local.time() < time(16, 0)
    return time(9, 0) <= local.time() < time(17, 30)


def annualization(inst_class: str) -> int:
    return 365 if inst_class == "crypto" else 252
