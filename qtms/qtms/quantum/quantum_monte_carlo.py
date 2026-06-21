"""Quantum-inspired Monte Carlo for the signal layer.

Simulates measurement under perturbed conditions: amplitude noise, regime
shifts and covariance shifts. The transition between 'up/down/flat' states is
treated as a probabilistic (Born-rule) process, hence quantum-inspired — but it
is honest classical sampling, not 'magic quantum'.

Outputs ``quantum_signal_stability`` and a ``measurement_distribution``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..app.schemas import LayerResult, utcnow
from .quantum_signal_layer import quantum_signal
from .quantum_state_encoder import ENCODE_FEATURES


def monte_carlo_quantum(
    df: pd.DataFrame,
    features: pd.DataFrame,
    n_paths: int = 200,
    seed: int = 42,
) -> LayerResult:
    rng = np.random.default_rng(seed)
    base_row = {
        c: float(features[c].iloc[-1]) for c in ENCODE_FEATURES if c in features.columns
    }
    base = quantum_signal(base_row)
    base_dir = np.sign(base["signal"])

    signals = np.empty(n_paths)
    long_p = np.empty(n_paths)
    short_p = np.empty(n_paths)
    flip = 0
    for i in range(n_paths):
        row = {}
        for k, v in base_row.items():
            # Amplitude noise + occasional regime shift (sign flip of a feature).
            noise = rng.normal(0.0, 0.1)
            val = v + noise
            if rng.random() < 0.03:  # regime/covariance shift shock
                val = -val * rng.uniform(0.5, 1.5)
            row[k] = val
        q = quantum_signal(row)
        signals[i] = q["signal"]
        long_p[i] = q["probs"]["long"]
        short_p[i] = q["probs"]["short"]
        if np.sign(q["signal"]) != base_dir and base_dir != 0:
            flip += 1

    stability = 1.0 - flip / n_paths
    return LayerResult(
        layer_name="quantum_monte_carlo",
        timestamp=utcnow(),
        symbol=str(df.attrs.get("symbol", "UNKNOWN")),
        signal=float(np.mean(signals)),
        confidence=float(max(np.mean(long_p), np.mean(short_p))),
        uncertainty=float(np.std(signals)),
        monte_carlo_summary={
            "n_paths": n_paths,
            "seed": seed,
            "quantum_signal_stability": float(stability),
            "signal_mean": float(np.mean(signals)),
            "signal_std": float(np.std(signals)),
            "measurement_distribution": {
                "long": float(np.mean(long_p)),
                "short": float(np.mean(short_p)),
                "flat": float(1.0 - np.mean(long_p) - np.mean(short_p)),
            },
        },
        warnings=["quantum-inspired Monte Carlo"]
        + (["unstable quantum signal"] if stability < 0.5 else []),
        metadata={"base_signal": base["signal"]},
    )
