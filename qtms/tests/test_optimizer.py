"""Strategy discovery + promotion: honest, leakage-resistant verdicts."""
from __future__ import annotations

from qtms.agents.learning_supervisor import LearningSupervisor
from qtms.agents.strategy_optimizer import discover_and_promote, optimize_strategy
from qtms.data.market_data import MarketDataAdapter


def test_optimize_returns_best_combo(cfg):
    cfg.monte_carlo.n_paths = 20
    df = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=600, seed=42, drift=0.001)
    best = optimize_strategy("trend_following", df, cfg)
    assert best["name"] == "trend_following"
    assert "entry_threshold" in best["combo"]
    assert best["candidates"] >= 1


def test_pure_noise_is_not_promoted(cfg):
    cfg.monte_carlo.n_paths = 20
    noise = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=1200, seed=7, drift=0.0)
    res = discover_and_promote(noise, cfg)
    # Honest result: random noise must not earn a 'promoted' verdict.
    assert res.promoted is False
    assert res.candidates_evaluated > 0


def test_real_trend_can_be_promoted_on_unseen_holdout(cfg):
    cfg.monte_carlo.n_paths = 30
    trend = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=1600, seed=42, drift=0.0012)
    res = discover_and_promote(trend, cfg)
    assert res.promoted is True
    assert len(res.survivors) >= 1
    # Promotion is judged on the UNSEEN holdout: positive, costed, enough trades.
    assert res.holdout_metrics["total_return"] > 0
    assert res.holdout_metrics["n_trades"] >= 8


def test_short_data_has_no_holdout(cfg):
    cfg.monte_carlo.n_paths = 20
    short = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=80, seed=1)
    res = discover_and_promote(short, cfg)
    assert res.promoted is False
    assert any("holdout" in r for r in res.reasons)


def test_promotion_cannot_enable_live(cfg):
    cfg.monte_carlo.n_paths = 20
    trend = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=1200, seed=42, drift=0.001)
    payload = LearningSupervisor(cfg).discover(trend)
    assert payload["can_enable_live"] is False
    assert payload["requires_manual_approval"] is True
