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


@router.post("/data/synthetic")
def data_synthetic(req: SyntheticReq):
    cfg = get_config()
    df = MarketDataAdapter(cfg).synthetic(req.symbol, n=req.n, seed=req.seed)
    STATE.set_data(req.symbol, df)
    robustness = monte_carlo_data_robustness(df, n_paths=80, seed=cfg.seed)
    return {
        "symbol": req.symbol,
        "rows": len(df),
        "last_close": float(df["close"].iloc[-1]),
        "data_robustness": robustness.monte_carlo_summary,
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
