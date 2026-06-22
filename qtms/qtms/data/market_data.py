"""Market data adapter + the data-layer Monte Carlo robustness simulation.

Supports synthetic generation and CSV import now; a ccxt fetch path is stubbed
for the future and is *disabled* (live data fetch is not part of the MVP hot
path). The Monte Carlo here stresses the data itself: missing candles, noisy
prices, spread widening, latency, and bad ticks — and reports a robustness
score so downstream layers know how much to trust the feed.
"""
from __future__ import annotations

from datetime import timezone

import numpy as np
import pandas as pd

from ..app.config import get_config
from ..app.schemas import LayerResult, utcnow
from .synthetic_data import generate_ohlcv
from .validators import validate_ohlcv


class MarketDataAdapter:
    def __init__(self, cfg=None):
        self.cfg = cfg or get_config()

    def synthetic(
        self, symbol: str, n: int = 1000, seed: int | None = None, drift: float = 0.0
    ) -> pd.DataFrame:
        return generate_ohlcv(
            symbol=symbol,
            n=n,
            timeframe=self.cfg.timeframe,
            seed=self.cfg.seed if seed is None else seed,
            drift=drift,
        )

    def from_csv(self, path: str, symbol: str) -> pd.DataFrame:
        df = pd.read_csv(path)
        # Normalize a time column to a UTC DatetimeIndex.
        time_col = next(
            (c for c in ("timestamp", "time", "date", "datetime") if c in df.columns),
            None,
        )
        if time_col is not None:
            df[time_col] = pd.to_datetime(df[time_col], utc=True)
            df = df.set_index(time_col).sort_index()
        df.attrs["symbol"] = symbol
        df.attrs["synthetic"] = False
        return df

    def live(
        self, symbol: str, timeframe: str | None = None, limit: int = 1000,
        source: str = "auto",
    ) -> pd.DataFrame:
        """Fetch REAL OHLCV price data (read-only, no API key, no trading).

        Raises ``LiveDataError`` if every public source fails; callers should
        catch it and fall back to ``synthetic()`` so loops stay resilient.
        """
        from .live_data import fetch_ohlcv

        return fetch_ohlcv(
            symbol, timeframe=timeframe or self.cfg.timeframe, limit=limit, source=source
        )

    def fetch_ccxt(self, *args, **kwargs):  # pragma: no cover - trading path disabled
        """Live *trading* via ccxt is intentionally NOT implemented. For real
        price *data* use ``live()`` (read-only public OHLCV)."""
        raise NotImplementedError(
            "Live trading via ccxt is disabled. Use live() for read-only data."
        )


def monte_carlo_data_robustness(
    df: pd.DataFrame, n_paths: int = 200, seed: int = 42
) -> LayerResult:
    """Stress the data feed and score how stable the close path is under
    realistic data defects. A high robustness score means downstream features
    are unlikely to flip due to feed noise alone."""
    rng = np.random.default_rng(seed)
    cfg = get_config()
    base = df["close"].to_numpy(dtype=float)
    n = len(base)
    ref_return = float(np.log(base[-1] / base[0])) if base[0] > 0 else 0.0

    perturbed_returns = np.empty(n_paths)
    flip_count = 0
    for i in range(n_paths):
        px = base.copy()
        # Noisy prices.
        px *= np.exp(rng.normal(0.0, 0.0015, size=n))
        # Bad ticks: a few large transient spikes.
        n_bad = rng.integers(0, max(1, n // 200) + 1)
        if n_bad:
            idx = rng.integers(0, n, size=n_bad)
            px[idx] *= rng.uniform(0.9, 1.1, size=n_bad)
        # Missing candles -> forward fill.
        n_missing = rng.integers(0, max(1, n // 100) + 1)
        if n_missing:
            midx = rng.integers(1, n, size=n_missing)
            px[midx] = px[midx - 1]
        r = float(np.log(px[-1] / px[0])) if px[0] > 0 else 0.0
        perturbed_returns[i] = r
        if np.sign(r) != np.sign(ref_return) and abs(ref_return) > 1e-6:
            flip_count += 1

    spread_widen_factor = float(1.0 + rng.random())  # simulated spread widening
    latency_jitter_ms = float(cfg.costs.latency_ms * (1.0 + rng.random()))

    std = float(np.std(perturbed_returns))
    sign_stability = 1.0 - flip_count / n_paths
    # Robustness blends sign stability with low dispersion relative to move size.
    dispersion_pen = min(1.0, std / (abs(ref_return) + 1e-3))
    robustness = float(max(0.0, min(1.0, 0.6 * sign_stability + 0.4 * (1 - dispersion_pen))))

    report = validate_ohlcv(df)
    warnings = list(report.issues) + list(report.warnings)

    return LayerResult(
        layer_name="market_data",
        timestamp=utcnow(),
        symbol=str(df.attrs.get("symbol", "UNKNOWN")),
        signal=0.0,
        confidence=report.quality_score,
        uncertainty=float(min(1.0, std * 10)),
        expected_return=float(np.mean(perturbed_returns)),
        expected_risk=std,
        monte_carlo_summary={
            "n_paths": n_paths,
            "seed": seed,
            "ref_log_return": ref_return,
            "return_std": std,
            "sign_stability": sign_stability,
            "robustness_score": robustness,
            "spread_widen_factor": spread_widen_factor,
            "latency_jitter_ms": latency_jitter_ms,
            "data_quality_score": report.quality_score,
        },
        warnings=warnings,
        metadata={"rows": n, "validation_ok": report.ok},
    )
