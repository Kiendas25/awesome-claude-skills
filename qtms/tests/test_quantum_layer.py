"""Quantum-inspired layer tests."""
from __future__ import annotations

import numpy as np

from qtms.features.pipeline import compute_features
from qtms.quantum.fallback_quantum_inspired import backend_label, qiskit_circuit_demo
from qtms.quantum.quantum_monte_carlo import monte_carlo_quantum
from qtms.quantum.quantum_portfolio_optimizer import (
    optimize_weights,
    risk_parity_weights,
    softmax_weights,
)
from qtms.quantum.quantum_signal_layer import evaluate, quantum_signal
from qtms.quantum.quantum_state_encoder import encode_state, is_normalized, probabilities


def test_encoder_produces_normalized_state():
    state = encode_state({"ma_spread": 0.4, "slope": -0.2, "momentum": 0.1, "zscore": 1.0})
    assert is_normalized(state)
    p = probabilities(state)
    assert np.isclose(p.sum(), 1.0)
    assert (p >= 0).all()


def test_encoder_handles_all_zero_features():
    state = encode_state({})
    assert is_normalized(state)


def test_quantum_signal_probabilities_sum_to_one():
    q = quantum_signal({"ma_spread": 0.5, "slope": 0.3, "momentum": 0.2})
    s = q["probs"]["long"] + q["probs"]["short"] + q["probs"]["flat"]
    assert np.isclose(s, 1.0)
    assert -1.0 <= q["signal"] <= 1.0


def test_quantum_layer_evaluate(df):
    feats = compute_features(df)
    res = evaluate(df, feats)
    assert res.layer_name == "quantum_signal"
    assert "measurement_distribution" in res.metadata


def test_quantum_monte_carlo_stability(df):
    feats = compute_features(df)
    res = monte_carlo_quantum(df, feats, n_paths=50, seed=7)
    stab = res.monte_carlo_summary["quantum_signal_stability"]
    assert 0.0 <= stab <= 1.0
    dist = res.monte_carlo_summary["measurement_distribution"]
    assert set(dist.keys()) == {"long", "short", "flat"}


def test_portfolio_optimizer_weights_valid():
    scores = np.array([0.6, 0.2, 0.9, 0.1])
    cov = np.eye(4) * 0.02
    for method in ("annealing", "softmax", "risk_parity"):
        out = optimize_weights(scores, cov, method=method, seed=7)
        w = out["weights"]
        assert np.isclose(w.sum(), 1.0, atol=1e-6)
        assert (w >= -1e-9).all()
    assert np.isclose(softmax_weights(scores).sum(), 1.0)
    assert np.isclose(risk_parity_weights(cov).sum(), 1.0)


def test_works_without_qiskit():
    # Core system must not require qiskit; demo returns a labelled fallback.
    out = qiskit_circuit_demo([0.5, -0.3, 0.1, 0.2])
    assert "backend" in out
    assert isinstance(backend_label(), str)
