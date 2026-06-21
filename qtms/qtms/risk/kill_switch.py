"""Kill switch accessors.

The actual singleton lives in ``app.safety`` so that every order-routing path
imports the SAME instance. This module just re-exports convenience functions so
the risk package is self-describing.
"""
from __future__ import annotations

from ..app.safety import KILL_SWITCH


def trip(reason: str) -> None:
    KILL_SWITCH.trip(reason)


def reset() -> None:
    KILL_SWITCH.reset()


def is_active() -> bool:
    return KILL_SWITCH.active


def status() -> dict:
    return {
        "active": KILL_SWITCH.active,
        "reason": KILL_SWITCH.reason,
        "triggered_at": str(KILL_SWITCH.triggered_at) if KILL_SWITCH.triggered_at else None,
    }
