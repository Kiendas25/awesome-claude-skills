"""Multi-layer stacking operation — the heart of QTMS.

Runs every active strategy, the quantum-inspired signal + its Monte Carlo, the
data/feature robustness layers, allocates weights, combines everything, runs a
stacking-level Monte Carlo for ensemble stability, and finally applies the
conviction gate to produce a single auditable ``StackDecision``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..app.config import QTMSConfig, get_config
from ..app.schemas import LayerResult, Signal, StackDecision, utcnow
from ..data.market_data import monte_carlo_data_robustness
from ..features.pipeline import compute_features, current_regime, monte_carlo_feature_stability
from ..quantum.quantum_monte_carlo import monte_carlo_quantum
from ..quantum.quantum_signal_layer import evaluate as quantum_evaluate
from ..risk.position_sizing import position_size
from ..strategies import build_active
from .conviction_gate import GateInputs, evaluate_gate
from .meta_model import combine
from .weight_allocator import allocate


def _stacking_monte_carlo(
    signals: dict[str, float],
    weights: dict[str, float],
    quantum_signal: float,
    base_signal: float,
    n_paths: int = 300,
    seed: int = 42,
) -> dict:
    """Perturb weights and quantum output; measure how often the final
    directional decision survives. Reject unstable ensembles."""
    rng = np.random.default_rng(seed)
    base_dir = np.sign(base_signal)
    if base_dir == 0:
        return {"n_paths": n_paths, "seed": seed, "signal_stability": 0.0}
    stable = 0
    names = list(signals.keys())
    base_w = np.array([weights.get(n, 0.0) for n in names])
    s = np.array([signals[n] for n in names])
    for _ in range(n_paths):
        w = np.clip(base_w + rng.normal(0, 0.1, size=len(names)), 0, None)
        if w.sum() == 0:
            continue
        w = w / w.sum()
        q = quantum_signal + rng.normal(0, 0.15)
        combined = 0.75 * float(np.dot(w, s)) + 0.25 * q
        if np.sign(combined) == base_dir:
            stable += 1
    return {
        "n_paths": n_paths,
        "seed": seed,
        "signal_stability": stable / n_paths,
    }


class SignalStack:
    def __init__(self, cfg: QTMSConfig | None = None):
        self.cfg = cfg or get_config()
        self.strategies = build_active(self.cfg)

    def decide(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame | None = None,
        equity: float | None = None,
        strategy_mc_paths: int = 120,
        seed: int | None = None,
    ) -> StackDecision:
        seed = self.cfg.seed if seed is None else seed
        symbol = str(df.attrs.get("symbol", "UNKNOWN"))
        features = compute_features(df) if features is None else features
        equity = equity if equity is not None else self.cfg.risk.starting_balance

        layer_results: list[LayerResult] = []

        # --- data + feature robustness layers ------------------------------
        # Auxiliary MC budgets scale with the configured path count so the
        # lighter paper-trading budget also speeds these up.
        aux = max(20, min(80, self.cfg.monte_carlo.n_paths))
        data_res = monte_carlo_data_robustness(df, n_paths=aux, seed=seed)
        feat_res = monte_carlo_feature_stability(df, n_paths=max(20, aux // 2 + 10), seed=seed)
        layer_results += [data_res, feat_res]
        data_quality = data_res.monte_carlo_summary.get("data_quality_score", 0.0)
        feature_robustness = feat_res.monte_carlo_summary.get(
            "feature_robustness_score", 0.0
        )

        # --- strategy layer ------------------------------------------------
        signals: dict[str, float] = {}
        robustness: dict[str, float] = {}
        prob_pos: dict[str, float] = {}
        ror: dict[str, float] = {}
        dd: dict[str, float] = {}
        cost_surv: dict[str, float] = {}
        signal_series: dict[str, np.ndarray] = {}

        for strat in self.strategies:
            res = strat.evaluate(
                df, features=features, run_mc=True, seed=seed
            )
            # Re-run MC with reduced paths for speed at the stack level handled
            # inside evaluate via cfg; keep the returned summary.
            mc = res.monte_carlo_summary
            signals[strat.name] = res.signal
            robustness[strat.name] = mc.get("robustness_score", 0.0)
            prob_pos[strat.name] = mc.get("prob_positive_expectancy", 0.0)
            ror[strat.name] = mc.get("risk_of_ruin", 1.0)
            dd[strat.name] = mc.get("max_drawdown_p95", 1.0)
            cost_surv[strat.name] = mc.get("cost_survival", 0.0)
            signal_series[strat.name] = (
                strat.score(features, df).clip(-1, 1).to_numpy()
            )
            layer_results.append(res)

        # --- quantum layer -------------------------------------------------
        q_res = quantum_evaluate(df, features)
        q_mc = monte_carlo_quantum(df, features, n_paths=max(40, aux), seed=seed)
        layer_results += [q_res, q_mc]
        q_signal = q_res.signal
        q_stability = q_mc.monte_carlo_summary.get("quantum_signal_stability", 0.0)

        # --- weight allocation + meta combine ------------------------------
        weights = allocate(
            list(signals.keys()), robustness, signal_series, cfg=self.cfg
        )
        meta = combine(signals, weights, q_signal)
        combined_signal = meta["combined_signal"]
        disagreement = meta["disagreement"]

        # --- stacking Monte Carlo ------------------------------------------
        stack_mc = _stacking_monte_carlo(
            signals, weights, q_signal, combined_signal, seed=seed
        )
        signal_stability = min(
            stack_mc["signal_stability"], q_stability if q_stability else 1.0
        )

        # --- aggregate gate metrics (weighted by allocation) ---------------
        active = [n for n in weights if weights[n] > 0]
        wsum = sum(weights[n] for n in active) or 1.0

        def wavg(d: dict[str, float], default: float) -> float:
            if not active:
                return default
            return sum(weights[n] * d.get(n, default) for n in active) / wsum

        agg_prob_pos = wavg(prob_pos, 0.0)
        agg_ror = wavg(ror, 1.0)
        agg_dd = wavg(dd, 1.0)
        agg_cost = wavg(cost_surv, 0.0)
        agg_robust = wavg(robustness, 0.0)
        regime = current_regime(features)

        # Conviction blends signal magnitude, ensemble robustness, stability,
        # agreement, and data/feature quality — deliberately multiplicative so a
        # single weak factor caps conviction.
        conviction = float(
            abs(combined_signal)
            * (0.5 + 0.5 * agg_robust)
            * (0.5 + 0.5 * signal_stability)
            * (1.0 - 0.5 * disagreement)
            * (0.5 + 0.5 * data_quality)
            * (0.5 + 0.5 * feature_robustness)
        )
        conviction = float(np.clip(conviction, 0.0, 1.0))

        # --- conviction gate ----------------------------------------------
        gate = evaluate_gate(
            GateInputs(
                conviction=conviction,
                prob_positive_expectancy=agg_prob_pos,
                risk_of_ruin=agg_ror,
                max_drawdown_sim=agg_dd,
                disagreement=disagreement,
                regime=regime,
                data_quality=data_quality,
                signal_stability=signal_stability,
                cost_survival=agg_cost,
            ),
            cfg=self.cfg,
        )

        final_dir = Signal.from_float(combined_signal) if gate["approved"] else Signal.FLAT

        # --- position sizing recommendation --------------------------------
        atr_pct = float(features.get("atr_pct", pd.Series([0.01])).iloc[-1]) or 0.01
        price = float(df["close"].iloc[-1])
        size = position_size(
            equity, price, stop_distance_pct=1.5 * atr_pct, conviction=conviction,
            cfg=self.cfg,
        )

        return StackDecision(
            symbol=symbol,
            timestamp=utcnow(),
            final_signal=final_dir,
            conviction=conviction,
            position_size=size["qty"] if gate["approved"] else 0.0,
            strategy_weights=weights,
            approved=gate["approved"],
            reject_reasons=gate["reject_reasons"],
            explanation={
                "combined_signal": combined_signal,
                "meta": meta,
                "regime": regime,
                "data_quality": data_quality,
                "feature_robustness": feature_robustness,
                "signal_stability": signal_stability,
                "quantum_signal": q_signal,
                "quantum_stability": q_stability,
                "agg_prob_positive_expectancy": agg_prob_pos,
                "agg_risk_of_ruin": agg_ror,
                "agg_max_drawdown_p95": agg_dd,
                "agg_cost_survival": agg_cost,
                "agg_robustness": agg_robust,
                "disagreement": disagreement,
                "gate_checks": gate["checks"],
                "stacking_monte_carlo": stack_mc,
                "position_sizing": size,
                "strategy_signals": signals,
                "strategy_robustness": robustness,
            },
            layer_results=[r.model_dump() for r in layer_results],
        )
