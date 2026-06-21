"""Post-trade analyzer (off-path).

Analyzes closed paper trades: separates winners/losers, computes per-strategy
attribution, and flags strategy decay. Pure analytics — NO LLM, NO order
placement, NO config mutation.
"""
from __future__ import annotations

import numpy as np

from ..app.schemas import TradeRecord
from ..reports import metrics as M


def analyze_trades(trades: list[TradeRecord]) -> dict:
    if not trades:
        return {"n_trades": 0, "note": "no trades to analyze"}
    pnls = np.array([t.pnl for t in trades])
    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]

    # Per-strategy attribution by dominant weight at entry.
    attribution: dict[str, list[float]] = {}
    for t in trades:
        if t.strategy_weights:
            dom = max(t.strategy_weights, key=t.strategy_weights.get)
        else:
            dom = "unknown"
        attribution.setdefault(dom, []).append(t.pnl)

    strat_stats = {
        k: {
            "n": len(v),
            "total_pnl": float(np.sum(v)),
            "expectancy": float(np.mean(v)),
            "win_rate": M.win_rate(np.array(v)),
        }
        for k, v in attribution.items()
    }

    # Strategy decay: compare first vs second half expectancy per strategy.
    decay = {}
    for k, v in attribution.items():
        if len(v) >= 6:
            half = len(v) // 2
            first = float(np.mean(v[:half]))
            second = float(np.mean(v[half:]))
            decay[k] = {"first_half": first, "second_half": second, "decayed": second < first}

    return {
        "n_trades": len(trades),
        "summary": M.trade_summary(pnls),
        "n_winners": len(winners),
        "n_losers": len(losers),
        "avg_mae_losers": float(np.mean([t.max_adverse_excursion for t in losers])) if losers else 0.0,
        "avg_mfe_winners": float(np.mean([t.max_favorable_excursion for t in winners])) if winners else 0.0,
        "strategy_attribution": strat_stats,
        "strategy_decay": decay,
    }
