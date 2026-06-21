"""Allocate weights across strategies using the quantum-inspired optimizer.

Weights are driven by each strategy's Monte Carlo robustness (NOT its raw
in-sample return) and a covariance estimate from their signal series, so
correlated strategies do not get double-counted.
"""
from __future__ import annotations

import numpy as np

from ..app.config import QTMSConfig, get_config
from ..quantum.quantum_portfolio_optimizer import optimize_weights


def allocate(
    strategy_names: list[str],
    robustness: dict[str, float],
    signal_series: dict[str, np.ndarray] | None = None,
    method: str = "annealing",
    cfg: QTMSConfig | None = None,
) -> dict[str, float]:
    cfg = cfg or get_config()
    if not strategy_names:
        return {}
    scores = np.array([max(0.0, robustness.get(n, 0.0)) for n in strategy_names])

    # Covariance of signal series (fallback to identity if unavailable).
    n = len(strategy_names)
    if signal_series and all(s in signal_series for s in strategy_names):
        mat = np.vstack([signal_series[s] for s in strategy_names])
        cov = np.cov(mat) if mat.shape[1] > 1 else np.eye(n) * 0.01
        cov = np.atleast_2d(cov)
        if cov.shape != (n, n):
            cov = np.eye(n) * 0.01
    else:
        cov = np.eye(n) * 0.01

    if scores.sum() == 0:
        # No robust strategy: return zero weights (the gate will reject).
        return {name: 0.0 for name in strategy_names}

    result = optimize_weights(scores, cov, method=method, seed=cfg.seed)
    w = result["weights"]
    # Re-weight by robustness so noise strategies are suppressed further.
    w = w * scores
    if w.sum() > 0:
        w = w / w.sum()
    return {name: float(wi) for name, wi in zip(strategy_names, w)}
