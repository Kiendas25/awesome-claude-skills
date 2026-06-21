"""Risk layer: sizing caps, exposure limits, drawdown guard, kill switch."""
from __future__ import annotations

from qtms.app.safety import KILL_SWITCH
from qtms.risk.drawdown_guard import DrawdownGuard
from qtms.risk.exposure import check_exposure
from qtms.risk.position_sizing import position_size
from qtms.risk.stop_loss_take_profit import check_exit, compute_levels
from qtms.app.schemas import Signal


def test_position_size_respects_cap(cfg):
    # Tiny stop distance would imply huge size; the cap must bind.
    out = position_size(10_000, 100.0, stop_distance_pct=0.0001, conviction=1.0, cfg=cfg)
    assert out["capped"]
    assert out["notional"] <= 10_000 * cfg.risk.max_position_pct + 1e-6


def test_position_size_scales_with_conviction(cfg):
    low = position_size(10_000, 100.0, 0.02, conviction=0.2, cfg=cfg)
    high = position_size(10_000, 100.0, 0.02, conviction=0.9, cfg=cfg)
    assert high["notional"] > low["notional"]


def test_exposure_blocks_too_many_positions(cfg):
    open_pos = {"A": 100.0, "B": 100.0, "C": 100.0}  # already at max (3)
    res = check_exposure(10_000, open_pos, "D", 100.0, cfg=cfg)
    assert not res["allowed"]


def test_exposure_blocks_per_symbol_cap(cfg):
    cap = 10_000 * cfg.risk.per_symbol_exposure_pct
    res = check_exposure(10_000, {"A": cap}, "A", cap, cfg=cfg)
    assert not res["allowed"]


def test_drawdown_guard_trips_kill_switch(cfg):
    g = DrawdownGuard(cfg)
    g.init(10_000, "2024-01-01")
    g.update(10_000, "2024-01-01")
    # Drop below max drawdown threshold.
    breach = 10_000 * (1 - cfg.risk.max_drawdown_pct - 0.01)
    status = g.update(breach, "2024-01-01")
    assert status["kill_switch"]
    assert KILL_SWITCH.active
    assert not g.can_open_new()


def test_daily_loss_halt(cfg):
    g = DrawdownGuard(cfg)
    g.init(10_000, "2024-01-01")
    loss = 10_000 * (1 - cfg.risk.max_daily_loss_pct - 0.005)
    status = g.update(loss, "2024-01-01")
    assert status["halted_for_day"]


def test_stop_take_levels_and_exit():
    levels = compute_levels(100.0, Signal.LONG, atr=2.0)
    assert levels["stop_loss"] < 100.0 < levels["take_profit"]
    assert check_exit(Signal.LONG, levels["stop_loss"] - 0.1, levels["stop_loss"], levels["take_profit"]) == "stop_loss"
    assert check_exit(Signal.LONG, levels["take_profit"] + 0.1, levels["stop_loss"], levels["take_profit"]) == "take_profit"
