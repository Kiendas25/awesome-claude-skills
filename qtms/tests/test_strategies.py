"""Each strategy must return a valid LayerResult with required fields."""
from __future__ import annotations

import pytest

from qtms.app.schemas import LayerResult
from qtms.features.pipeline import compute_features
from qtms.strategies import REGISTRY, build_strategy


@pytest.mark.parametrize("name", list(REGISTRY.keys()))
def test_strategy_returns_valid_layer_result(name, df, cfg):
    cfg.monte_carlo.n_paths = 30
    strat = build_strategy(name, cfg=cfg)
    res = strat.evaluate(df, run_mc=True, seed=7)
    assert isinstance(res, LayerResult)
    assert res.layer_name == f"strategy:{name}"
    assert -1.0 <= res.signal <= 1.0
    assert 0.0 <= res.confidence <= 1.0
    assert 0.0 <= res.uncertainty <= 1.0
    assert "robustness_score" in res.monte_carlo_summary
    assert "reason_codes" in res.metadata
    assert "invalidation_level" in res.metadata


@pytest.mark.parametrize("name", list(REGISTRY.keys()))
def test_strategy_signal_is_deterministic(name, df, cfg):
    cfg.monte_carlo.n_paths = 30
    a = build_strategy(name, cfg=cfg).evaluate(df, run_mc=False, seed=7)
    b = build_strategy(name, cfg=cfg).evaluate(df, run_mc=False, seed=7)
    assert a.signal == b.signal
    assert a.confidence == b.confidence


def test_generate_signals_discrete(df, cfg):
    feats = compute_features(df)
    pos = build_strategy("trend_following", cfg=cfg).generate_signals(feats, df)
    assert set(pos.unique()).issubset({-1.0, 0.0, 1.0})


def test_stat_arb_labeled_placeholder(df, cfg):
    res = build_strategy("statistical_arbitrage", cfg=cfg).evaluate(df, run_mc=False)
    assert "NOT_VALIDATED_PAIRS" in res.metadata["reason_codes"]
