"""Validation & anti-overfitting reports.

Produces an honest, cost-aware verdict on whether a strategy has a *demonstrated*
edge. The default verdict is FAIL. A strategy passes only if it clears every
hard gate: adequate sample, no single-trade dependence, costs don't destroy the
edge, drawdown acceptable, low parameter sensitivity, stable across regimes, and
sufficient Monte Carlo robustness.

Several statistics (deflated Sharpe, probability of backtest overfitting) are
clearly-labelled placeholders, not the full literature estimators.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .app.config import QTMSConfig, get_config
from .features.pipeline import classify_regime, compute_features
from .monte_carlo.bootstrap import bootstrap_ci
from .monte_carlo.engine import monte_carlo_strategy, run_backtest
from .monte_carlo.risk_of_ruin import risk_of_ruin
from .reports import metrics as M


@dataclass
class ValidationResult:
    strategy: str
    passed: bool
    score: float
    metrics: dict = field(default_factory=dict)
    walk_forward: list = field(default_factory=list)
    regime_performance: dict = field(default_factory=dict)
    parameter_sensitivity: dict = field(default_factory=dict)
    monte_carlo: dict = field(default_factory=dict)
    fail_reasons: list = field(default_factory=list)


MIN_TRADES = 30
MAX_SINGLE_TRADE_SHARE = 0.5  # one trade may not exceed 50% of gross profit
MAX_PARAM_SENSITIVITY = 0.6
MIN_ROBUSTNESS = 0.5


def _walk_forward(strategy, df: pd.DataFrame, cfg: QTMSConfig, folds: int = 4) -> list:
    n = len(df)
    fold_size = n // (folds + 1)
    results = []
    feats_all = compute_features(df)
    for i in range(folds):
        test_start = fold_size * (i + 1)
        test_end = min(n, test_start + fold_size)
        seg = df.iloc[test_start:test_end]
        if len(seg) < 20:
            continue
        seg_feats = feats_all.iloc[test_start:test_end]
        pos = strategy.generate_signals(seg_feats, seg)
        bt = run_backtest(pos, seg, cfg=cfg)
        results.append(
            {
                "fold": i,
                "total_return": bt.metrics["total_return"],
                "sharpe": bt.metrics["sharpe"],
                "max_drawdown": bt.metrics["max_drawdown"],
                "n_trades": bt.metrics["n_trades"],
            }
        )
    return results


def _regime_performance(strategy, df: pd.DataFrame, cfg: QTMSConfig) -> dict:
    feats = compute_features(df)
    regimes = classify_regime(feats)
    pos = strategy.generate_signals(feats, df)
    bt = run_backtest(pos, df, cfg=cfg)
    bar_ret = pd.Series(bt.bar_returns, index=df.index)
    out = {}
    for reg in regimes.unique():
        mask = (regimes == reg).to_numpy()
        r = bar_ret[mask]
        out[reg] = {
            "bars": int(mask.sum()),
            "mean_return": float(r.mean()) if len(r) else 0.0,
            "sharpe": M.sharpe(r.to_numpy()),
        }
    return out


def _parameter_sensitivity(strategy, df: pd.DataFrame, cfg: QTMSConfig) -> dict:
    """Vary the entry threshold +/-30% and measure return dispersion. High
    dispersion => fragile/overfit parameters."""
    feats = compute_features(df)
    base_thr = strategy.entry_threshold
    returns = []
    grid = [base_thr * m for m in (0.7, 0.85, 1.0, 1.15, 1.3)]
    for thr in grid:
        strategy.entry_threshold = thr
        pos = strategy.generate_signals(feats, df)
        bt = run_backtest(pos, df, cfg=cfg)
        returns.append(bt.metrics["total_return"])
    strategy.entry_threshold = base_thr
    returns = np.array(returns)
    spread = float(returns.max() - returns.min())
    scale = abs(returns.mean()) + 1e-3
    sensitivity = float(min(1.0, spread / (scale * 4)))
    return {
        "grid": grid,
        "returns": returns.tolist(),
        "sensitivity": sensitivity,
        "heatmap": {str(round(t, 3)): float(r) for t, r in zip(grid, returns)},
    }


def validate_strategy(strategy, df: pd.DataFrame, cfg: QTMSConfig | None = None) -> ValidationResult:
    cfg = cfg or get_config()
    feats = compute_features(df)

    # Train/test split (70/30).
    cut = int(len(df) * 0.7)
    train, test = df.iloc[:cut], df.iloc[cut:]
    train_feats, test_feats = feats.iloc[:cut], feats.iloc[cut:]

    pos_full = strategy.generate_signals(feats, df)
    bt = run_backtest(pos_full, df, cfg=cfg)
    trade_returns = bt.trade_returns

    pos_test = strategy.generate_signals(test_feats, test)
    bt_test = run_backtest(pos_test, test, cfg=cfg)

    mc = monte_carlo_strategy(pos_full, df, cfg=cfg, seed=cfg.seed)
    ror = risk_of_ruin(trade_returns, seed=cfg.seed)
    wf = _walk_forward(strategy, df, cfg)
    regime_perf = _regime_performance(strategy, df, cfg)
    param_sens = _parameter_sensitivity(strategy, df, cfg)

    # Bootstrap CI on per-trade expectancy.
    if trade_returns.size:
        exp_point, exp_lo, exp_hi = bootstrap_ci(trade_returns, np.mean, seed=cfg.seed)
    else:
        exp_point, exp_lo, exp_hi = 0.0, 0.0, 0.0

    gross_profit = trade_returns[trade_returns > 0].sum() if trade_returns.size else 0.0
    single_trade_share = (
        float(trade_returns.max() / gross_profit) if gross_profit > 0 else 1.0
    )

    sr = bt.metrics["sharpe"]
    deflated = M.deflated_sharpe_placeholder(sr, n_trials=6, n_obs=int(trade_returns.size))
    # Crude PBO placeholder: fraction of walk-forward folds with negative return.
    pbo = (
        float(np.mean([1.0 if f["total_return"] <= 0 else 0.0 for f in wf]))
        if wf
        else 1.0
    )

    metrics = {
        "n_trades": int(trade_returns.size),
        "total_return": bt.metrics["total_return"],
        "cost_adjusted_return": bt.metrics["total_return"],  # backtest already nets costs
        "test_return": bt_test.metrics["total_return"],
        "sharpe": sr,
        "deflated_sharpe_placeholder": deflated,
        "max_drawdown": bt.metrics["max_drawdown"],
        "turnover": bt.metrics["turnover"],
        "win_rate": bt.metrics["win_rate"],
        "profit_factor": bt.metrics["profit_factor"],
        "expectancy": bt.metrics["expectancy"],
        "expectancy_ci95": [exp_lo, exp_hi],
        "avg_win": bt.metrics["avg_win"],
        "avg_loss": bt.metrics["avg_loss"],
        "tail_loss_cvar05": bt.metrics["tail_loss_cvar05"],
        "risk_of_ruin": ror["risk_of_ruin"],
        "single_trade_share": single_trade_share,
        "prob_backtest_overfitting_placeholder": pbo,
    }

    # --- hard pass/fail gates ---------------------------------------------
    reasons: list[str] = []
    if trade_returns.size < MIN_TRADES:
        reasons.append(f"sample too small: {trade_returns.size} < {MIN_TRADES} trades")
    if single_trade_share > MAX_SINGLE_TRADE_SHARE:
        reasons.append("edge depends on one lucky trade")
    if bt.metrics["total_return"] <= 0:
        reasons.append("costs destroy edge / non-positive cost-adjusted return")
    if bt.metrics["max_drawdown"] > cfg.risk.max_drawdown_pct:
        reasons.append("max drawdown exceeds limit")
    if param_sens["sensitivity"] > MAX_PARAM_SENSITIVITY:
        reasons.append("high parameter sensitivity (fragile)")
    if mc.get("robustness_score", 0.0) < MIN_ROBUSTNESS:
        reasons.append("Monte Carlo robustness too low")
    if ror["risk_of_ruin"] > cfg.risk.max_risk_of_ruin:
        reasons.append("risk of ruin too high")
    # Regime instability: any regime with >=20 bars and negative sharpe.
    unstable = [
        r for r, v in regime_perf.items() if v["bars"] >= 20 and v["sharpe"] < -0.5
    ]
    if unstable:
        reasons.append(f"unstable across regimes: {unstable}")

    passed = len(reasons) == 0
    score = float(
        np.clip(
            0.3 * mc.get("robustness_score", 0.0)
            + 0.2 * mc.get("prob_positive_expectancy", 0.0)
            + 0.2 * (1 - ror["risk_of_ruin"])
            + 0.15 * (1 - param_sens["sensitivity"])
            + 0.15 * (1 - pbo),
            0.0,
            1.0,
        )
    )

    return ValidationResult(
        strategy=strategy.name,
        passed=passed,
        score=score,
        metrics=metrics,
        walk_forward=wf,
        regime_performance=regime_perf,
        parameter_sensitivity=param_sens,
        monte_carlo=mc,
        fail_reasons=reasons,
    )
