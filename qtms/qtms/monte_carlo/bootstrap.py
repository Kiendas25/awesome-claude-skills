"""Bootstrap resampling utilities (IID and stationary block bootstrap)."""
from __future__ import annotations

import numpy as np


def iid_bootstrap(x: np.ndarray, n_paths: int, rng: np.random.Generator) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return np.zeros((n_paths, 0))
    idx = rng.integers(0, x.size, size=(n_paths, x.size))
    return x[idx]


def block_bootstrap(
    x: np.ndarray, n_paths: int, block: int, rng: np.random.Generator
) -> np.ndarray:
    """Stationary block bootstrap — preserves short-run autocorrelation, which
    matters for trading-return series."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n == 0:
        return np.zeros((n_paths, 0))
    block = max(1, min(block, n))
    out = np.empty((n_paths, n))
    n_blocks = int(np.ceil(n / block))
    for p in range(n_paths):
        starts = rng.integers(0, n, size=n_blocks)
        pieces = [np.take(x, range(s, s + block), mode="wrap") for s in starts]
        out[p] = np.concatenate(pieces)[:n]
    return out


def bootstrap_ci(x: np.ndarray, stat=np.mean, n_paths: int = 1000, seed: int = 42):
    """Return (point, lo95, hi95) bootstrap confidence interval for ``stat``."""
    rng = np.random.default_rng(seed)
    samples = iid_bootstrap(x, n_paths, rng)
    vals = stat(samples, axis=1)
    return float(stat(np.asarray(x))), float(np.percentile(vals, 2.5)), float(
        np.percentile(vals, 97.5)
    )
