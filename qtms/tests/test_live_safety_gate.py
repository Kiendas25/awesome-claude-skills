"""Live trading must be impossible by default; the gate must be multi-factor."""
from __future__ import annotations

import os

import pytest

from qtms.app.config import get_config
from qtms.app.safety import (
    KILL_SWITCH,
    LiveGateInputs,
    approval_phrase,
    assert_can_trade,
    evaluate_live_gate,
)
from qtms.execution.live_broker_stub import LiveBrokerStub
from qtms.execution.order_router import OrderRouter
from qtms.execution.paper_broker import PaperBroker
from qtms.app.schemas import Signal


def test_live_disabled_by_default(cfg):
    assert cfg.live.live_trading_enabled is False
    decision = evaluate_live_gate(LiveGateInputs(), cfg)
    assert decision.allowed is False
    assert len(decision.reasons) > 0


def test_live_blocked_even_with_perfect_inputs_but_no_env(cfg):
    # Everything operationally good, but config flag + env not set.
    good = LiveGateInputs(
        validation_passed=True,
        paper_trade_count=10_000,
        observed_max_drawdown=0.01,
        observed_risk_of_ruin=0.0,
        broker_configured=True,
    )
    decision = evaluate_live_gate(good, cfg)
    assert not decision.allowed
    assert not decision.checks["config_live_enabled"]


def test_live_requires_exact_approval_phrase(cfg):
    cfg.live.live_trading_enabled = True
    os.environ["QTMS_ENABLE_LIVE"] = "true"
    os.environ["QTMS_MANUAL_LIVE_APPROVAL"] = "wrong-phrase"
    good = LiveGateInputs(
        validation_passed=True, paper_trade_count=10_000,
        observed_max_drawdown=0.01, observed_risk_of_ruin=0.0, broker_configured=True,
    )
    decision = evaluate_live_gate(good, cfg)
    assert not decision.allowed
    assert not decision.checks["manual_approval_phrase"]
    # With the correct phrase + all gates, it would pass — but broker still stub.
    os.environ["QTMS_MANUAL_LIVE_APPROVAL"] = approval_phrase(cfg)
    decision2 = evaluate_live_gate(good, cfg)
    assert decision2.allowed  # gate itself can pass...
    # ...but the actual live broker refuses to send real orders.
    with pytest.raises((PermissionError, NotImplementedError)):
        LiveBrokerStub().place_order("BTC/USDT", Signal.LONG, 1.0, good)


def test_kill_switch_overrides_everything(cfg):
    KILL_SWITCH.trip("test")
    with pytest.raises(PermissionError):
        assert_can_trade(live=False)
    with pytest.raises(PermissionError):
        assert_can_trade(live=True, inputs=LiveGateInputs())


def test_router_routes_to_paper_not_live(cfg):
    router = OrderRouter(PaperBroker(cfg))
    out = router.route_open("BTC/USDT", Signal.LONG, 0.1, 30_000.0, live=False)
    assert out["routed"] == "paper"


def test_router_live_path_blocked(cfg):
    router = OrderRouter(PaperBroker(cfg))
    with pytest.raises((PermissionError, NotImplementedError)):
        router.route_open("BTC/USDT", Signal.LONG, 0.1, 30_000.0, live=True,
                          gate_inputs=LiveGateInputs())
