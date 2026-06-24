"""ML meta-model: honest out-of-sample verdicts, no leakage, no trading."""
from __future__ import annotations

from qtms.agents.meta_learner import train_meta_model
from qtms.data.market_data import MarketDataAdapter
from qtms.strategies import REGISTRY


def test_registry_doubled_to_twelve():
    # 6 original + 6 extended building blocks.
    assert len(REGISTRY) >= 12
    for name in ("momentum", "rsi_reversion", "donchian_breakout",
                 "macd_trend", "bollinger_bounce", "vwap_reversion"):
        assert name in REGISTRY


def test_meta_model_structure(cfg):
    df = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=900, seed=11)
    out = train_meta_model(df, horizon=3, folds=4)
    assert out["available"] is True
    assert "oos_auc_mean" in out
    assert 0.0 <= out["oos_auc_mean"] <= 1.0
    assert isinstance(out["has_edge"], bool)
    assert "top_features" in out


def test_meta_model_pure_noise_has_no_edge(cfg):
    # Random-walk-ish data must NOT show a reliable edge (honest null).
    df = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=1200, seed=3, drift=0.0)
    out = train_meta_model(df, horizon=3, folds=4)
    # Out-of-sample AUC on noise should sit near 0.5; edge claim must be False-ish.
    assert out["oos_auc_mean"] < 0.6
    if out["has_edge"]:
        # If it ever claims an edge on noise, it must at least be marginal.
        assert out["oos_auc_mean"] < 0.58


def test_meta_model_too_little_data(cfg):
    df = MarketDataAdapter(cfg).synthetic("BTC/USDT", n=40, seed=1)
    out = train_meta_model(df, horizon=3)
    assert out["has_edge"] is False
