"""Performance and risk metrics. Pure functions, no side effects.

These are honest, cost-aware metrics. Win rate alone is never used as a quality
bar (a high win rate with fat-tailed losers is a trap), so expectancy, profit
factor and drawdown are reported alongside it.
"""
from __future__ import annotations

import numpy as np


def max_drawdown(equity: np.ndarray) -> float:
    """Max peak-to-trough drawdown as a positive fraction in [0, 1]."""
    equity = np.asarray(equity, dtype=float)
    if equity.size == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak == 0, 1.0, peak)
    return float(-dd.min())


def sharpe(returns: np.ndarray, periods_per_year: int = 105_120) -> float:
    """Annualized Sharpe of per-bar returns (default = 5m bars per year)."""
    returns = np.asarray(returns, dtype=float)
    if returns.size < 2:
        return 0.0
    sd = returns.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(returns.mean() / sd * np.sqrt(periods_per_year))


def win_rate(pnls: np.ndarray) -> float:
    pnls = np.asarray(pnls, dtype=float)
    if pnls.size == 0:
        return 0.0
    return float((pnls > 0).mean())


def profit_factor(pnls: np.ndarray) -> float:
    pnls = np.asarray(pnls, dtype=float)
    gains = pnls[pnls > 0].sum()
    losses = -pnls[pnls < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def expectancy(pnls: np.ndarray) -> float:
    pnls = np.asarray(pnls, dtype=float)
    return float(pnls.mean()) if pnls.size else 0.0


def avg_win_loss(pnls: np.ndarray) -> tuple[float, float]:
    pnls = np.asarray(pnls, dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    return (
        float(wins.mean()) if wins.size else 0.0,
        float(losses.mean()) if losses.size else 0.0,
    )


def tail_loss(pnls: np.ndarray, q: float = 0.05) -> float:
    """Expected shortfall (CVaR) of the worst ``q`` fraction of trades."""
    pnls = np.asarray(pnls, dtype=float)
    if pnls.size == 0:
        return 0.0
    cutoff = np.quantile(pnls, q)
    tail = pnls[pnls <= cutoff]
    return float(tail.mean()) if tail.size else float(cutoff)


def deflated_sharpe_placeholder(sr: float, n_trials: int, n_obs: int) -> float:
    """Crude deflated-Sharpe haircut: penalize for multiple testing and small
    samples. Placeholder — not the full Bailey/Lopez de Prado statistic."""
    if n_obs < 2:
        return 0.0
    trial_pen = 1.0 / (1.0 + np.log1p(max(0, n_trials - 1)))
    obs_pen = 1.0 - 1.0 / np.sqrt(n_obs)
    return float(sr * trial_pen * max(0.0, obs_pen))


def trade_summary(pnls: np.ndarray) -> dict:
    aw, al = avg_win_loss(pnls)
    return {
        "n_trades": int(np.asarray(pnls).size),
        "win_rate": win_rate(pnls),
        "profit_factor": profit_factor(pnls),
        "expectancy": expectancy(pnls),
        "avg_win": aw,
        "avg_loss": al,
        "tail_loss_cvar05": tail_loss(pnls),
    }
