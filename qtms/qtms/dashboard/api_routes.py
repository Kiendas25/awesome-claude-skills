"""FastAPI routes for QTMS. Local-first, paper-only by default."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..app.config import get_config
from ..app.paper_engine import PaperTradingEngine
from ..app.safety import (
    KILL_SWITCH,
    LiveGateInputs,
    approval_phrase,
    evaluate_live_gate,
)
from ..app.state import STATE
from ..agents.autopilot import get_autopilot
from ..agents.learning_supervisor import LearningSupervisor
from ..data.market_data import MarketDataAdapter, monte_carlo_data_robustness
from ..data.storage import load_json
from ..monte_carlo.engine import monte_carlo_strategy
from ..stacking.signal_stack import SignalStack
from ..strategies import build_strategy
from ..validation import validate_strategy

router = APIRouter()


class SyntheticReq(BaseModel):
    symbol: str = "BTC/USDT"
    n: int = 800
    seed: int | None = None
    drift: float = 0.0  # per-bar log-drift; >0 injects a genuine trend/edge


class BacktestReq(BaseModel):
    symbol: str = "BTC/USDT"
    strategy: str = "trend_following"


class MonteCarloReq(BaseModel):
    symbol: str = "BTC/USDT"
    strategy: str = "trend_following"
    n_paths: int = 300


class PaperStartReq(BaseModel):
    symbol: str = "BTC/USDT"
    warmup: int = 150
    mc_paths: int = 40


class PaperRunReq(BaseModel):
    steps: int = 25


class AnalyzeReq(BaseModel):
    symbol: str = "BTC/USDT"
    run_validation: bool = True


class AutopilotReq(BaseModel):
    symbol: str | None = None          # single symbol, or…
    symbols: list[str] | None = None   # …a list to rotate through (defaults to top-10)
    interval_seconds: float = 20.0
    drift: float = 0.0008
    n_candles: int = 1200
    paper_steps: int = 12
    data_source: str = "synthetic"   # "synthetic" or "live" (real OHLCV)
    timeframe: str = "5m"
    source: str = "auto"             # exchange name or 'auto' for live data
    limit: int = 1000


class LiveDataReq(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "5m"
    limit: int = 1000
    source: str = "auto"


@router.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "live" if get_config().live.live_trading_enabled else "paper/research",
        "live_trading_enabled": get_config().live.live_trading_enabled,
        "kill_switch": KILL_SWITCH.active,
    }


@router.get("/config")
def config():
    return get_config().model_dump()


@router.get("/symbols")
def symbols():
    return {"symbols": get_config().symbols}


@router.post("/data/synthetic")
def data_synthetic(req: SyntheticReq):
    cfg = get_config()
    df = MarketDataAdapter(cfg).synthetic(req.symbol, n=req.n, seed=req.seed, drift=req.drift)
    STATE.set_data(req.symbol, df)
    robustness = monte_carlo_data_robustness(df, n_paths=80, seed=cfg.seed)
    return {
        "symbol": req.symbol,
        "rows": len(df),
        "last_close": float(df["close"].iloc[-1]),
        "data_robustness": robustness.monte_carlo_summary,
    }


@router.post("/data/live")
def data_live(req: LiveDataReq):
    """Fetch REAL OHLCV from public exchanges (read-only, no key, no trading)."""
    cfg = get_config()
    try:
        df = MarketDataAdapter(cfg).live(
            req.symbol, timeframe=req.timeframe, limit=req.limit, source=req.source
        )
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Public exchange APIs may be blocked on your network/region. "
                    "Try a different 'source' (binance/coinbase/kraken) or use synthetic data.",
        }
    STATE.set_data(req.symbol, df)
    return {
        "ok": True,
        "symbol": req.symbol,
        "source": df.attrs.get("source"),
        "timeframe": req.timeframe,
        "rows": len(df),
        "last_close": float(df["close"].iloc[-1]),
        "first_time": str(df.index[0]),
        "last_time": str(df.index[-1]),
        "data_quality": df.attrs.get("data_quality_score"),
    }


@router.post("/backtest/run")
def backtest_run(req: BacktestReq):
    cfg = get_config()
    df = STATE.get_or_make(req.symbol)
    vres = validate_strategy(build_strategy(req.strategy, cfg=cfg), df, cfg)
    return {
        "symbol": req.symbol,
        "strategy": req.strategy,
        "passed": vres.passed,
        "score": vres.score,
        "metrics": vres.metrics,
        "fail_reasons": vres.fail_reasons,
        "walk_forward": vres.walk_forward,
        "regime_performance": vres.regime_performance,
    }


@router.post("/monte-carlo/run")
def monte_carlo_run(req: MonteCarloReq):
    cfg = get_config()
    df = STATE.get_or_make(req.symbol)
    strat = build_strategy(req.strategy, cfg=cfg)
    from ..features.pipeline import compute_features

    pos = strat.generate_signals(compute_features(df), df)
    mc = monte_carlo_strategy(pos, df, cfg=cfg, seed=cfg.seed, n_paths=req.n_paths)
    return {"symbol": req.symbol, "strategy": req.strategy, "monte_carlo": mc}


@router.post("/paper/start")
def paper_start(req: PaperStartReq):
    cfg = get_config()
    df = STATE.get_or_make(req.symbol)
    STATE.engine = PaperTradingEngine(cfg, mc_paths=req.mc_paths)
    return STATE.engine.start(df, warmup=req.warmup)


@router.post("/paper/step")
def paper_step(req: PaperRunReq | None = None):
    if STATE.engine is None:
        return {"error": "paper engine not started"}
    steps = req.steps if req else 1
    return STATE.engine.run(max_steps=steps)


@router.post("/paper/stop")
def paper_stop():
    if STATE.engine is None:
        return {"error": "paper engine not started"}
    return STATE.engine.stop()


@router.get("/paper/status")
def paper_status():
    if STATE.engine is None:
        return {"running": False, "note": "not started"}
    return STATE.engine.status()


@router.get("/paper/trades")
def paper_trades():
    if STATE.engine is None:
        return {"trades": []}
    return {"trades": [t.model_dump() for t in STATE.engine.broker.closed_trades]}


@router.get("/reports/latest")
def reports_latest():
    return {
        "validation": load_json("reports/validation_latest.json", default=None),
        "paper": load_json("reports/paper_latest.json", default=None),
        "recommendations": load_json("reports/recommendations_latest.json", default=None),
    }


@router.get("/agents/learning/latest")
def learning_latest():
    return LearningSupervisor.latest() or {"note": "no analysis yet"}


@router.post("/agents/learning/analyze")
def learning_analyze(req: AnalyzeReq):
    cfg = get_config()
    df = STATE.get_or_make(req.symbol)
    trades = STATE.engine.broker.closed_trades if STATE.engine else []
    reco = LearningSupervisor(cfg).analyze(df, trades=trades, run_validation=req.run_validation)
    # Trim heavy fields for the HTTP response.
    return {
        "symbol": reco["symbol"],
        "overfitting_risk_score": reco["overfitting_risk_score"],
        "propose_disable": reco["propose_disable"],
        "parameter_proposals": reco["parameter_proposals"],
        "risk_proposals": reco["risk_proposals"],
        "can_enable_live": reco["can_enable_live"],
        "requires_manual_approval": reco["requires_manual_approval"],
    }


@router.post("/agents/learning/discover")
def learning_discover(req: AnalyzeReq):
    """Search strategy variants, compose survivors, and re-validate the composite
    on an UNSEEN holdout. Returns whether it was promoted. Promotion is a
    research verdict only — it never enables live trading or changes config."""
    cfg = get_config()
    df = STATE.get_or_make(req.symbol)
    return LearningSupervisor(cfg).discover(df)


@router.get("/agents/learning/promotion")
def learning_promotion():
    return LearningSupervisor.latest_promotion() or {"note": "no discovery run yet"}


@router.post("/autopilot/start")
def autopilot_start(req: AutopilotReq):
    """Start the autonomous RESEARCH loop (paper-only). It discovers, paper
    trades, analyzes, and surfaces promotions for manual approval. It can never
    enable live trading and the kill switch stops it."""
    return get_autopilot().start(
        symbol=req.symbol, symbols=req.symbols, interval_seconds=req.interval_seconds,
        drift=req.drift, n_candles=req.n_candles, paper_steps=req.paper_steps,
        data_source=req.data_source, timeframe=req.timeframe,
        source=req.source, limit=req.limit,
    )


@router.post("/autopilot/stop")
def autopilot_stop():
    return get_autopilot().stop()


@router.get("/autopilot/status")
def autopilot_status():
    return get_autopilot().status()


@router.post("/autopilot/approve")
def autopilot_approve():
    """Manually approve the latest promotion (for PAPER use only)."""
    return get_autopilot().approve_latest()


@router.post("/live/request-approval")
def live_request_approval():
    """Returns the live gate status and what is still blocking. Never enables
    live trading. The approval phrase is shown so an operator can consciously
    set it as an environment variable — that alone is still not sufficient."""
    cfg = get_config()
    decision = evaluate_live_gate(LiveGateInputs(), cfg)
    return {
        "live_trading_enabled": cfg.live.live_trading_enabled,
        "approved": decision.allowed,
        "gate_checks": decision.checks,
        "blocking_reasons": decision.reasons,
        "required_env": {
            "QTMS_ENABLE_LIVE": "true",
            "QTMS_MANUAL_LIVE_APPROVAL": approval_phrase(cfg),
        },
        "warning": "Live trading is disabled by default and not implemented in the MVP.",
    }


@router.post("/live/disabled-status")
@router.get("/live/disabled-status")
def live_disabled_status():
    cfg = get_config()
    return {
        "live_trading_enabled": cfg.live.live_trading_enabled,
        "is_disabled": not cfg.live.live_trading_enabled,
        "kill_switch": KILL_SWITCH.active,
        "message": "LIVE TRADING DISABLED. Paper trading only. No real funds at risk.",
    }
