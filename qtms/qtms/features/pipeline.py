"""Feature pipeline: assemble all feature blocks and score feature stability.

The Monte Carlo here perturbs prices/volumes and resamples windows, then checks
whether the *latest* feature vector stays stable. Unstable features should not
drive trades, so the robustness score feeds the conviction gate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..app.schemas import LayerResult, utcnow
from .liquidity import liquidity_features
from .mean_reversion import mean_reversion_features
from .microstructure import microstructure_features
from .regime import classify_regime, current_regime
from .trend import trend_features
from .volatility import volatility_features

# Features used for stability scoring (the ones strategies actually consume).
_STABILITY_COLS = ["ma_spread", "slope", "momentum", "zscore", "atr_pct", "vol_regime"]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    blocks = [
        trend_features(df),
        mean_reversion_features(df),
        volatility_features(df),
        liquidity_features(df),
        microstructure_features(df),
    ]
    feats = pd.concat(blocks, axis=1)
    feats["regime"] = classify_regime(feats)
    feats.attrs["symbol"] = df.attrs.get("symbol", "UNKNOWN")
    return feats


def _latest_vector(df: pd.DataFrame) -> np.ndarray:
    feats = compute_features(df)
    return feats[_STABILITY_COLS].iloc[-1].to_numpy(dtype=float)


def monte_carlo_feature_stability(
    df: pd.DataFrame, n_paths: int = 150, seed: int = 42
) -> LayerResult:
    rng = np.random.default_rng(seed)
    base_vec = _latest_vector(df)
    n = len(df)
    samples = np.empty((n_paths, len(base_vec)))

    for i in range(n_paths):
        d = df.copy()
        # Perturb prices and volumes.
        noise = np.exp(rng.normal(0.0, 0.001, size=n))
        for col in ("open", "high", "low", "close"):
            d[col] = d[col] * noise
        d["volume"] = d["volume"] * np.exp(rng.normal(0.0, 0.05, size=n))
        samples[i] = _latest_vector(d)

    means = np.nanmean(samples, axis=0)
    stds = np.nanstd(samples, axis=0)
    scale = np.maximum(np.abs(base_vec), 1e-3)
    rel_disp = np.nanmean(stds / scale)
    robustness = float(max(0.0, min(1.0, 1.0 - rel_disp)))

    regime = current_regime(compute_features(df))
    return LayerResult(
        layer_name="features",
        timestamp=utcnow(),
        symbol=str(df.attrs.get("symbol", "UNKNOWN")),
        signal=0.0,
        confidence=robustness,
        uncertainty=float(min(1.0, rel_disp)),
        expected_return=0.0,
        expected_risk=float(np.nanmean(stds)),
        monte_carlo_summary={
            "n_paths": n_paths,
            "seed": seed,
            "feature_robustness_score": robustness,
            "relative_dispersion": float(rel_disp),
            "stability_cols": _STABILITY_COLS,
            "feature_means": {c: float(m) for c, m in zip(_STABILITY_COLS, means)},
        },
        warnings=["features unstable"] if robustness < 0.5 else [],
        metadata={"regime": regime},
    )
