"""Quantum State Encoder (quantum-inspired).

Encodes a normalized market-feature vector into a unit-norm 'state vector' whose
squared amplitudes are a valid probability distribution over feature basis
states. This is amplitude encoding in spirit; it requires no quantum hardware.
"""
from __future__ import annotations

import numpy as np

# Features selected for encoding (kept small so amplitudes stay interpretable).
ENCODE_FEATURES = [
    "ma_spread",
    "slope",
    "momentum",
    "zscore",
    "vwap_dist",
    "atr_pct",
    "vol_regime",
    "wick_skew",
]


def _squash(x: float) -> float:
    return float(np.tanh(x))


def encode_state(feature_row: dict[str, float]) -> np.ndarray:
    """Return a unit-norm complex amplitude vector for the given features.

    Amplitudes encode normalized feature *importance* (magnitude) with a phase
    carrying the feature's sign — enabling interference in the signal layer.
    """
    mags = []
    phases = []
    for name in ENCODE_FEATURES:
        v = _squash(float(feature_row.get(name, 0.0)))
        mags.append(abs(v) + 1e-6)  # avoid all-zero degenerate state
        phases.append(0.0 if v >= 0 else np.pi)
    mags = np.asarray(mags, dtype=float)
    amps = np.sqrt(mags / mags.sum())  # Born-rule normalization on probabilities
    state = amps * np.exp(1j * np.asarray(phases))
    return state / np.linalg.norm(state)


def is_normalized(state: np.ndarray, tol: float = 1e-9) -> bool:
    return bool(abs(np.linalg.norm(state) - 1.0) < tol)


def probabilities(state: np.ndarray) -> np.ndarray:
    """Born-rule measurement probabilities |amplitude|^2 (sums to 1)."""
    p = np.abs(state) ** 2
    return p / p.sum()
