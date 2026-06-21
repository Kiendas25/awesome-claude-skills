"""Exposure limits: max open positions and per-symbol exposure caps."""
from __future__ import annotations

from ..app.config import QTMSConfig, get_config


def check_exposure(
    equity: float,
    open_positions: dict[str, float],  # symbol -> notional
    symbol: str,
    new_notional: float,
    cfg: QTMSConfig | None = None,
) -> dict:
    cfg = cfg or get_config()
    reasons: list[str] = []

    # Count distinct open symbols (a new symbol would add one).
    n_open = len([s for s, v in open_positions.items() if abs(v) > 1e-9])
    if symbol not in open_positions and n_open >= cfg.risk.max_open_positions:
        reasons.append(
            f"max_open_positions ({cfg.risk.max_open_positions}) reached"
        )

    # Per-symbol exposure cap.
    existing = abs(open_positions.get(symbol, 0.0))
    projected = existing + abs(new_notional)
    cap = equity * cfg.risk.per_symbol_exposure_pct
    if projected > cap:
        reasons.append(
            f"per_symbol_exposure cap exceeded: {projected:.0f} > {cap:.0f}"
        )

    return {"allowed": len(reasons) == 0, "reasons": reasons, "n_open": n_open}
