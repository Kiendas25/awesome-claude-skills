"""Quantum-inspired portfolio / strategy weight optimizer.

Provides risk-parity, softmax, and a simulated-annealing search over weights
that maximizes a covariance-aware risk-adjusted score. 'Quantum-inspired' here
means the annealing uses a temperature schedule and probabilistic acceptance —
analogous to quantum annealing, implemented classically and deterministically.
"""
from __future__ import annotations

import numpy as np


def risk_parity_weights(cov: np.ndarray) -> np.ndarray:
    vol = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    inv = 1.0 / vol
    return inv / inv.sum()


def softmax_weights(scores: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    z = scores / max(temperature, 1e-6)
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def _objective(w: np.ndarray, scores: np.ndarray, cov: np.ndarray, risk_aversion: float) -> float:
    ret = float(w @ scores)
    var = float(w @ cov @ w)
    return ret - risk_aversion * var


def simulated_annealing_weights(
    scores: np.ndarray,
    cov: np.ndarray,
    risk_aversion: float = 2.0,
    steps: int = 800,
    seed: int = 42,
) -> np.ndarray:
    """Anneal toward weights maximizing risk-adjusted score. Deterministic via
    the seed. Weights are non-negative and sum to 1 (long-only allocation of
    capital across strategy *confidence*, not directional bets)."""
    rng = np.random.default_rng(seed)
    n = len(scores)
    w = np.ones(n) / n
    best = w.copy()
    best_obj = _objective(w, scores, cov, risk_aversion)
    cur_obj = best_obj
    for t in range(steps):
        temp = max(1e-3, 1.0 * (1.0 - t / steps))
        cand = w + rng.normal(0.0, 0.1, size=n)
        cand = np.clip(cand, 0.0, None)
        s = cand.sum()
        if s == 0:
            continue
        cand /= s
        obj = _objective(cand, scores, cov, risk_aversion)
        if obj > cur_obj or rng.random() < np.exp((obj - cur_obj) / temp):
            w, cur_obj = cand, obj
            if obj > best_obj:
                best, best_obj = cand.copy(), obj
    return best


def optimize_weights(
    scores: np.ndarray,
    cov: np.ndarray | None = None,
    method: str = "annealing",
    seed: int = 42,
) -> dict:
    scores = np.asarray(scores, dtype=float)
    n = len(scores)
    if cov is None:
        cov = np.eye(n) * 0.01
    if method == "risk_parity":
        w = risk_parity_weights(cov)
    elif method == "softmax":
        w = softmax_weights(scores)
    else:
        w = simulated_annealing_weights(scores, cov, seed=seed)
    return {
        "weights": w,
        "method": method,
        "objective": _objective(w, scores, cov, 2.0),
    }
