"""Strategy researcher (off-path): proposes parameter ranges and which
strategies to disable, validated against historical simulations.

Crucially, every proposal is checked with a before/after Monte Carlo and an
overfitting-risk score. Proposals that only help one narrow window are rejected.
All output is a *proposal* — nothing is applied automatically.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..app.config import QTMSConfig, get_config
from ..monte_carlo.engine import monte_carlo_strategy
from ..features.pipeline import compute_features
from ..strategies import build_strategy


def _robustness(strategy, df: pd.DataFrame, cfg: QTMSConfig, seed: int) -> float:
    feats = compute_features(df)
    pos = strategy.generate_signals(feats, df)
    mc = monte_carlo_strategy(pos, df, cfg=cfg, seed=seed)
    return mc.get("robustness_score", 0.0)


def research(df: pd.DataFrame, validation_results: dict, cfg: QTMSConfig | None = None) -> dict:
    cfg = cfg or get_config()
    proposals: list[dict] = []
    disable: list[str] = []

    for name, vres in validation_results.items():
        if not isinstance(vres, dict):
            continue
        if not vres.get("passed", False):
            # Propose disabling failed strategies that are also non-robust.
            robust = vres.get("monte_carlo", {}).get("robustness_score", 0.0)
            if robust < 0.45:
                disable.append(name)

        # Propose a tighter entry-threshold range around the best-performing
        # point in the parameter-sensitivity heatmap.
        heat = vres.get("parameter_sensitivity", {}).get("heatmap", {})
        if heat:
            best_thr = max(heat, key=heat.get)
            proposals.append(
                {
                    "strategy": name,
                    "type": "entry_threshold_range",
                    "candidate": float(best_thr),
                    "range": [float(best_thr) * 0.9, float(best_thr) * 1.1],
                    "reason": "centered on best out-of-grid threshold",
                }
            )

    # Before/after Monte Carlo robustness for one candidate (anti-overfitting).
    overfitting_scores = {}
    for p in proposals:
        name = p["strategy"]
        base = build_strategy(name, cfg=cfg)
        cand = build_strategy(name, params=None, cfg=cfg)
        cand.entry_threshold = p["candidate"]
        # Split data into two windows; a real improvement should help BOTH.
        mid = len(df) // 2
        d1, d2 = df.iloc[:mid], df.iloc[mid:]
        d1.attrs["symbol"] = d2.attrs["symbol"] = df.attrs.get("symbol", "X")
        before = (_robustness(base, d1, cfg, cfg.seed) + _robustness(base, d2, cfg, cfg.seed + 1)) / 2
        after1 = _robustness(cand, d1, cfg, cfg.seed)
        after2 = _robustness(cand, d2, cfg, cfg.seed + 1)
        after = (after1 + after2) / 2
        # Overfitting risk: improves in one window but not the other.
        single_window = (after1 - before) * (after2 - before) < 0
        overfitting_scores[name] = {
            "before": before,
            "after": after,
            "improves_both_windows": not single_window,
            "accepted": (after > before) and (not single_window),
        }
        p["accepted"] = overfitting_scores[name]["accepted"]

    return {
        "parameter_proposals": proposals,
        "propose_disable": disable,
        "overfitting_check": overfitting_scores,
    }
