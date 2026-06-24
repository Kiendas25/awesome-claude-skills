"""Strategy optimizer + promotion loop (off-path).

This is the "give the agent room to find a real edge — honestly" engine. It:

1. SEARCHES a small parameter grid per strategy on a TRAIN window using
   walk-forward scoring (so a setting must work on multiple sub-windows, not one
   lucky stretch). This is the *margin* to discover better settings.
2. KEEPS only strategies that pass full validation on TRAIN.
3. COMPOSES the survivors into one weighted ensemble (the "promoted strategy"),
   weighting by TRAIN robustness — no holdout data leaks into the weights.
4. RE-VALIDATES that composite on a HOLDOUT window it has NEVER seen. Only if it
   survives unseen data (positive cost-adjusted return, acceptable drawdown,
   enough trades) is it labelled ``promoted``.

Nothing here promises profit and nothing relaxes safety. Promotion is just an
honest, leakage-resistant verdict that an edge *might* be real and deserves
further paper trading.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..app.config import QTMSConfig, get_config
from ..features.pipeline import compute_features
from ..monte_carlo.engine import monte_carlo_strategy, run_backtest
from ..strategies import REGISTRY, build_strategy
from ..validation import validate_strategy

# Small, deliberate search spaces. ``entry_threshold`` is a base attribute;
# other keys are strategy ``params``. Each combination is one candidate variant,
# giving the agent dozens of building-block variants to judge across strategies.
SEARCH_SPACE: dict[str, dict[str, list]] = {
    "trend_following": {"entry_threshold": [0.2, 0.3, 0.45]},
    "mean_reversion": {"entry_threshold": [0.2, 0.3, 0.4], "z_entry": [1.0, 1.5, 2.0]},
    "breakout": {"entry_threshold": [0.2, 0.3, 0.45], "lookback": [10, 20, 30]},
    "volatility_expansion": {"entry_threshold": [0.2, 0.3, 0.45]},
    "liquidity_sweep": {"entry_threshold": [0.2, 0.3], "lookback": [10, 20]},
    "statistical_arbitrage": {"entry_threshold": [0.3, 0.4]},
    # extended universe
    "momentum": {"entry_threshold": [0.2, 0.3, 0.45], "lookback": [7, 14, 21]},
    "rsi_reversion": {"entry_threshold": [0.2, 0.3], "period": [9, 14, 21]},
    "donchian_breakout": {"entry_threshold": [0.2, 0.3, 0.45], "lookback": [15, 25, 40]},
    "macd_trend": {"entry_threshold": [0.2, 0.3, 0.45]},
    "bollinger_bounce": {"entry_threshold": [0.2, 0.3]},
    "vwap_reversion": {"entry_threshold": [0.2, 0.3]},
}


@dataclass
class PromotionResult:
    promoted: bool
    survivors: list[dict] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    holdout_metrics: dict = field(default_factory=dict)
    train_metrics: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    candidates_evaluated: int = 0


def _make(name: str, combo: dict, cfg: QTMSConfig):
    params = {k: v for k, v in combo.items() if k != "entry_threshold"}
    strat = build_strategy(name, params=params, cfg=cfg)
    if "entry_threshold" in combo:
        strat.entry_threshold = combo["entry_threshold"]
    return strat


def _walk_forward_score(strat, feats: pd.DataFrame, df: pd.DataFrame,
                        cfg: QTMSConfig, folds: int = 3) -> float:
    """Mean fold return penalized by fold-to-fold instability. Higher = better.
    A candidate that only wins in one fold is penalized by the std term."""
    n = len(df)
    fs = n // (folds + 1)
    if fs < 20:
        return -np.inf
    rets, dds = [], []
    for i in range(folds):
        a = fs * (i + 1)
        b = min(n, a + fs)
        seg, sf = df.iloc[a:b], feats.iloc[a:b]
        if len(seg) < 20:
            continue
        bt = run_backtest(strat.generate_signals(sf, seg), seg, cfg=cfg)
        rets.append(bt.metrics["total_return"])
        dds.append(bt.metrics["max_drawdown"])
    if not rets:
        return -np.inf
    return float(np.mean(rets) - 0.5 * np.std(rets) - 0.25 * np.mean(dds))


def optimize_strategy(name: str, train_df: pd.DataFrame, cfg: QTMSConfig) -> dict:
    """Grid-search the best variant of one strategy on the TRAIN window."""
    feats = compute_features(train_df)
    space = SEARCH_SPACE.get(name, {"entry_threshold": [0.3]})
    keys = list(space.keys())
    best = None
    n_eval = 0
    for values in itertools.product(*[space[k] for k in keys]):
        combo = dict(zip(keys, values))
        strat = _make(name, combo, cfg)
        score = _walk_forward_score(strat, feats, train_df, cfg)
        n_eval += 1
        if best is None or score > best["score"]:
            best = {"combo": combo, "score": score}
    best["name"] = name
    best["candidates"] = n_eval
    return best


def _composite_positions(survivors: list[dict], df: pd.DataFrame,
                         weights: dict[str, float], cfg: QTMSConfig,
                         threshold: float = 0.15) -> pd.Series:
    feats = compute_features(df)
    combined = pd.Series(0.0, index=df.index)
    for s in survivors:
        strat = _make(s["name"], s["combo"], cfg)
        combined = combined + weights.get(s["name"], 0.0) * strat.score(feats, df).clip(-1, 1)
    pos = pd.Series(0.0, index=df.index)
    pos[combined > threshold] = 1.0
    pos[combined < -threshold] = -1.0
    return pos


def discover_and_promote(
    df: pd.DataFrame,
    cfg: QTMSConfig | None = None,
    train_frac: float = 0.7,
    min_holdout_trades: int = 8,
) -> PromotionResult:
    cfg = cfg or get_config()
    n = len(df)
    cut = int(n * train_frac)
    train = df.iloc[:cut].copy()
    holdout = df.iloc[cut:].copy()
    train.attrs["symbol"] = holdout.attrs["symbol"] = df.attrs.get("symbol", "UNKNOWN")

    if len(holdout) < 40:
        return PromotionResult(False, reasons=["not enough data for a holdout window"])

    # 1) search best variant per strategy on TRAIN; 2) validate survivors on TRAIN.
    survivors: list[dict] = []
    total_candidates = 0
    n_strategies = 0  # how many strategies were searched (for multiple-testing)
    train_robustness: dict[str, float] = {}
    for name in cfg.active_strategies:
        if name not in REGISTRY:
            continue
        n_strategies += 1
        best = optimize_strategy(name, train, cfg)
        total_candidates += best["candidates"]
        strat = _make(name, best["combo"], cfg)
        vres = validate_strategy(strat, train, cfg)
        if vres.passed:
            survivors.append({"name": name, "combo": best["combo"],
                              "train_score": best["score"], "train_validation_score": vres.score})
            train_robustness[name] = vres.monte_carlo.get("robustness_score", 0.0)

    if not survivors:
        return PromotionResult(
            False, candidates_evaluated=total_candidates,
            reasons=["no strategy survived validation on the training window — "
                     "treat all as noise (honest result)"],
        )

    # 3) weights from TRAIN robustness only (no holdout leakage).
    rb = np.array([max(1e-6, train_robustness[s["name"]]) for s in survivors])
    rb = rb / rb.sum()
    weights = {s["name"]: float(w) for s, w in zip(survivors, rb)}

    # composite on TRAIN (reference) and on the unseen HOLDOUT (the real test).
    train_pos = _composite_positions(survivors, train, weights, cfg)
    holdout_pos = _composite_positions(survivors, holdout, weights, cfg)
    train_bt = run_backtest(train_pos, train, cfg=cfg)
    holdout_bt = run_backtest(holdout_pos, holdout, cfg=cfg)
    holdout_mc = monte_carlo_strategy(holdout_pos, holdout, cfg=cfg, seed=cfg.seed)

    hm = holdout_bt.metrics
    reasons: list[str] = []
    if hm["total_return"] <= 0:
        reasons.append("composite not profitable on unseen holdout (after costs)")
    if hm["max_drawdown"] > cfg.risk.max_drawdown_pct:
        reasons.append("composite holdout drawdown exceeds limit")
    if hm["n_trades"] < min_holdout_trades:
        reasons.append(f"too few holdout trades ({hm['n_trades']} < {min_holdout_trades})")
    if holdout_mc.get("robustness_score", 0.0) < 0.5:
        reasons.append("composite holdout Monte Carlo robustness too low")

    # Multiple-testing protection via THREE independent out-of-sample checks —
    # the more strategies searched, the easier a lucky winner is on noise, so a
    # single positive holdout is not enough:
    #  (a) bootstrap prob_positive_expectancy on the holdout (noise≈0.1, edge≈0.9),
    #  (b) a minimum holdout return that DEFLATES with search size (more
    #      strategies searched -> a bigger demonstrated edge is required),
    #  (c) consistency across BOTH halves of the holdout (luck rarely repeats).
    holdout_ppe = float(holdout_mc.get("prob_positive_expectancy", 0.0))
    if holdout_ppe < 0.60:
        reasons.append(
            f"holdout bootstrap confidence too low (prob_positive_expectancy="
            f"{holdout_ppe:.2f} < 0.60)"
        )

    min_return = 0.03 * (n_strategies / 6.0)
    if hm["total_return"] < min_return:
        reasons.append(
            f"holdout edge too small for the search size (return="
            f"{hm['total_return']:.3f} < {min_return:.3f} for {n_strategies} strategies)"
        )

    half = len(holdout) // 2
    h1 = holdout.iloc[:half].copy()
    h2 = holdout.iloc[half:].copy()
    h1.attrs["symbol"] = h2.attrs["symbol"] = holdout.attrs.get("symbol", "X")
    r1 = run_backtest(_composite_positions(survivors, h1, weights, cfg), h1, cfg=cfg).metrics["total_return"]
    r2 = run_backtest(_composite_positions(survivors, h2, weights, cfg), h2, cfg=cfg).metrics["total_return"]
    if not (r1 > 0 and r2 > 0):
        reasons.append(
            f"inconsistent across holdout sub-windows (first half={r1:.3f}, second half={r2:.3f})"
        )

    promoted = len(reasons) == 0
    return PromotionResult(
        promoted=promoted,
        survivors=survivors,
        weights=weights,
        holdout_metrics={
            **hm,
            "mc_robustness": holdout_mc.get("robustness_score", 0.0),
            "prob_positive_expectancy": holdout_ppe,
            "min_return_required": min_return,
            "subwindow_returns": [r1, r2],
            "strategies_searched": n_strategies,
        },
        train_metrics=train_bt.metrics,
        reasons=reasons or ["passed all unseen-holdout gates (multiple-testing aware)"],
        candidates_evaluated=total_candidates,
    )
