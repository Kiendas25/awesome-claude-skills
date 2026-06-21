"""Stacking + conviction gate: weak signals must be rejected by default."""
from __future__ import annotations

from qtms.app.schemas import Signal, StackDecision
from qtms.stacking.conviction_gate import GateInputs, evaluate_gate
from qtms.stacking.signal_stack import SignalStack


def test_gate_rejects_low_conviction(cfg):
    g = GateInputs(
        conviction=0.1, prob_positive_expectancy=0.9, risk_of_ruin=0.0,
        max_drawdown_sim=0.01, disagreement=0.0, regime="trend_up",
        data_quality=1.0, signal_stability=1.0, cost_survival=1.0,
    )
    out = evaluate_gate(g, cfg)
    assert not out["approved"]
    assert "failed: conviction" in out["reject_reasons"]


def test_gate_approves_strong_inputs(cfg):
    g = GateInputs(
        conviction=0.9, prob_positive_expectancy=0.9, risk_of_ruin=0.0,
        max_drawdown_sim=0.01, disagreement=0.0, regime="trend_up",
        data_quality=1.0, signal_stability=1.0, cost_survival=1.0,
    )
    out = evaluate_gate(g, cfg)
    assert out["approved"]


def test_stack_produces_decision_and_is_conservative(cfg, df):
    cfg.monte_carlo.n_paths = 20
    dec = SignalStack(cfg).decide(df, seed=7)
    assert isinstance(dec, StackDecision)
    assert 0.0 <= dec.conviction <= 1.0
    # On edgeless synthetic data the system should default to FLAT / rejected.
    if not dec.approved:
        assert dec.final_signal == Signal.FLAT
        assert dec.position_size == 0.0
        assert len(dec.reject_reasons) > 0
    assert len(dec.layer_results) >= 8  # data, features, strategies, quantum x2
