"""Live broker STUB. Disabled by default. Sends NO real orders.

This is intentionally a stub: it records intent only and refuses to act unless
the full live gate passes AND it is explicitly marked configured. The MVP does
not implement real exchange private-key trading.
"""
from __future__ import annotations

from ..app.safety import LiveGateInputs, assert_can_trade
from ..app.schemas import Signal


class LiveBrokerStub:
    """A non-functional placeholder for a real exchange adapter."""

    def __init__(self):
        self.configured = False  # must be explicitly turned on by an operator
        self.sent_orders: list[dict] = []

    def configure(self, confirm_phrase: str) -> bool:
        """Operator must pass the literal confirmation phrase. Even then, the
        stub still cannot place real orders — there is no exchange wiring."""
        if confirm_phrase == "I-UNDERSTAND-THIS-IS-A-STUB":
            self.configured = True
        return self.configured

    def place_order(
        self,
        symbol: str,
        direction: Signal,
        qty: float,
        gate_inputs: LiveGateInputs,
    ) -> dict:
        # Full live gate must pass (raises PermissionError otherwise).
        gate_inputs.broker_configured = self.configured
        assert_can_trade(live=True, inputs=gate_inputs)
        # Even past the gate, the MVP stub refuses to touch a real exchange.
        raise NotImplementedError(
            "Live exchange execution is NOT implemented in the MVP. "
            "This stub records intent only and never sends real orders."
        )
