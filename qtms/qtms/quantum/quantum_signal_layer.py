"""Quantum Signal Layer (quantum-inspired).

Combines the encoded feature state with directional 'reference' states for
long / short / flat using interference (inner products / overlaps). Measurement
probabilities over the three outcomes give a directional signal plus a
calibrated uncertainty. No qiskit required; clearly labelled quantum-inspired.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..app.config import get_config
from ..app.schemas import LayerResult, Signal, utcnow
from .quantum_state_encoder import ENCODE_FEATURES, encode_state, probabilities

# Directional reference vectors over ENCODE_FEATURES: which features 'vote' long.
# Sign = directional contribution; magnitude = weight. Hand-set, deterministic.
_LONG_REF = np.array([1.0, 1.0, 1.0, -0.5, -0.5, 0.0, 0.3, 0.5])


def _reference_states() -> dict[str, np.ndarray]:
    long_amps = np.sqrt(np.abs(_LONG_REF) + 1e-6)
    long_state = (long_amps * np.exp(1j * np.where(_LONG_REF >= 0, 0.0, np.pi)))
    long_state = long_state / np.linalg.norm(long_state)
    short_state = np.conj(long_state) * np.exp(1j * np.pi)
    short_state = short_state / np.linalg.norm(short_state)
    # Flat reference: uniform superposition (no directional structure).
    flat_state = np.ones(len(_LONG_REF), dtype=complex)
    flat_state = flat_state / np.linalg.norm(flat_state)
    return {"long": long_state, "short": short_state, "flat": flat_state}


def quantum_signal(feature_row: dict[str, float]) -> dict:
    state = encode_state(feature_row)
    refs = _reference_states()
    # Interference amplitudes = overlap <ref|psi>; probability = |overlap|^2.
    overlaps = {k: complex(np.vdot(v, state)) for k, v in refs.items()}
    raw = {k: abs(o) ** 2 for k, o in overlaps.items()}
    total = sum(raw.values()) or 1.0
    probs = {k: v / total for k, v in raw.items()}
    signal = probs["long"] - probs["short"]
    # Uncertainty from the entropy of the outcome distribution (normalized).
    p = np.array(list(probs.values()))
    entropy = -np.sum(p * np.log(p + 1e-12)) / np.log(len(p))
    return {
        "probs": probs,
        "signal": float(signal),
        "uncertainty": float(entropy),
        "measurement_distribution": probs,
    }


def evaluate(df: pd.DataFrame, features: pd.DataFrame) -> LayerResult:
    row = features[ [c for c in ENCODE_FEATURES if c in features.columns] ].iloc[-1].to_dict()
    q = quantum_signal(row)
    return LayerResult(
        layer_name="quantum_signal",
        timestamp=utcnow(),
        symbol=str(df.attrs.get("symbol", "UNKNOWN")),
        signal=q["signal"],
        confidence=float(max(q["probs"]["long"], q["probs"]["short"])),
        uncertainty=q["uncertainty"],
        monte_carlo_summary={},
        warnings=["quantum-inspired (no qiskit hardware)"],
        metadata={
            "measurement_distribution": q["measurement_distribution"],
            "direction": Signal.from_float(q["signal"]).value,
            "method": "interference_overlap",
        },
    )
