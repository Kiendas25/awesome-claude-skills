"""QTMS end-to-end demo (no server required).

Runs the full local-first pipeline deterministically:
  data -> features -> strategies -> quantum -> stacking -> paper trading ->
  validation -> learning supervisor -> Obsidian brain notes.

Usage:  python run_demo.py
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

from qtms.agents.learning_supervisor import LearningSupervisor
from qtms.app.config import get_config
from qtms.app.paper_engine import PaperTradingEngine
from qtms.app.safety import KILL_SWITCH, approval_phrase, evaluate_live_gate, LiveGateInputs
from qtms.data.market_data import MarketDataAdapter
from qtms.stacking.signal_stack import SignalStack


def main() -> None:
    cfg = get_config()
    symbol = "BTC/USDT"
    print("=" * 70)
    print("QTMS — Quantum Trading Multi-Layer Stacking Operation (DEMO)")
    print("Mode: RESEARCH / PAPER  |  Live trading: DISABLED  |  No real funds.")
    print("=" * 70)

    # 1) data
    df = MarketDataAdapter(cfg).synthetic(symbol, n=600, seed=cfg.seed)
    print(f"\n[1] Synthetic data: {len(df)} candles for {symbol} (seed={cfg.seed})")

    # 2) one full stacking decision
    print("\n[2] Stacking decision (all layers + Monte Carlo)...")
    dec = SignalStack(cfg).decide(df, seed=cfg.seed)
    print(f"    final_signal = {dec.final_signal.value}")
    print(f"    conviction   = {dec.conviction:.3f}  approved = {dec.approved}")
    if dec.reject_reasons:
        print(f"    rejected because: {dec.reject_reasons}")
    print(f"    strategy weights = { {k: round(v,2) for k,v in dec.strategy_weights.items()} }")
    print(f"    quantum stability = {dec.explanation['quantum_stability']:.3f}")

    # 3) paper trading
    print("\n[3] Paper trading (virtual money only)...")
    eng = PaperTradingEngine(cfg, mc_paths=30)
    eng.start(df, warmup=200)
    eng.run(max_steps=20)
    st = eng.stop()
    print(f"    equity={st['equity']:.2f}  closed_trades={st['n_trades']}  decisions={st['n_decisions']}")

    # 4) learning supervisor (off-path)
    print("\n[4] Learning supervisor (off-path, no LLM, cannot enable live)...")
    reco = LearningSupervisor(cfg).analyze(df, trades=eng.broker.closed_trades, run_validation=True)
    print(f"    overfitting_risk_score = {reco['overfitting_risk_score']:.3f}")
    print(f"    propose_disable        = {reco['propose_disable']}")
    print(f"    can_enable_live        = {reco['can_enable_live']} (always False)")
    n_pass = sum(1 for v in reco["validation"].values() if v["passed"])
    print(f"    strategies passing validation: {n_pass}/{len(reco['validation'])}")

    # 5) live gate status
    print("\n[5] Live trading gate status:")
    gate = evaluate_live_gate(LiveGateInputs(), cfg)
    print(f"    allowed = {gate.allowed}  (blocked by {len(gate.reasons)} gates)")
    print(f"    kill_switch active = {KILL_SWITCH.active}")
    print(f"    approval phrase (consent only) = {approval_phrase(cfg)}")

    print("\nObsidian notes written under QTMS_BRAIN/. Reports under data_store/reports/.")
    print("Reminder: most strategies are noise until validation passes. No profit promised.")


if __name__ == "__main__":
    main()
