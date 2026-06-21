"""Deterministic configuration for QTMS.

All randomness in the system flows from ``QTMSConfig.seed`` so that every
simulation is reproducible. Live trading flags live here too, defaulting to the
safest possible values.
"""
from __future__ import annotations

import os
from pydantic import BaseModel, Field


class RiskConfig(BaseModel):
    starting_balance: float = 10_000.0
    risk_per_trade: float = 0.005          # 0.5% of equity at risk per trade
    max_position_pct: float = 0.20         # max 20% of equity in one position
    max_open_positions: int = 3
    max_daily_loss_pct: float = 0.03       # halt new trades after 3% daily loss
    max_drawdown_pct: float = 0.20         # kill switch territory
    per_symbol_exposure_pct: float = 0.25
    max_risk_of_ruin: float = 0.05         # gate: reject above this


class CostConfig(BaseModel):
    taker_fee: float = 0.0006              # 6 bps per side
    maker_fee: float = 0.0002
    base_slippage_bps: float = 2.0         # baseline slippage in basis points
    spread_bps: float = 1.0                # placeholder spread assumption
    latency_ms: float = 150.0              # placeholder execution latency


class ConvictionConfig(BaseModel):
    min_conviction: float = 0.55
    min_prob_positive_expectancy: float = 0.55
    max_strategy_disagreement: float = 0.6
    min_data_quality: float = 0.6
    min_signal_stability: float = 0.5
    allowed_regimes: list[str] = Field(
        default_factory=lambda: ["trend_up", "trend_down", "range", "low_vol"]
    )


class MonteCarloConfig(BaseModel):
    n_paths: int = 500
    horizon: int = 64
    bootstrap_blocks: int = 8


class LiveConfig(BaseModel):
    """Live trading is OFF by default and multi-gated. See ``app/safety.py``."""

    live_trading_enabled: bool = False
    min_paper_trades: int = 200
    require_validation_pass: bool = True


class QTMSConfig(BaseModel):
    seed: int = 42
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    timeframe: str = "5m"
    data_dir: str = "data_store"
    brain_dir: str = "QTMS_BRAIN"
    active_strategies: list[str] = Field(
        default_factory=lambda: [
            "trend_following",
            "mean_reversion",
            "breakout",
            "volatility_expansion",
            "liquidity_sweep",
            "statistical_arbitrage",
        ]
    )
    risk: RiskConfig = Field(default_factory=RiskConfig)
    costs: CostConfig = Field(default_factory=CostConfig)
    conviction: ConvictionConfig = Field(default_factory=ConvictionConfig)
    monte_carlo: MonteCarloConfig = Field(default_factory=MonteCarloConfig)
    live: LiveConfig = Field(default_factory=LiveConfig)

    @classmethod
    def from_env(cls) -> "QTMSConfig":
        cfg = cls()
        if "QTMS_SEED" in os.environ:
            cfg.seed = int(os.environ["QTMS_SEED"])
        # Live enabling via env is read by safety.py; never auto-enabled here.
        return cfg


_CONFIG: QTMSConfig | None = None


def get_config() -> QTMSConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = QTMSConfig.from_env()
    return _CONFIG


def set_config(cfg: QTMSConfig) -> None:
    global _CONFIG
    _CONFIG = cfg
