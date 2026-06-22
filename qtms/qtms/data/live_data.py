"""Real / live market-data fetch (READ-ONLY public OHLCV).

IMPORTANT: this fetches *price data only* from public exchange endpoints. It
needs no API key and CANNOT place orders — live *trading* remains disabled and
unimplemented. Pulling the latest candles each loop is what "live data" means
here (true tick streams are unnecessary for intraday research).

Resilient by design: tries ccxt (if installed), then public REST endpoints
(Binance → Coinbase → Kraken). All network I/O goes through ``_http_get_json``
so it can be mocked in tests. Callers should handle ``LiveDataError`` and fall
back to synthetic data so an autonomous loop never crashes on a network blip.
"""
from __future__ import annotations

import json
import urllib.request

import numpy as np
import pandas as pd

from ..app.schemas import utcnow  # noqa: F401  (kept for parity/imports)
from .validators import validate_ohlcv


class LiveDataError(RuntimeError):
    pass


# timeframe -> (binance interval, kraken minutes, coinbase granularity seconds)
_TF = {
    "1m": ("1m", 1, 60),
    "5m": ("5m", 5, 300),
    "15m": ("15m", 15, 900),
    "1h": ("1h", 60, 3600),
    "4h": ("4h", 240, 14400),
    "1d": ("1d", 1440, 86400),
}


def _http_get_json(url: str, timeout: float = 10.0):
    """Single network seam (mock this in tests)."""
    req = urllib.request.Request(url, headers={"User-Agent": "qtms/0.1 (research)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _split(symbol: str) -> tuple[str, str]:
    if "/" in symbol:
        base, quote = symbol.split("/", 1)
    else:  # e.g. BTCUSDT -> best-effort split on common quotes
        for q in ("USDT", "USDC", "USD", "EUR", "BTC"):
            if symbol.upper().endswith(q):
                return symbol[: -len(q)].upper(), q
        base, quote = symbol[:-3].upper(), symbol[-3:].upper()
    return base.upper(), quote.upper()


# --- providers: each returns list[(ts_ms, open, high, low, close, volume)] ----
def _from_binance(symbol: str, timeframe: str, limit: int):
    base, quote = _split(symbol)
    interval = _TF[timeframe][0]
    url = (
        f"https://api.binance.com/api/v3/klines?symbol={base}{quote}"
        f"&interval={interval}&limit={min(limit, 1000)}"
    )
    data = _http_get_json(url)
    rows = [
        (int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]))
        for k in data
    ]
    return rows[-limit:]


def _from_coinbase(symbol: str, timeframe: str, limit: int):
    base, quote = _split(symbol)
    if quote == "USDT":
        quote = "USD"  # Coinbase uses USD spot products
    gran = _TF[timeframe][2]
    url = (
        f"https://api.exchange.coinbase.com/products/{base}-{quote}/candles"
        f"?granularity={gran}"
    )
    data = _http_get_json(url)  # [[time_s, low, high, open, close, volume], ...] newest first
    rows = [
        (int(c[0]) * 1000, float(c[3]), float(c[2]), float(c[1]), float(c[4]), float(c[5]))
        for c in data
    ]
    rows.sort(key=lambda r: r[0])
    return rows[-limit:]


def _from_kraken(symbol: str, timeframe: str, limit: int):
    base, quote = _split(symbol)
    if base == "BTC":
        base = "XBT"  # Kraken uses XBT
    minutes = _TF[timeframe][1]
    url = f"https://api.kraken.com/0/public/OHLC?pair={base}{quote}&interval={minutes}"
    data = _http_get_json(url)
    if data.get("error"):
        raise LiveDataError(f"kraken error: {data['error']}")
    result = data.get("result", {})
    key = next((k for k in result if k != "last"), None)
    if not key:
        raise LiveDataError("kraken: no result series")
    rows = [
        (int(c[0]) * 1000, float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[6]))
        for c in result[key]
    ]
    return rows[-limit:]


_PROVIDERS = {
    "binance": _from_binance,
    "coinbase": _from_coinbase,
    "kraken": _from_kraken,
}
_DEFAULT_ORDER = ["binance", "coinbase", "kraken"]


def _to_df(rows: list, symbol: str, timeframe: str, source: str) -> pd.DataFrame:
    if not rows:
        raise LiveDataError("no rows returned")
    arr = np.array(rows, dtype=float)
    idx = pd.to_datetime(arr[:, 0].astype("int64"), unit="ms", utc=True)
    df = pd.DataFrame(
        {
            "open": arr[:, 1],
            "high": arr[:, 2],
            "low": arr[:, 3],
            "close": arr[:, 4],
            "volume": arr[:, 5],
        },
        index=pd.DatetimeIndex(idx, name="timestamp"),
    )
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df["spread"] = df["close"] * 0.0001  # placeholder; real L1 spread not in OHLCV
    df.attrs.update(
        {"symbol": symbol, "timeframe": timeframe, "synthetic": False, "source": source}
    )
    return df


def fetch_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "5m",
    limit: int = 1000,
    source: str = "auto",
) -> pd.DataFrame:
    """Fetch real OHLCV. ``source`` is 'auto' or one of binance/coinbase/kraken.

    Tries ccxt first if installed and a specific exchange is named; otherwise
    walks the public REST fallback chain. Raises ``LiveDataError`` if all fail.
    """
    if timeframe not in _TF:
        raise LiveDataError(f"unsupported timeframe: {timeframe}")

    # Optional ccxt path (only if the user has it AND named an exchange).
    if source not in ("auto", *_PROVIDERS):
        try:  # pragma: no cover - exercised only when ccxt + exchange present
            import ccxt

            ex = getattr(ccxt, source)()
            raw = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            return _to_df([tuple(r) for r in raw], symbol, timeframe, f"ccxt:{source}")
        except Exception as e:
            raise LiveDataError(f"ccxt source '{source}' failed: {e}")

    order = _DEFAULT_ORDER if source == "auto" else [source]
    errors = []
    for name in order:
        try:
            rows = _PROVIDERS[name](symbol, timeframe, limit)
            df = _to_df(rows, symbol, timeframe, name)
            report = validate_ohlcv(df)
            df.attrs["data_quality_score"] = report.quality_score
            return df
        except Exception as e:  # try the next provider
            errors.append(f"{name}: {type(e).__name__} {str(e)[:60]}")
    raise LiveDataError("all live data sources failed -> " + " | ".join(errors))
