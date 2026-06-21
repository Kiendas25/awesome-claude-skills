"""Common schemas shared across every QTMS layer.

The cornerstone is ``LayerResult``: every layer (data, features, strategies,
quantum, stacking) emits one so that uncertainty, Monte Carlo summaries and
warnings are first-class, never hidden.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Signal(str, Enum):
    """Discrete trade direction. ``signal`` floats map onto these."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"

    @staticmethod
    def from_float(x: float, threshold: float = 0.15) -> "Signal":
        if x > threshold:
            return Signal.LONG
        if x < -threshold:
            return Signal.SHORT
        return Signal.FLAT


class LayerResult(BaseModel):
    """Uniform output object emitted by every layer in the stack.

    ``signal`` is in [-1, 1] (negative = short, positive = long).
    ``confidence`` and ``uncertainty`` are in [0, 1]. They are intentionally
    separate: a layer can be confident in direction yet carry high uncertainty
    from Monte Carlo dispersion.
    """

    layer_name: str
    timestamp: datetime = Field(default_factory=utcnow)
    symbol: str
    signal: float = 0.0
    confidence: float = 0.0
    uncertainty: float = 1.0
    expected_return: float = 0.0
    expected_risk: float = 0.0
    monte_carlo_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def direction(self) -> Signal:
        return Signal.from_float(self.signal)

    def with_warning(self, msg: str) -> "LayerResult":
        self.warnings.append(msg)
        return self


class MonteCarloSummary(BaseModel):
    """Standardized Monte Carlo result block used inside ``monte_carlo_summary``."""

    n_paths: int
    seed: int
    mean: float
    std: float
    p05: float
    p50: float
    p95: float
    prob_positive: float
    max_drawdown_p95: float = 0.0
    risk_of_ruin: float = 0.0
    robustness_score: float = 0.0
    extra: dict[str, Any] = Field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()


class TradeRecord(BaseModel):
    """Full journal entry for one paper trade — entry through exit."""

    trade_id: str
    symbol: str
    direction: Signal
    qty: float
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    fees: float = 0.0
    slippage: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    max_adverse_excursion: float = 0.0
    max_favorable_excursion: float = 0.0
    entry_reason: list[str] = Field(default_factory=list)
    exit_reason: list[str] = Field(default_factory=list)
    strategy_weights: dict[str, float] = Field(default_factory=dict)
    signal_snapshot: dict[str, Any] = Field(default_factory=dict)
    monte_carlo_summary: dict[str, Any] = Field(default_factory=dict)
    risk_state: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.exit_time is None


class StackDecision(BaseModel):
    """Output of the stacking + conviction gate layer."""

    symbol: str
    timestamp: datetime = Field(default_factory=utcnow)
    final_signal: Signal = Signal.FLAT
    conviction: float = 0.0
    position_size: float = 0.0
    strategy_weights: dict[str, float] = Field(default_factory=dict)
    approved: bool = False
    reject_reasons: list[str] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)
    layer_results: list[dict[str, Any]] = Field(default_factory=list)
