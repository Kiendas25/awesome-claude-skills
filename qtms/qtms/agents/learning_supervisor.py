"""Learning Supervisor (off-path, NO LLM in hot path).

Runs AFTER simulations / paper trading to analyze results and propose
improvements. It is structurally incapable of:

* enabling live trading (``CAN_ENABLE_LIVE = False`` and no code path touches
  the live config),
* placing orders,
* mutating runtime config.

Everything it produces is a *proposal* persisted to a recommendations file and
the Obsidian brain. Applying a proposal requires a separate manual step.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..app.config import QTMSConfig, get_config
from ..app.schemas import TradeRecord
from ..data.storage import load_json, save_json
from ..reports import report_writer
from ..validation import validate_strategy
from ..strategies import build_active
from . import post_trade_analyzer, risk_reviewer, strategy_researcher
from .strategy_optimizer import discover_and_promote


class LearningSupervisor:
    # Hard invariant asserted by tests: the agent can never enable live trading.
    CAN_ENABLE_LIVE = False

    def __init__(self, cfg: QTMSConfig | None = None):
        self.cfg = cfg or get_config()

    # The following method exists ONLY to make the safety contract explicit and
    # testable. It always refuses.
    def enable_live_trading(self, *args, **kwargs):
        raise PermissionError(
            "Learning supervisor cannot enable live trading. Manual operator "
            "approval through the live gate is required."
        )

    def analyze(
        self,
        df: pd.DataFrame,
        trades: list[TradeRecord] | None = None,
        run_validation: bool = True,
    ) -> dict:
        trades = trades or []
        symbol = str(df.attrs.get("symbol", "UNKNOWN"))

        trade_analysis = post_trade_analyzer.analyze_trades(trades)

        validation_results: dict = {}
        if run_validation:
            for strat in build_active(self.cfg):
                vres = validate_strategy(strat, df, self.cfg)
                validation_results[strat.name] = {
                    "passed": vres.passed,
                    "score": vres.score,
                    "metrics": vres.metrics,
                    "monte_carlo": vres.monte_carlo,
                    "parameter_sensitivity": vres.parameter_sensitivity,
                    "fail_reasons": vres.fail_reasons,
                }

        # Aggregate risk-of-ruin across strategies for the risk reviewer.
        rors = [
            v.get("metrics", {}).get("risk_of_ruin", 0.0)
            for v in validation_results.values()
        ]
        agg = {"aggregate_risk_of_ruin": float(np.mean(rors)) if rors else 0.0}

        research = strategy_researcher.research(df, validation_results, self.cfg)
        risk_props = risk_reviewer.review_risk(trade_analysis, agg, self.cfg)

        # Overfitting risk score: high if many proposals fail the two-window
        # robustness check.
        checks = research.get("overfitting_check", {})
        if checks:
            overfit_risk = 1.0 - float(np.mean([1.0 if v["accepted"] else 0.0 for v in checks.values()]))
        else:
            overfit_risk = 0.0

        # Scorecards persisted for regime-specific / decay tracking over time.
        scorecards = self._update_scorecards(validation_results)

        recommendations = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "mode": "research/paper",
            "can_enable_live": self.CAN_ENABLE_LIVE,
            "requires_manual_approval": True,
            "trade_analysis": trade_analysis,
            "validation": validation_results,
            "parameter_proposals": research["parameter_proposals"],
            "propose_disable": research["propose_disable"],
            "risk_proposals": risk_props,
            "overfitting_risk_score": overfit_risk,
            "blocked_configs": [
                p for p in research["parameter_proposals"] if not p.get("accepted", False)
            ],
            "strategy_scorecards": scorecards,
            "note": (
                "Proposals only. Most strategies are treated as noise until "
                "validation passes. Apply manually after review."
            ),
        }

        report_writer.write_recommendations(recommendations)
        if trades:
            status = {
                "equity": 0.0, "starting_balance": self.cfg.risk.starting_balance,
                "n_trades": len(trades), "n_decisions": 0,
            }
            report_writer.write_daily_paper_report(symbol, status, trade_analysis)
        report_writer.write_validation_report(symbol, validation_results)
        save_json("agents/learning_latest.json", recommendations)
        return recommendations

    def discover(self, df: pd.DataFrame) -> dict:
        """Search strategy variants, compose the survivors, and re-validate the
        composite on an UNSEEN holdout window. Persists the promoted config and
        writes an Obsidian note. Promotion is a research verdict only — it never
        enables live trading or changes runtime config automatically."""
        symbol = str(df.attrs.get("symbol", "UNKNOWN"))
        result = discover_and_promote(df, self.cfg)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "promoted": result.promoted,
            "candidates_evaluated": result.candidates_evaluated,
            "survivors": result.survivors,
            "weights": result.weights,
            "train_metrics": result.train_metrics,
            "holdout_metrics": result.holdout_metrics,
            "reasons": result.reasons,
            "can_enable_live": self.CAN_ENABLE_LIVE,
            "requires_manual_approval": True,
            "note": (
                "Composite was tuned on TRAIN and judged on an UNSEEN holdout. "
                "A 'promoted' verdict means it survived unseen data once — it is "
                "NOT a profit guarantee. Continue paper trading before trusting it."
            ),
        }
        save_json("agents/promoted_strategy.json", payload)
        body = [
            f"## Strategy discovery & promotion — {symbol}\n",
            f"- **Verdict:** {'PROMOTED ✅' if result.promoted else 'NOT promoted ❌'}",
            f"- candidates evaluated: {result.candidates_evaluated}",
            f"- survivors (passed TRAIN validation): {[s['name'] for s in result.survivors]}",
            f"- ensemble weights: { {k: round(v,2) for k,v in result.weights.items()} }",
            f"- holdout metrics: {result.holdout_metrics}",
            f"- reasons: {result.reasons}\n",
            "> Promotion = survived UNSEEN holdout once. Not a profit promise. "
            "Keep paper trading. Live trading stays disabled.",
        ]
        report_writer.obs.write_note(
            f"Strategy Promotion {symbol}", "\n".join(body),
            tags=["promotion", "learning", "qtms"], subfolder="learning",
        )
        return payload

    @staticmethod
    def latest_promotion() -> dict | None:
        return load_json("agents/promoted_strategy.json", default=None)

    def _update_scorecards(self, validation_results: dict) -> dict:
        card = load_json("agents/scorecards.json", default={})
        for name, v in validation_results.items():
            entry = card.setdefault(name, {"history": []})
            entry["history"].append(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "passed": v.get("passed"),
                    "score": v.get("score"),
                    "robustness": v.get("monte_carlo", {}).get("robustness_score", 0.0),
                }
            )
            entry["history"] = entry["history"][-20:]  # keep last 20
            entry["latest_passed"] = v.get("passed")
            entry["latest_score"] = v.get("score")
        save_json("agents/scorecards.json", card)
        return card

    @staticmethod
    def latest() -> dict | None:
        return load_json("agents/learning_latest.json", default=None)
