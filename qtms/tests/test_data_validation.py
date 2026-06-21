"""Data validation + no-lookahead tests."""
from __future__ import annotations

import numpy as np

from qtms.data.validators import assert_no_lookahead, validate_ohlcv
from qtms.features.trend import trend_features
from qtms.features.pipeline import compute_features


def test_clean_data_passes(df):
    report = validate_ohlcv(df)
    assert report.ok
    assert report.quality_score >= 0.9


def test_negative_prices_caught(df):
    bad = df.copy()
    bad.iloc[5, bad.columns.get_loc("close")] = -1.0
    report = validate_ohlcv(bad)
    assert not report.ok
    assert any("non-positive" in i for i in report.issues)
    assert report.quality_score < 1.0


def test_duplicate_timestamps_caught(df):
    bad = df.copy()
    bad = bad.iloc[list(range(len(bad))) + [10]]  # duplicate one row
    report = validate_ohlcv(bad)
    assert any("duplicate" in i for i in report.issues)


def test_nan_caught(df):
    bad = df.copy()
    bad.iloc[3, bad.columns.get_loc("open")] = np.nan
    report = validate_ohlcv(bad)
    assert not report.ok


def test_no_lookahead_in_features(df):
    # Trend features at time t must not change when future data is added.
    assert assert_no_lookahead(lambda d: trend_features(d), df, "ema_fast")
    assert assert_no_lookahead(lambda d: trend_features(d), df, "momentum")


def test_features_are_causal_for_full_pipeline(df):
    feats_full = compute_features(df)
    cut = len(df) // 2
    feats_cut = compute_features(df.iloc[:cut])
    # The latest row of the truncated frame equals the same row in full frame.
    for col in ("ma_spread", "zscore", "atr_pct"):
        a = feats_full[col].iloc[cut - 1]
        b = feats_cut[col].iloc[cut - 1]
        assert np.isclose(a, b, atol=1e-9)
