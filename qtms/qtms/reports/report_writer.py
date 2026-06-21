"""Report writer: turns analysis dicts into Markdown reports + JSON, and writes
them to both the data store and the Obsidian brain.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..data.storage import save_json
from . import obsidian_exporter as obs


def _fmt(d: dict, indent: int = 0) -> str:
    lines = []
    pad = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{pad}- **{k}**:")
            lines.append(_fmt(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{pad}- **{k}**: {v}")
        else:
            lines.append(f"{pad}- **{k}**: {v}")
    return "\n".join(lines)


def write_validation_report(symbol: str, results: dict) -> dict:
    body = [f"## Validation summary — {symbol}\n"]
    rows = []
    for name, r in results.items():
        if not isinstance(r, dict):
            continue
        rows.append([
            name,
            "PASS" if r.get("passed") else "FAIL",
            round(r.get("score", 0), 3),
            r.get("metrics", {}).get("n_trades", 0),
            round(r.get("metrics", {}).get("total_return", 0), 4),
            round(r.get("metrics", {}).get("max_drawdown", 0), 4),
            "; ".join(r.get("fail_reasons", [])) or "-",
        ])
    body.append(obs.md_table(
        ["strategy", "verdict", "score", "trades", "return", "maxDD", "fail_reasons"], rows
    ))
    note = obs.write_note(f"Validation Summary {symbol}", "\n".join(body),
                          tags=["validation", "qtms"], subfolder="validations")
    save_json("reports/validation_latest.json", results)
    return {"note": note}


def write_daily_paper_report(symbol: str, status: dict, trade_analysis: dict,
                             mc_summary: dict | None = None) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body = [
        f"## Daily paper trading report — {symbol} — {today}\n",
        f"- Mode: **PAPER (no real money)**",
        f"- Equity: {round(status.get('equity', 0), 2)} / start {status.get('starting_balance')}",
        f"- Closed trades: {status.get('n_trades', 0)}",
        f"- Decisions evaluated: {status.get('n_decisions', 0)}\n",
        "### Trade analysis",
        _fmt(trade_analysis),
    ]
    if mc_summary:
        body += ["\n### Monte Carlo (paper survivability)", _fmt(mc_summary)]
    body += [
        "\n### What improved / what failed",
        "- See strategy attribution and decay above.",
        "\n### Recommended next experiments",
        "- Re-run validation after >= configured min sample of paper trades.",
    ]
    note = obs.write_note(f"Daily Paper Report {symbol}", "\n".join(body),
                          tags=["paper", "daily", "qtms"], subfolder="daily")
    save_json("reports/paper_latest.json", {"status": status, "analysis": trade_analysis})
    return {"note": note}


def write_recommendations(reco: dict) -> dict:
    body = [
        "## Learning Supervisor Recommendations\n",
        "> These are PROPOSALS only. Manual approval is required to apply any of "
        "them. The learning agent cannot enable live trading or change config.\n",
        "```json",
        json.dumps(reco, indent=2, default=str),
        "```",
    ]
    note = obs.write_note("Learning Supervisor Recommendations", "\n".join(body),
                          tags=["learning", "recommendations", "qtms"], subfolder="learning")
    save_json("reports/recommendations_latest.json", reco)
    return {"note": note}
