"""Multi-day paper-test campaign + strategy keep/fix/erase analysis (off-path).

Runs discovery + paper trading across the whole coin universe for several
'days' (independent data windows), then judges each strategy on the evidence:

* KEEP   — earns its place (validates often and/or contributes to promotions),
* IMPROVE — sometimes useful but inconsistent (tune before trusting),
* ERASE  — dead weight: almost never validates and never contributes.

This never trades real money and never enables live. On synthetic data it
assigns diverse regimes to coins (some trend up, some down, some choppy) so the
analysis is representative rather than uniformly "all noise". With live data it
uses the real markets as-is.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from ..app.config import QTMSConfig, get_config
from ..data.market_data import MarketDataAdapter
from ..reports import obsidian_exporter as obs
from ..data.storage import save_json
from .strategy_optimizer import discover_and_promote


def _regime_drift(i: int) -> float:
    """Assign a representative drift per coin index (synthetic only)."""
    pattern = [0.0012, 0.0, -0.0011, 0.0, 0.0010, 0.0, -0.0009, 0.0, 0.0008, 0.0]
    return pattern[i % len(pattern)]


def run_campaign(
    days: int = 3,
    cfg: QTMSConfig | None = None,
    data_source: str = "synthetic",
    n_candles: int = 1100,
    timeframe: str = "5m",
    progress=None,
) -> dict:
    cfg = cfg or get_config()
    symbols = list(cfg.symbols)
    adapter = MarketDataAdapter(cfg)

    strat = {n: {"trials": 0, "passed": 0, "promoted_in": 0, "rob_sum": 0.0}
             for n in cfg.active_strategies}
    coin_stats = {s: {"rounds": 0, "promotions": 0, "best_return": 0.0} for s in symbols}
    total_promotions = 0
    total_runs = 0

    for day in range(days):
        for i, sym in enumerate(symbols):
            seed = cfg.seed + day * 1000 + i
            if data_source == "live":
                try:
                    df = adapter.live(sym, timeframe=timeframe, limit=n_candles)
                except Exception:
                    df = adapter.synthetic(sym, n=n_candles, seed=seed, drift=_regime_drift(i))
            else:
                df = adapter.synthetic(sym, n=n_candles, seed=seed, drift=_regime_drift(i))
            df.attrs["symbol"] = sym

            res = discover_and_promote(df, cfg)
            total_runs += 1
            coin_stats[sym]["rounds"] += 1

            for d in res.strategy_detail:
                rec = strat.get(d["name"])
                if rec is None:
                    continue
                rec["trials"] += 1
                rec["rob_sum"] += float(d.get("robustness", 0.0))
                if d["passed"]:
                    rec["passed"] += 1
            if res.promoted:
                total_promotions += 1
                coin_stats[sym]["promotions"] += 1
                r = float((res.holdout_metrics or {}).get("total_return", 0.0) or 0.0)
                coin_stats[sym]["best_return"] = max(coin_stats[sym]["best_return"], r)
                for s in res.survivors:
                    if s["name"] in strat:
                        strat[s["name"]]["promoted_in"] += 1
            if progress:
                progress(day, sym, res.promoted)

    # --- per-strategy verdicts -------------------------------------------
    scorecards = []
    for name, rec in strat.items():
        trials = max(1, rec["trials"])
        pass_rate = rec["passed"] / trials
        promo_rate = rec["promoted_in"] / trials
        avg_rob = rec["rob_sum"] / trials
        if promo_rate >= 0.10 or (pass_rate >= 0.30 and promo_rate > 0):
            verdict = "KEEP"
        elif pass_rate >= 0.10 or promo_rate > 0:
            verdict = "IMPROVE"
        else:
            verdict = "ERASE"
        scorecards.append({
            "strategy": name, "verdict": verdict,
            "validation_pass_rate": round(pass_rate, 3),
            "promotion_contribution_rate": round(promo_rate, 3),
            "avg_robustness": round(avg_rob, 3),
            "trials": rec["trials"],
        })
    order = {"KEEP": 0, "IMPROVE": 1, "ERASE": 2}
    scorecards.sort(key=lambda s: (order[s["verdict"]], -s["promotion_contribution_rate"]))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "PAPER (no real money)",
        "data_source": data_source,
        "days": days,
        "symbols": symbols,
        "total_runs": total_runs,
        "total_promotions": total_promotions,
        "promotion_rate": round(total_promotions / max(1, total_runs), 3),
        "strategy_scorecards": scorecards,
        "coin_stats": coin_stats,
        "recommendations": {
            "keep": [s["strategy"] for s in scorecards if s["verdict"] == "KEEP"],
            "improve": [s["strategy"] for s in scorecards if s["verdict"] == "IMPROVE"],
            "erase": [s["strategy"] for s in scorecards if s["verdict"] == "ERASE"],
        },
        "can_enable_live": False,
        "note": ("Verdicts are evidence-based over a simulated multi-day paper test. "
                 "ERASE = never earned its place; IMPROVE = inconsistent; KEEP = pulls weight. "
                 "Apply manually — nothing here changes config or trades live."),
    }
    save_json("agents/campaign_latest.json", report)
    _write_report(report)
    return report


def _write_report(report: dict) -> None:
    rows = [
        f"| {s['strategy']} | {s['verdict']} | {s['validation_pass_rate']} | "
        f"{s['promotion_contribution_rate']} | {s['avg_robustness']} |"
        for s in report["strategy_scorecards"]
    ]
    body = [
        f"## {report['days']}-day paper-test campaign analysis\n",
        f"- Mode: **{report['mode']}** · data: {report['data_source']} · "
        f"runs: {report['total_runs']} · promotions: {report['total_promotions']} "
        f"(rate {report['promotion_rate']})\n",
        "### Strategy verdicts (KEEP / IMPROVE / ERASE)",
        "| strategy | verdict | validation pass-rate | promotion contribution | avg robustness |",
        "| --- | --- | --- | --- | --- |",
        *rows,
        "",
        f"- **KEEP:** {report['recommendations']['keep']}",
        f"- **IMPROVE:** {report['recommendations']['improve']}",
        f"- **ERASE:** {report['recommendations']['erase']}",
        "",
        "> " + report["note"],
    ]
    obs.write_note("Campaign Analysis", "\n".join(body),
                   tags=["campaign", "analysis", "qtms"], subfolder="campaign")
