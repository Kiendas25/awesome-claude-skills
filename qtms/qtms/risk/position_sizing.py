"""Position sizing: volatility-targeted, conviction-scaled, capped.

Size is the SMALLEST of: fixed-fractional risk budget (risk_per_trade / stop
distance) and the hard max-position cap. Conviction scales *down* from the cap,
never up beyond it. This makes oversizing structurally impossible.
"""
from __future__ import annotations

from ..app.config import QTMSConfig, get_config


def position_size(
    equity: float,
    price: float,
    stop_distance_pct: float,
    conviction: float,
    cfg: QTMSConfig | None = None,
) -> dict:
    cfg = cfg or get_config()
    conviction = max(0.0, min(1.0, conviction))
    stop_distance_pct = max(stop_distance_pct, 0.001)  # floor to avoid huge size

    # Risk-budget notional: lose at most risk_per_trade of equity if stop hit.
    risk_budget = equity * cfg.risk.risk_per_trade
    risk_notional = risk_budget / stop_distance_pct

    # Hard cap on notional.
    cap_notional = equity * cfg.risk.max_position_pct

    notional = min(risk_notional, cap_notional) * conviction
    notional = max(0.0, notional)
    qty = notional / price if price > 0 else 0.0
    return {
        "qty": qty,
        "notional": notional,
        "risk_notional": risk_notional,
        "cap_notional": cap_notional,
        "capped": risk_notional > cap_notional,
        "conviction_scale": conviction,
    }
