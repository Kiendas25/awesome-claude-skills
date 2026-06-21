"""Meta-model: combine weighted strategy signals with the quantum signal.

Produces a combined directional signal, a conviction proxy, and a
strategy-disagreement measure. Deterministic; no learning at runtime (any
learning happens off-path in the agents package and is applied via config).
"""
from __future__ import annotations

import numpy as np


def combine(
    signals: dict[str, float],
    weights: dict[str, float],
    quantum_signal: float,
    quantum_weight: float = 0.25,
) -> dict:
    names = [n for n in signals if weights.get(n, 0.0) > 0]
    if not names:
        return {
            "combined_signal": 0.0,
            "disagreement": 1.0,
            "weighted_strategy_signal": 0.0,
            "n_contributing": 0,
        }
    w = np.array([weights[n] for n in names])
    s = np.array([signals[n] for n in names])
    w = w / w.sum()
    weighted = float(np.dot(w, s))

    # Disagreement: weighted std of directional sign + dispersion of magnitudes.
    signs = np.sign(s)
    mean_sign = float(np.dot(w, signs))
    disagreement = float(np.clip(1.0 - abs(mean_sign), 0.0, 1.0))

    combined = (1 - quantum_weight) * weighted + quantum_weight * quantum_signal
    return {
        "combined_signal": float(np.clip(combined, -1, 1)),
        "weighted_strategy_signal": weighted,
        "quantum_signal": quantum_signal,
        "disagreement": disagreement,
        "n_contributing": len(names),
        "contributing": names,
    }
