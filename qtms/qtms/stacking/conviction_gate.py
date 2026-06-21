"""Conviction gate: the final yes/no on whether a trade is allowed.

A trade is approved ONLY if every condition passes. The default posture is
rejection. Each failed condition is recorded with a human-readable reason so
the decision is fully auditable.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..app.config import QTMSConfig, get_config


@dataclass
class GateInputs:
    conviction: float
    prob_positive_expectancy: float
    risk_of_ruin: float
    max_drawdown_sim: float
    disagreement: float
    regime: str
    data_quality: float
    signal_stability: float
    cost_survival: float


def evaluate_gate(g: GateInputs, cfg: QTMSConfig | None = None) -> dict:
    cfg = cfg or get_config()
    c = cfg.conviction
    checks: dict[str, bool] = {
        "conviction": g.conviction >= c.min_conviction,
        "prob_positive_expectancy": g.prob_positive_expectancy
        >= c.min_prob_positive_expectancy,
        "risk_of_ruin": g.risk_of_ruin <= cfg.risk.max_risk_of_ruin,
        "max_drawdown_sim": g.max_drawdown_sim <= cfg.risk.max_drawdown_pct,
        "strategy_disagreement": g.disagreement <= c.max_strategy_disagreement,
        "regime_allowed": g.regime in c.allowed_regimes,
        "data_quality": g.data_quality >= c.min_data_quality,
        "signal_stability": g.signal_stability >= c.min_signal_stability,
        "cost_survival": g.cost_survival >= 0.5,
    }
    reasons = [f"failed: {k}" for k, ok in checks.items() if not ok]
    return {"approved": all(checks.values()), "checks": checks, "reject_reasons": reasons}
