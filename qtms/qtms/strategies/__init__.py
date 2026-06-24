"""Strategy registry."""
from __future__ import annotations

from .base import Strategy
from .breakout import Breakout
from .extended import (
    BollingerBounce,
    DonchianBreakout,
    MACDTrend,
    Momentum,
    RSIReversion,
    VWAPReversion,
)
from .liquidity_sweep import LiquiditySweep
from .mean_reversion import MeanReversion
from .statistical_arbitrage import StatisticalArbitrage
from .trend_following import TrendFollowing
from .volatility_expansion import VolatilityExpansion

REGISTRY: dict[str, type[Strategy]] = {
    TrendFollowing.name: TrendFollowing,
    MeanReversion.name: MeanReversion,
    Breakout.name: Breakout,
    VolatilityExpansion.name: VolatilityExpansion,
    LiquiditySweep.name: LiquiditySweep,
    StatisticalArbitrage.name: StatisticalArbitrage,
    # extended universe
    Momentum.name: Momentum,
    RSIReversion.name: RSIReversion,
    DonchianBreakout.name: DonchianBreakout,
    MACDTrend.name: MACDTrend,
    BollingerBounce.name: BollingerBounce,
    VWAPReversion.name: VWAPReversion,
}


def build_strategy(name: str, params: dict | None = None, cfg=None) -> Strategy:
    if name not in REGISTRY:
        raise KeyError(f"unknown strategy: {name}")
    return REGISTRY[name](params=params, cfg=cfg)


def build_active(cfg) -> list[Strategy]:
    return [build_strategy(n, cfg=cfg) for n in cfg.active_strategies if n in REGISTRY]
