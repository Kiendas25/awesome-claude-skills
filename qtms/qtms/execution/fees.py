"""Fee model."""
from __future__ import annotations

from ..app.config import QTMSConfig, get_config


def fee_amount(notional: float, maker: bool = False, cfg: QTMSConfig | None = None) -> float:
    cfg = cfg or get_config()
    rate = cfg.costs.maker_fee if maker else cfg.costs.taker_fee
    return abs(notional) * rate
