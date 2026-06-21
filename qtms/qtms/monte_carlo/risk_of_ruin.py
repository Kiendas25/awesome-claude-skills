"""Risk-of-ruin estimation via Monte Carlo resampling of trade outcomes.

Risk of ruin = probability that equity falls below a ruin threshold within a
horizon, given the empirical distribution of per-trade returns. We never assume
a clean Gaussian; we resample observed outcomes (with replacement)."""
from __future__ import annotations

import numpy as np


def risk_of_ruin(
    trade_returns: np.ndarray,
    n_paths: int = 1000,
    horizon: int | None = None,
    ruin_drawdown: float = 0.5,
    seed: int = 42,
) -> dict:
    """Estimate probability of hitting ``ruin_drawdown`` peak-to-trough.

    ``trade_returns`` are fractional per-trade returns (e.g. +0.01 = +1%).
    Returns a dict with risk_of_ruin and the drawdown distribution percentiles.
    """
    trade_returns = np.asarray(trade_returns, dtype=float)
    if trade_returns.size == 0:
        return {
            "risk_of_ruin": 1.0,
            "max_dd_p50": 1.0,
            "max_dd_p95": 1.0,
            "n_paths": 0,
            "note": "no trades -> assume worst case",
        }
    rng = np.random.default_rng(seed)
    horizon = horizon or max(20, trade_returns.size)
    ruined = 0
    max_dds = np.empty(n_paths)
    for i in range(n_paths):
        sampled = rng.choice(trade_returns, size=horizon, replace=True)
        equity = np.cumprod(1.0 + sampled)
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        mdd = float(dd.max())
        max_dds[i] = mdd
        if mdd >= ruin_drawdown:
            ruined += 1
    return {
        "risk_of_ruin": ruined / n_paths,
        "max_dd_p50": float(np.percentile(max_dds, 50)),
        "max_dd_p95": float(np.percentile(max_dds, 95)),
        "horizon": horizon,
        "n_paths": n_paths,
        "ruin_drawdown": ruin_drawdown,
        "seed": seed,
    }
