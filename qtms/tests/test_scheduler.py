"""Daily auto-curation scheduler: consensus logic, persistence, safety."""
from __future__ import annotations

from qtms.agents.scheduler import (
    DailyCampaignScheduler,
    compute_consensus,
)
from qtms.app.safety import KILL_SWITCH


def test_consensus_requires_consistency():
    # 4 days: 'foo' always ERASE -> ERASE; 'bar' mixed -> not ERASE; 'baz' KEEP.
    history = [
        {"verdicts": {"foo": "ERASE", "bar": "ERASE", "baz": "KEEP"}},
        {"verdicts": {"foo": "ERASE", "bar": "KEEP", "baz": "KEEP"}},
        {"verdicts": {"foo": "ERASE", "bar": "IMPROVE", "baz": "KEEP"}},
        {"verdicts": {"foo": "ERASE", "bar": "ERASE", "baz": "KEEP"}},
    ]
    c = compute_consensus(history)
    assert c["foo"]["verdict"] == "ERASE"   # 4/4 ERASE
    assert c["bar"]["verdict"] != "ERASE"   # only 2/4 ERASE -> not consistent
    assert c["baz"]["verdict"] == "KEEP"


def test_one_bad_day_does_not_erase():
    history = [
        {"verdicts": {"foo": "KEEP"}},
        {"verdicts": {"foo": "KEEP"}},
        {"verdicts": {"foo": "ERASE"}},  # single bad day
    ]
    assert compute_consensus(history)["foo"]["verdict"] != "ERASE"


def test_too_few_runs_no_erase_consensus():
    history = [{"verdicts": {"foo": "ERASE"}}, {"verdicts": {"foo": "ERASE"}}]
    # Only 2 runs (< MIN_RUNS_FOR_CONSENSUS) -> cannot reach ERASE consensus.
    assert compute_consensus(history)["foo"]["verdict"] != "ERASE"


def test_scheduler_run_now_records_history(cfg):
    cfg.monte_carlo.n_paths = 10
    from qtms.data.storage import save_json
    save_json("agents/campaign_history.json", {})  # clean slate
    sch = DailyCampaignScheduler(cfg)
    sch.state.days = 1
    sch.state.data_source = "synthetic"
    sch.state.n_candles = 500
    out = sch.run_now()
    assert out["ran"] is True
    assert "verdicts" in out and "consensus" in out
    assert sch.status()["n_runs"] >= 1
    assert sch.status()["history_len"] >= 1


def test_scheduler_cannot_enable_live(cfg):
    assert DailyCampaignScheduler.CAN_ENABLE_LIVE is False
    assert DailyCampaignScheduler(cfg).status()["can_enable_live"] is False


def test_scheduler_kill_switch_skips(cfg):
    sch = DailyCampaignScheduler(cfg)
    KILL_SWITCH.trip("test")
    try:
        out = sch.run_now()
        assert out.get("skipped") is True
    finally:
        KILL_SWITCH.reset()


def test_apply_consensus_keeps_minimum_active(cfg):
    # Force a history where nearly everything is consensus-ERASE; apply must
    # refuse to leave too few active strategies.
    sch = DailyCampaignScheduler(cfg)
    erase_all = {s: "ERASE" for s in cfg.active_strategies}
    sch.history = [{"verdicts": erase_all} for _ in range(3)]
    res = sch.apply_consensus()
    assert res["applied"] is False
    assert set(cfg.active_strategies)  # unchanged
