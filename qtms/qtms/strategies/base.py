"""Strategy base class.

A strategy exposes a *continuous* score in [-1, 1] per bar. The base class turns
that into discrete positions, the latest LayerResult, and a Monte Carlo
robustness summary. Strategies NEVER place orders — they only produce signals.
The risk layer and execution router decide what (if anything) actually trades.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from ..app.config import QTMSConfig, get_config
from ..app.schemas import LayerResult, Signal, utcnow
from ..features.pipeline import compute_features
from ..monte_carlo.engine import monte_carlo_strategy


class Strategy(ABC):
    name: str = "base"
    entry_threshold: float = 0.3

    def __init__(self, params: dict | None = None, cfg: QTMSConfig | None = None):
        self.params = {**self.default_params(), **(params or {})}
        self.cfg = cfg or get_config()

    @staticmethod
    def default_params() -> dict:
        return {}

    @abstractmethod
    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        """Return a continuous conviction score in [-1, 1] per bar."""

    @abstractmethod
    def reason_codes(self, features: pd.DataFrame, df: pd.DataFrame) -> list[str]:
        """Human-readable reasons for the latest signal."""

    def generate_signals(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        s = self.score(features, df).clip(-1, 1)
        pos = pd.Series(0.0, index=s.index)
        pos[s > self.entry_threshold] = 1.0
        pos[s < -self.entry_threshold] = -1.0
        return pos

    def evaluate(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame | None = None,
        run_mc: bool = True,
        seed: int | None = None,
    ) -> LayerResult:
        features = compute_features(df) if features is None else features
        score = self.score(features, df).clip(-1, 1)
        positions = self.generate_signals(features, df)
        latest = float(score.iloc[-1])
        confidence = float(min(1.0, abs(latest)))

        atr_pct = float(features.get("atr_pct", pd.Series([0.0])).iloc[-1])
        price = float(df["close"].iloc[-1])
        invalidation = (
            price * (1 - 1.5 * atr_pct) if latest > 0 else price * (1 + 1.5 * atr_pct)
        )

        mc = {}
        uncertainty = 1.0 - confidence
        if run_mc:
            mc = monte_carlo_strategy(
                positions, df, cfg=self.cfg, seed=self.cfg.seed if seed is None else seed
            )
            uncertainty = float(1.0 - mc.get("robustness_score", 0.0))

        warnings: list[str] = []
        if mc and mc.get("n_trades", 0) < 5:
            warnings.append("very few trades — signal may be noise")
        if mc and mc.get("robustness_score", 0.0) < 0.5:
            warnings.append("low Monte Carlo robustness")

        return LayerResult(
            layer_name=f"strategy:{self.name}",
            timestamp=utcnow(),
            symbol=str(df.attrs.get("symbol", "UNKNOWN")),
            signal=latest,
            confidence=confidence,
            uncertainty=uncertainty,
            expected_return=float(mc.get("mean_bootstrap_return", 0.0)) if mc else 0.0,
            expected_risk=float(mc.get("max_drawdown_p95", atr_pct)) if mc else atr_pct,
            monte_carlo_summary=mc,
            warnings=warnings,
            metadata={
                "direction": Signal.from_float(latest).value,
                "invalidation_level": invalidation,
                "expected_holding_bars": self.params.get("holding_bars", 10),
                "estimated_risk_pct": 1.5 * atr_pct,
                "reason_codes": self.reason_codes(features, df),
                "params": self.params,
            },
        )
