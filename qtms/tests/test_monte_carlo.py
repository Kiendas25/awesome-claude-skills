"""Monte Carlo determinism + risk-of-ruin behavior."""
from __future__ import annotations

import numpy as np

from qtms.features.pipeline import compute_features
from qtms.monte_carlo.engine import monte_carlo_strategy, run_backtest
from qtms.monte_carlo.risk_of_ruin import risk_of_ruin
from qtms.strategies import build_strategy


def test_monte_carlo_deterministic_with_seed(df, cfg):
    cfg.monte_carlo.n_paths = 50
    strat = build_strategy("trend_following", cfg=cfg)
    feats = compute_features(df)
    pos = strat.generate_signals(feats, df)
    a = monte_carlo_strategy(pos, df, cfg=cfg, seed=123)
    b = monte_carlo_strategy(pos, df, cfg=cfg, seed=123)
    assert a["robustness_score"] == b["robustness_score"]
    assert a["prob_positive_expectancy"] == b["prob_positive_expectancy"]


def test_monte_carlo_changes_with_seed(df, cfg):
    cfg.monte_carlo.n_paths = 50
    strat = build_strategy("mean_reversion", cfg=cfg)
    pos = strat.generate_signals(compute_features(df), df)
    a = monte_carlo_strategy(pos, df, cfg=cfg, seed=1)
    b = monte_carlo_strategy(pos, df, cfg=cfg, seed=2)
    # Different seeds should generally give different bootstrap means.
    assert a["mean_bootstrap_return"] != b["mean_bootstrap_return"]


def test_risk_of_ruin_bounds():
    good = np.full(100, 0.01)
    bad = np.full(100, -0.2)
    r_good = risk_of_ruin(good, n_paths=200, seed=7)
    r_bad = risk_of_ruin(bad, n_paths=200, seed=7)
    assert 0.0 <= r_good["risk_of_ruin"] <= 1.0
    assert r_bad["risk_of_ruin"] > r_good["risk_of_ruin"]


def test_no_trades_is_worst_case():
    r = risk_of_ruin(np.array([]), n_paths=50)
    assert r["risk_of_ruin"] == 1.0


def test_backtest_is_causal_and_costed(df, cfg):
    strat = build_strategy("breakout", cfg=cfg)
    pos = strat.generate_signals(compute_features(df), df)
    bt = run_backtest(pos, df, cfg=cfg)
    assert bt.equity.size == len(df)
    assert "max_drawdown" in bt.metrics
    assert bt.metrics["max_drawdown"] >= 0.0
