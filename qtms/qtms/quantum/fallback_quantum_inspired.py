"""Quantum backend selector + optional qiskit circuit demo.

The core system is fully functional WITHOUT qiskit. If qiskit happens to be
installed, ``qiskit_circuit_demo`` encodes features as RY rotation angles on a
small circuit and returns measurement probabilities — purely illustrative. The
rest of QTMS never depends on it.
"""
from __future__ import annotations

import numpy as np

try:  # pragma: no cover - exercised only when qiskit is present
    import qiskit  # noqa: F401

    QISKIT_AVAILABLE = True
except Exception:
    QISKIT_AVAILABLE = False


def backend_label() -> str:
    return "qiskit" if QISKIT_AVAILABLE else "quantum-inspired (classical fallback)"


def qiskit_circuit_demo(feature_values: list[float], shots: int = 1024) -> dict:
    """Encode features as RY angles, simulate, return measurement counts.

    Returns a clearly-labelled fallback result if qiskit is unavailable so
    callers get a uniform shape either way.
    """
    angles = [float(np.pi * np.tanh(v)) for v in feature_values[:4]]
    if not QISKIT_AVAILABLE:
        # Deterministic classical analogue of measurement probabilities.
        probs = [np.cos(a / 2) ** 2 for a in angles]
        return {
            "backend": backend_label(),
            "available": False,
            "angles": angles,
            "p_zero_per_qubit": probs,
            "note": "qiskit not installed; classical analogue returned",
        }
    # pragma: no cover below — only runs with qiskit installed.
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    from qiskit import transpile

    n = len(angles)
    qc = QuantumCircuit(n, n)
    for i, a in enumerate(angles):
        qc.ry(a, i)
    qc.measure(range(n), range(n))
    sim = AerSimulator()
    result = sim.run(transpile(qc, sim), shots=shots).result()
    counts = result.get_counts()
    return {
        "backend": backend_label(),
        "available": True,
        "angles": angles,
        "counts": counts,
        "shots": shots,
    }
