"""Core backtest + Monte Carlo engine shared by strategies and the stack.

The backtest is strictly causal: a position decided at bar t is applied to the
return realized from t to t+1, so there is no lookahead. Costs (fees +
slippage) are charged on every position change.

The Monte Carlo wraps a backtest with bootstrap resampling and cost
randomization to answer the only question that matters: *is the edge real, or
did it depend on one lucky sample?*
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..app.config import QTMSConfig, get_config
from ..reports import metrics as M
from .bootstrap import block_bootstrap
from .risk_of_ruin import risk_of_ruin


@dataclass
class BacktestResult:
    bar_returns: np.ndarray
    equity: np.ndarray
    trade_returns: np.ndarray
    metrics: dict = field(default_factory=dict)


def _extract_trades(positions: np.ndarray, bar_returns: np.ndarray) -> np.ndarray:
    """Group consecutive equal nonzero positions into trades, summing returns."""
    trades: list[float] = []
    i, n = 0, len(positions)
    while i < n:
        pos = positions[i]
        if pos == 0:
            i += 1
            continue
        j = i
        acc = 0.0
        while j < n and positions[j] == pos:
            acc += positions[j] * bar_returns[j]
            j += 1
        trades.append(acc)
        i = j
    return np.asarray(trades, dtype=float)


def run_backtest(
    positions: pd.Series,
    df: pd.DataFrame,
    fee: float | None = None,
    slippage_bps: float | None = None,
    cfg: QTMSConfig | None = None,
) -> BacktestResult:
    cfg = cfg or get_config()
    fee = cfg.costs.taker_fee if fee is None else fee
    slippage_bps = cfg.costs.base_slippage_bps if slippage_bps is None else slippage_bps

    close = df["close"].astype(float)
    bar_ret = close.pct_change().fillna(0.0).to_numpy()
    # Causal: act on next bar.
    pos = positions.reindex(df.index).fillna(0.0).shift(1).fillna(0.0).to_numpy()

    cost_rate = fee + slippage_bps / 10_000.0
    turnover = np.abs(np.diff(pos, prepend=0.0))
    costs = turnover * cost_rate
    strat_ret = pos * bar_ret - costs

    equity = np.cumprod(1.0 + strat_ret)
    trade_returns = _extract_trades(pos, bar_ret)
    # Charge round-trip costs to each trade for honest per-trade pnl.
    if trade_returns.size:
        trade_returns = trade_returns - 2 * cost_rate

    metrics = {
        "total_return": float(equity[-1] - 1.0) if equity.size else 0.0,
        "sharpe": M.sharpe(strat_ret),
        "max_drawdown": M.max_drawdown(equity),
        "turnover": float(turnover.sum()),
        **M.trade_summary(trade_returns),
        "cost_rate": cost_rate,
    }
    return BacktestResult(strat_ret, equity, trade_returns, metrics)


def monte_carlo_strategy(
    positions: pd.Series,
    df: pd.DataFrame,
    cfg: QTMSConfig | None = None,
    seed: int = 42,
    n_paths: int | None = None,
) -> dict:
    """Bootstrap + cost-randomized robustness summary for one position series."""
    cfg = cfg or get_config()
    n_paths = n_paths or cfg.monte_carlo.n_paths
    rng = np.random.default_rng(seed)

    base = run_backtest(positions, df, cfg=cfg)
    if base.bar_returns.size < 5:
        return {
            "n_paths": 0,
            "seed": seed,
            "prob_positive_expectancy": 0.0,
            "robustness_score": 0.0,
            "warning": "insufficient data",
        }

    # Block-bootstrap the per-bar strategy returns to test path-dependence.
    boot = block_bootstrap(
        base.bar_returns, n_paths, cfg.monte_carlo.bootstrap_blocks, rng
    )
    boot_equity = np.cumprod(1.0 + boot, axis=1)
    final_returns = boot_equity[:, -1] - 1.0
    max_dds = np.array([M.max_drawdown(eq) for eq in boot_equity])
    prob_pos = float((final_returns > 0).mean())

    # Cost-stress: re-run with randomized higher slippage/fees.
    cost_survived = 0
    for _ in range(min(50, n_paths)):
        extra_slip = cfg.costs.base_slippage_bps * (1 + 2 * rng.random())
        r = run_backtest(positions, df, slippage_bps=extra_slip, cfg=cfg)
        if r.metrics["total_return"] > 0:
            cost_survived += 1
    cost_survival = cost_survived / min(50, n_paths)

    # Signal persistence: how often the position holds bar-to-bar.
    pos_arr = positions.reindex(df.index).fillna(0.0).to_numpy()
    if pos_arr.size > 1:
        persistence = float((pos_arr[1:] == pos_arr[:-1]).mean())
    else:
        persistence = 0.0

    ror = risk_of_ruin(
        base.trade_returns, n_paths=min(1000, n_paths * 2), seed=seed
    )

    # Robustness blends the independent signals; deliberately conservative.
    robustness = float(
        np.clip(
            0.35 * prob_pos
            + 0.25 * cost_survival
            + 0.20 * (1 - ror["risk_of_ruin"])
            + 0.20 * min(1.0, persistence + 0.3),
            0.0,
            1.0,
        )
    )

    return {
        "n_paths": n_paths,
        "seed": seed,
        "base_total_return": base.metrics["total_return"],
        "base_sharpe": base.metrics["sharpe"],
        "base_max_drawdown": base.metrics["max_drawdown"],
        "prob_positive_expectancy": prob_pos,
        "mean_bootstrap_return": float(final_returns.mean()),
        "return_p05": float(np.percentile(final_returns, 5)),
        "return_p95": float(np.percentile(final_returns, 95)),
        "max_drawdown_p95": float(np.percentile(max_dds, 95)),
        "cost_survival": cost_survival,
        "signal_persistence": persistence,
        "risk_of_ruin": ror["risk_of_ruin"],
        "robustness_score": robustness,
        "n_trades": int(base.trade_returns.size),
    }
