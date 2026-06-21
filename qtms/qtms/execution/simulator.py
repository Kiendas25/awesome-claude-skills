"""Execution simulator: turns an intended order into a realistic fill.

Applies slippage and fees and reports an effective fill price. Latency is
modeled as a placeholder delay attached to the fill metadata.
"""
from __future__ import annotations

import numpy as np

from ..app.config import QTMSConfig, get_config
from ..app.schemas import Signal
from .fees import fee_amount
from .slippage import apply_slippage, slippage_bps


def simulate_fill(
    symbol: str,
    direction: Signal,
    qty: float,
    ref_price: float,
    volatility_pct: float = 0.0,
    spread_widen: float = 1.0,
    seed: int | None = None,
    cfg: QTMSConfig | None = None,
) -> dict:
    cfg = cfg or get_config()
    rng = np.random.default_rng(seed) if seed is not None else None
    sl_bps = slippage_bps(direction, volatility_pct, spread_widen, rng, cfg)
    fill_price = apply_slippage(ref_price, direction, sl_bps)
    notional = abs(qty) * fill_price
    fee = fee_amount(notional, maker=False, cfg=cfg)
    slip_cost = abs(fill_price - ref_price) * abs(qty)
    return {
        "symbol": symbol,
        "direction": direction.value,
        "qty": qty,
        "ref_price": ref_price,
        "fill_price": fill_price,
        "slippage_bps": sl_bps,
        "slippage_cost": slip_cost,
        "fee": fee,
        "notional": notional,
        "latency_ms": cfg.costs.latency_ms,
    }
