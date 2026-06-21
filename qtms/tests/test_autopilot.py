"""Research autopilot: autonomous, paper-only, cannot go live, kill-switch safe."""
from __future__ import annotations

import time

from qtms.agents.autopilot import Autopilot
from qtms.app.safety import KILL_SWITCH


def test_autopilot_cannot_enable_live():
    assert Autopilot.CAN_ENABLE_LIVE is False
    ap = Autopilot()
    # No live broker / router references anywhere on the autopilot.
    assert not hasattr(ap, "live")
    assert not hasattr(ap, "router")


def test_one_cycle_runs_and_surfaces_promotion(cfg):
    cfg.monte_carlo.n_paths = 20
    ap = Autopilot(cfg)
    ap.state.symbol = "BTC/USDT"
    ap.drift = 0.0012          # data with a genuine edge
    ap.n_candles = 1400
    ap.paper_steps = 4
    ap.mc_paths = 20
    s = ap.run_one_cycle()
    assert s["cycle"] == 1
    assert s["can_enable_live"] is False
    assert "paper_equity" in s
    if s["promoted"]:
        assert len(ap.status()["pending_approvals"]) >= 1


def test_kill_switch_skips_cycle(cfg):
    ap = Autopilot(cfg)
    KILL_SWITCH.trip("test")
    s = ap.run_one_cycle()
    assert s.get("skipped") is True
    assert "kill switch" in s["reason"]


def test_manual_approval_required(cfg):
    cfg.monte_carlo.n_paths = 20
    ap = Autopilot(cfg)
    ap.drift = 0.0012
    ap.n_candles = 1400
    ap.paper_steps = 3
    ap.run_one_cycle()
    status = ap.status()
    # Promotions are surfaced as PENDING (approved=False) until a human approves.
    for p in status["pending_approvals"]:
        assert p["approved"] is False
    res = ap.approve_latest()
    if status["pending_approvals"]:
        assert res["approved"] is not None
        assert "live still disabled" in res["note"]


def test_start_stop_lifecycle(cfg):
    cfg.monte_carlo.n_paths = 15
    ap = Autopilot(cfg)
    out = ap.start(symbol="BTC/USDT", interval_seconds=3, drift=0.0, n_candles=300, paper_steps=2)
    assert out["running"] is True
    time.sleep(0.2)
    assert ap.status()["running"] is True
    stopped = ap.stop()
    assert stopped["running"] is False
