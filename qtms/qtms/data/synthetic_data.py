"""Deterministic synthetic OHLCV generation.

Produces realistic-ish crypto intraday candles using a regime-switching
geometric random walk. Fully reproducible from a seed. This is research data,
NOT a market prediction — it exists so layers can be exercised offline.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

_TIMEFRAME_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}


def generate_ohlcv(
    symbol: str = "BTC/USDT",
    n: int = 1000,
    timeframe: str = "5m",
    seed: int = 42,
    start_price: float = 30_000.0,
    start_time: datetime | None = None,
    drift: float = 0.0,
) -> pd.DataFrame:
    """Generate ``n`` deterministic OHLCV candles for ``symbol``.

    ``drift`` adds a constant per-bar log-return on top of the regime noise.
    A nonzero drift injects a *genuine* trend (a real edge) so the discovery
    loop can be exercised on data that actually contains signal; the default of
    0.0 is pure regime noise where the honest verdict is "no edge".

    Returns a DataFrame indexed by UTC timestamp with columns:
    open, high, low, close, volume, spread.
    """
    rng = np.random.default_rng(seed)
    minutes = _TIMEFRAME_MINUTES.get(timeframe, 5)
    if start_time is None:
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Regime-switching drift/vol so feature & regime layers have signal to find.
    n_regimes = max(1, n // 120)
    drifts = rng.normal(0.0, 0.0004, size=n_regimes)
    vols = np.abs(rng.normal(0.006, 0.003, size=n_regimes)) + 0.001
    regime_idx = np.repeat(np.arange(n_regimes), int(np.ceil(n / n_regimes)))[:n]

    log_returns = rng.normal(
        loc=drifts[regime_idx] + drift, scale=vols[regime_idx], size=n
    )
    close = start_price * np.exp(np.cumsum(log_returns))
    prev_close = np.concatenate([[start_price], close[:-1]])

    # Build candles around the close path.
    intrabar = np.abs(rng.normal(0.0, vols[regime_idx], size=n)) * close
    open_ = prev_close * np.exp(rng.normal(0.0, 0.0008, size=n))
    high = np.maximum(open_, close) + intrabar * rng.uniform(0.1, 1.0, size=n)
    low = np.minimum(open_, close) - intrabar * rng.uniform(0.1, 1.0, size=n)
    low = np.clip(low, 1e-6, None)

    base_vol = rng.lognormal(mean=6.0, sigma=0.5, size=n)
    volume = base_vol * (1.0 + 5.0 * np.abs(log_returns) / (vols[regime_idx]))
    spread = (close * 0.0001) * (1.0 + rng.random(n))

    idx = pd.DatetimeIndex(
        [start_time + timedelta(minutes=minutes * i) for i in range(n)],
        name="timestamp",
    )
    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "spread": spread,
        },
        index=idx,
    )
    df.attrs["symbol"] = symbol
    df.attrs["timeframe"] = timeframe
    df.attrs["synthetic"] = True
    df.attrs["seed"] = seed
    return df
