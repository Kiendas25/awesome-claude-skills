"""Learning supervisor: off-path, cannot enable live, validation gates work."""
from __future__ import annotations

import pytest

from qtms.agents.learning_supervisor import LearningSupervisor
from qtms.strategies import build_strategy
from qtms.validation import validate_strategy


def test_supervisor_cannot_enable_live(cfg):
    sup = LearningSupervisor(cfg)
    assert sup.CAN_ENABLE_LIVE is False
    with pytest.raises(PermissionError):
        sup.enable_live_trading()


def test_supervisor_produces_recommendations(cfg, df):
    cfg.monte_carlo.n_paths = 20
    sup = LearningSupervisor(cfg)
    reco = sup.analyze(df, trades=[], run_validation=True)
    assert reco["can_enable_live"] is False
    assert reco["requires_manual_approval"] is True
    assert "overfitting_risk_score" in reco
    assert 0.0 <= reco["overfitting_risk_score"] <= 1.0
    assert "validation" in reco
    assert "strategy_scorecards" in reco


def test_validation_fails_small_sample(cfg):
    from qtms.data.market_data import MarketDataAdapter
    # Very short series -> too few trades -> must fail.
    short = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=60, seed=3)
    cfg.monte_carlo.n_paths = 20
    res = validate_strategy(build_strategy("trend_following", cfg=cfg), short, cfg)
    assert not res.passed
    assert any("sample too small" in r for r in res.fail_reasons)


def test_validation_fails_high_drawdown(cfg, df):
    cfg.monte_carlo.n_paths = 20
    # Force an absurdly low drawdown tolerance so any real strategy fails it.
    cfg.risk.max_drawdown_pct = 0.0001
    res = validate_strategy(build_strategy("breakout", cfg=cfg), df, cfg)
    assert not res.passed
    assert any("drawdown" in r for r in res.fail_reasons)


def test_supervisor_is_off_path_no_orders(cfg, df):
    # The supervisor has no broker/router references at all.
    sup = LearningSupervisor(cfg)
    assert not hasattr(sup, "broker")
    assert not hasattr(sup, "router")
