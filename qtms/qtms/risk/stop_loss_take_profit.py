"""ATR-based stop-loss / take-profit and trailing-stop helpers."""
from __future__ import annotations

from ..app.schemas import Signal


def compute_levels(
    entry_price: float,
    direction: Signal,
    atr: float,
    sl_atr_mult: float = 1.5,
    tp_atr_mult: float = 2.5,
) -> dict:
    if direction == Signal.LONG:
        sl = entry_price - sl_atr_mult * atr
        tp = entry_price + tp_atr_mult * atr
    elif direction == Signal.SHORT:
        sl = entry_price + sl_atr_mult * atr
        tp = entry_price - tp_atr_mult * atr
    else:
        return {"stop_loss": None, "take_profit": None}
    return {
        "stop_loss": max(sl, 1e-9),
        "take_profit": max(tp, 1e-9),
        "sl_distance_pct": abs(entry_price - sl) / entry_price,
        "rr_ratio": tp_atr_mult / sl_atr_mult,
    }


def trailing_stop(
    direction: Signal,
    current_stop: float,
    price: float,
    atr: float,
    trail_atr_mult: float = 1.5,
) -> float:
    """Ratchet the stop in the favorable direction only (placeholder trailing)."""
    if direction == Signal.LONG:
        return max(current_stop, price - trail_atr_mult * atr)
    if direction == Signal.SHORT:
        return min(current_stop, price + trail_atr_mult * atr)
    return current_stop


def check_exit(direction: Signal, price: float, stop: float, take: float) -> str | None:
    """Return 'stop_loss' / 'take_profit' / None for the current price."""
    if direction == Signal.LONG:
        if price <= stop:
            return "stop_loss"
        if price >= take:
            return "take_profit"
    elif direction == Signal.SHORT:
        if price >= stop:
            return "stop_loss"
        if price <= take:
            return "take_profit"
    return None
