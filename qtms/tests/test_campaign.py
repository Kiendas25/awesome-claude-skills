"""Multi-day campaign analysis: produces keep/fix/erase verdicts, paper-only."""
from __future__ import annotations

from qtms.agents.campaign import run_campaign


def test_campaign_produces_verdicts(cfg):
    cfg.monte_carlo.n_paths = 10
    # Small run: 1 day, fewer candles for speed.
    report = run_campaign(days=1, cfg=cfg, n_candles=600)
    assert report["can_enable_live"] is False
    assert report["total_runs"] == len(cfg.symbols)
    cards = report["strategy_scorecards"]
    assert len(cards) == len(cfg.active_strategies)
    for c in cards:
        assert c["verdict"] in ("KEEP", "IMPROVE", "ERASE")
        assert 0.0 <= c["validation_pass_rate"] <= 1.0
    rec = report["recommendations"]
    assert set(rec) == {"keep", "improve", "erase"}
    # Every strategy is classified into exactly one bucket.
    assert sum(len(v) for v in rec.values()) == len(cards)
