"""Risk reviewer (off-path): proposes risk reductions. Proposals only."""
from __future__ import annotations

from ..app.config import QTMSConfig, get_config


def review_risk(trade_analysis: dict, validation: dict | None, cfg: QTMSConfig | None = None) -> list[dict]:
    cfg = cfg or get_config()
    proposals: list[dict] = []
    summary = trade_analysis.get("summary", {})

    ror = (validation or {}).get("aggregate_risk_of_ruin", 0.0)
    if ror > cfg.risk.max_risk_of_ruin:
        proposals.append(
            {
                "type": "reduce_risk_per_trade",
                "from": cfg.risk.risk_per_trade,
                "to": round(cfg.risk.risk_per_trade * 0.5, 5),
                "reason": f"observed risk of ruin {ror:.3f} exceeds limit",
            }
        )

    pf = summary.get("profit_factor", 0.0)
    if 0 < pf < 1.0:
        proposals.append(
            {
                "type": "reduce_max_position_pct",
                "from": cfg.risk.max_position_pct,
                "to": round(cfg.risk.max_position_pct * 0.5, 4),
                "reason": f"profit factor {pf:.2f} < 1.0 — shrink exposure while edge unproven",
            }
        )

    tail = summary.get("tail_loss_cvar05", 0.0)
    if tail < 0 and abs(tail) > 2 * abs(summary.get("avg_loss", 0.0) or 1e-9):
        proposals.append(
            {
                "type": "tighten_stop_loss",
                "reason": "tail losses are large relative to typical loss",
            }
        )

    return proposals
