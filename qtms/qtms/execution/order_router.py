"""Order router: the ONLY path orders may take.

Every order — paper or live — passes through here. The router enforces the kill
switch and (for live) the full live gate before anything reaches a broker.
Strategies cannot call brokers directly; they only emit signals.
"""
from __future__ import annotations

from ..app.safety import KILL_SWITCH, LiveGateInputs, assert_can_trade
from ..app.schemas import Signal
from .live_broker_stub import LiveBrokerStub
from .paper_broker import PaperBroker


class OrderRouter:
    def __init__(self, paper: PaperBroker, live: LiveBrokerStub | None = None):
        self.paper = paper
        self.live = live or LiveBrokerStub()

    def route_open(
        self,
        symbol: str,
        direction: Signal,
        qty: float,
        ref_price: float,
        live: bool = False,
        gate_inputs: LiveGateInputs | None = None,
        **kwargs,
    ) -> dict:
        # Kill switch first — overrides everything (raises if active).
        assert_can_trade(live=live, inputs=gate_inputs)
        if live:
            # Will raise NotImplementedError in the MVP stub even if gate passes.
            self.live.place_order(symbol, direction, qty, gate_inputs or LiveGateInputs())
            return {"routed": "live", "status": "blocked_stub"}
        pos = self.paper.open(symbol, direction, qty, ref_price, **kwargs)
        return {"routed": "paper", "trade_id": pos.trade_id, "entry_price": pos.entry_price}

    def route_close(
        self,
        symbol: str,
        ref_price: float,
        exit_reason: list[str] | None = None,
        seed: int | None = None,
    ) -> dict:
        if KILL_SWITCH.active:
            # Closing positions is always allowed (risk-reducing), even with the
            # kill switch active — we never trap an operator in a position.
            pass
        record = self.paper.close(symbol, ref_price, exit_reason=exit_reason, seed=seed)
        return {"routed": "paper", "closed": record is not None}
