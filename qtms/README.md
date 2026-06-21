# QTMS — Quantum Trading Multi-Layer Stacking Operation

A **deterministic, local-first, paper-trading-first** research system for
crypto-style intraday signals. It stacks classical strategies, a
quantum-inspired signal layer, and Monte Carlo risk simulation behind a strict
**conviction gate**, then paper-trades the result. An off-path learning agent
analyzes outcomes and proposes improvements.

> ⚠️ **No profit is promised.** Most strategies are treated as noise until
> proven by Monte Carlo robustness + validation. **Live trading is disabled by
> default and not implemented** in this MVP. No real funds are ever used.

---

## Why this design

- **Honesty over hype.** Every layer emits a uniform `LayerResult` carrying a
  signal *and* its uncertainty, Monte Carlo summary, and warnings. The system
  defaults to **FLAT / rejected** when there is no demonstrated edge.
- **Safety is structural, not advisory.** Live trading requires ~10 independent
  gates (config flag + two env vars + validation + paper sample + drawdown +
  risk-of-ruin + no critical violations + inactive kill switch + configured
  broker). Strategies cannot place orders; everything routes through risk + the
  order router. A global kill switch overrides everything.
- **Quantum-inspired, not magic.** Amplitude encoding, interference-style
  scoring, and probabilistic ("Born-rule") Monte Carlo run with **no quantum
  hardware**. If `qiskit` is installed a small circuit demo is available, but it
  is never required.

## Architecture (data flow)

```
market data ─▶ validation ─▶ features ─▶ strategies ┐
                                          quantum    ├▶ stacking ─▶ conviction gate ─▶ risk ─▶ order router ─▶ paper broker
            (Monte Carlo at every layer) regime ─────┘                                                   │
                                                                                          off-path: learning supervisor
                                                                                          (validation, analysis, Obsidian)
```

## Project layout

```
qtms/
  qtms/
    app/        config.py schemas.py safety.py state.py paper_engine.py main.py
    data/       synthetic_data.py validators.py storage.py market_data.py
    features/   trend.py mean_reversion.py volatility.py liquidity.py
                microstructure.py regime.py pipeline.py
    strategies/ base.py + 6 strategies (trend, mean-rev, breakout,
                vol-expansion, liquidity-sweep, stat-arb placeholder)
    quantum/    quantum_state_encoder.py quantum_signal_layer.py
                quantum_portfolio_optimizer.py quantum_monte_carlo.py
                fallback_quantum_inspired.py
    stacking/   signal_stack.py meta_model.py conviction_gate.py weight_allocator.py
    monte_carlo/engine.py bootstrap.py risk_of_ruin.py stress.py layer_simulator.py
    risk/       position_sizing.py exposure.py drawdown_guard.py
                stop_loss_take_profit.py kill_switch.py
    execution/  simulator.py paper_broker.py live_broker_stub.py
                slippage.py fees.py order_router.py
    agents/     learning_supervisor.py post_trade_analyzer.py
                strategy_researcher.py risk_reviewer.py
    reports/    metrics.py report_writer.py obsidian_exporter.py
    dashboard/  api_routes.py
    validation.py
  tests/        9 test modules (63 tests)
  QTMS_BRAIN/   Obsidian "second brain" notes (live readiness checklist + generated)
  data_store/   local Parquet/JSON storage (gitignored)
  run_demo.py   end-to-end CLI demo
```

## Setup

```bash
cd qtms
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
```

## How to run

**End-to-end demo (no server):**
```bash
python run_demo.py
```

**API + minimal dashboard:**
```bash
uvicorn qtms.app.main:app --reload
# open http://127.0.0.1:8000/  (dashboard)
# docs at http://127.0.0.1:8000/docs
```

Key endpoints: `GET /health`, `GET /config`, `POST /data/synthetic`,
`POST /backtest/run`, `POST /monte-carlo/run`, `POST /paper/start|step|stop`,
`GET /paper/status|trades`, `GET /reports/latest`,
`GET|POST /agents/learning/latest|analyze`,
`POST /live/request-approval`, `GET|POST /live/disabled-status`.

## How to test

```bash
cd qtms
pytest            # 63 tests, ~7s
```

Tests prove: no lookahead leakage, data validation catches bad data, Monte Carlo
is deterministic with a seed, every strategy returns a valid `LayerResult`, the
quantum encoder normalizes its state vector, the stacking gate rejects weak
signals, the risk layer caps oversized positions, the paper broker applies
fees/slippage, **live trading is disabled by default**, the **learning
supervisor cannot enable live trading**, and validation fails on small samples /
high drawdown.

## What is implemented

- Synthetic OHLCV generation (regime-switching, seeded) + CSV import + strict
  validation with a data-quality score; data-layer Monte Carlo robustness.
- Full feature set (trend, mean-reversion, volatility, liquidity, microstructure,
  regime) with feature-stability Monte Carlo.
- 6 deterministic strategies, each with confidence, invalidation level,
  reason codes, and per-strategy Monte Carlo (bootstrap, cost stress, signal
  persistence, probability of positive expectancy, drawdown distribution, risk
  of ruin).
- Quantum-inspired encoder / signal / portfolio optimizer / Monte Carlo, with a
  classical fallback and optional qiskit demo.
- Stacking engine + weight allocator + meta-model + conviction gate, with
  ensemble-stability Monte Carlo and a full explanation object.
- Risk layer: volatility-targeted sizing with hard caps, exposure limits,
  drawdown guard that trips the kill switch, ATR stops/takes, kill switch.
- Execution: slippage + fee models, paper broker with full trade journal
  (MAE/MFE, strategy weights, signal snapshot, MC summary), live broker **stub**,
  order router (the only path to a broker).
- Paper trading engine (bar-by-bar orchestration with stops + daily-loss halt).
- Validation & anti-overfitting: train/test split, walk-forward, bootstrap CIs,
  parameter sensitivity heatmap, regime performance, deflated-Sharpe and PBO
  placeholders, hard pass/fail gates.
- Research **autopilot**: an autonomous, paper-only background loop (refresh data
  → discover & promote on unseen data → paper-trade → analyze → report) that
  surfaces promotions for manual approval. It cannot enable live trading and the
  kill switch stops it (`/autopilot/start|stop|status|approve`).
- Off-path learning supervisor + analyzers/reviewers producing proposals only,
  with before/after Monte Carlo and an overfitting-risk score; writes Obsidian
  notes + a recommendations file. **Cannot** enable live or place orders.
- FastAPI app + minimal HTML dashboard.

## What remains as future work

- Real exchange data + execution (a `ccxt` adapter is stubbed and disabled).
  Live broker is a non-functional stub by design.
- Multi-asset / true pairs statistical arbitrage (current stat-arb is a labelled
  placeholder).
- Full deflated-Sharpe and probability-of-backtest-overfitting estimators
  (currently labelled placeholders).
- Real qiskit circuits beyond the demo; learned meta-model weights.
- Persistence of paper sessions across restarts; richer dashboard charts.

## Safety warnings

- **This is research software, not investment advice. No profit is promised.**
- Live trading is **off by default** and the MVP live broker **does not send real
  orders**. Do not wire a real exchange without completing
  `QTMS_BRAIN/Live_Readiness_Checklist.md`.
- No private keys belong in this repo. No secrets are printed in logs.
- No LLM runs in the trading path; agent analysis is strictly off-path.
- The kill switch overrides everything. When in doubt, the system stands aside.
