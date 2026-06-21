"""Slippage model: base slippage + spread + latency + volatility component.

Deterministic given a seed. Slippage always moves price AGAINST the trader (a
buy fills higher, a sell fills lower) — never in their favor by default.
"""
from __future__ import annotations

import numpy as np

from ..app.config import QTMSConfig, get_config
from ..app.schemas import Signal


def slippage_bps(
    direction: Signal,
    volatility_pct: float = 0.0,
    spread_widen: float = 1.0,
    rng: np.random.Generator | None = None,
    cfg: QTMSConfig | None = None,
) -> float:
    cfg = cfg or get_config()
    base = cfg.costs.base_slippage_bps
    spread = cfg.costs.spread_bps * spread_widen
    vol_component = max(0.0, volatility_pct) * 10_000 * 0.05  # 5% of vol in bps
    noise = 0.0
    if rng is not None:
        noise = abs(rng.normal(0.0, base * 0.3))
    total = base + spread + vol_component + noise
    return float(total)


def apply_slippage(price: float, direction: Signal, bps: float) -> float:
    frac = bps / 10_000.0
    if direction == Signal.LONG:
        return price * (1.0 + frac)   # buy fills worse (higher)
    if direction == Signal.SHORT:
        return price * (1.0 - frac)   # sell fills worse (lower)
    return price
