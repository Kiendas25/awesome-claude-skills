"""Generic helper to run a layer's Monte Carlo and normalize its summary.

Every layer exposes its own ``monte_carlo_*`` function returning a LayerResult;
this module just collects them so callers (stacking, reports) get a uniform
view across the whole stack.
"""
from __future__ import annotations

import pandas as pd

from ..app.schemas import LayerResult
from ..data.market_data import monte_carlo_data_robustness
from ..features.pipeline import monte_carlo_feature_stability


def run_layer_monte_carlo(df: pd.DataFrame, seed: int = 42) -> dict[str, LayerResult]:
    """Run the data and feature layer Monte Carlo passes. Strategy and quantum
    MC are run by their own engines where the position series is available."""
    return {
        "market_data": monte_carlo_data_robustness(df, seed=seed),
        "features": monte_carlo_feature_stability(df, seed=seed),
    }
