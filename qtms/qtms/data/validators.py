"""Market-data validation and a data-quality score.

The validator is intentionally strict: bad data is the cheapest way to fool a
backtest. It reports issues rather than silently repairing them, and produces a
0..1 ``quality_score`` consumed by the conviction gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass
class ValidationReport:
    ok: bool
    quality_score: float
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def validate_ohlcv(df: pd.DataFrame, timeframe_minutes: int | None = None) -> ValidationReport:
    issues: list[str] = []
    warnings: list[str] = []
    penalty = 0.0

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return ValidationReport(
            ok=False, quality_score=0.0, issues=[f"missing columns: {missing}"]
        )

    if len(df) == 0:
        return ValidationReport(ok=False, quality_score=0.0, issues=["empty dataframe"])

    # Negative / non-positive prices.
    neg = (df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()
    if neg:
        issues.append(f"{neg} candles with non-positive prices")
        penalty += 0.4

    # OHLC consistency: high >= max(open,close), low <= min(open,close).
    bad_high = (df["high"] < df[["open", "close"]].max(axis=1) - 1e-9).sum()
    bad_low = (df["low"] > df[["open", "close"]].min(axis=1) + 1e-9).sum()
    if bad_high or bad_low:
        issues.append(f"OHLC inconsistency: {bad_high} high, {bad_low} low violations")
        penalty += 0.3

    # Negative volume.
    if (df["volume"] < 0).any():
        issues.append("negative volume present")
        penalty += 0.2

    # Duplicate timestamps.
    dups = df.index.duplicated().sum()
    if dups:
        issues.append(f"{dups} duplicate timestamps")
        penalty += 0.2

    # Monotonic time index (lookahead / ordering protection).
    if not df.index.is_monotonic_increasing:
        issues.append("time index is not monotonically increasing")
        penalty += 0.3

    # Timestamp gaps.
    if isinstance(df.index, pd.DatetimeIndex) and len(df) > 2:
        deltas = df.index.to_series().diff().dropna()
        modal = deltas.mode()
        if len(modal):
            step = modal.iloc[0]
            gap_count = int((deltas > step * 1.5).sum())
            if gap_count:
                warnings.append(f"{gap_count} timestamp gaps detected")
                penalty += min(0.2, gap_count / len(df))

    # NaN / inf.
    n_nan = int(df[REQUIRED_COLUMNS].isna().sum().sum())
    if n_nan:
        issues.append(f"{n_nan} NaN values in OHLCV")
        penalty += 0.2
    if np.isinf(df[REQUIRED_COLUMNS].to_numpy()).any():
        issues.append("infinite values in OHLCV")
        penalty += 0.3

    quality = max(0.0, 1.0 - penalty)
    ok = len(issues) == 0
    stats = {
        "rows": int(len(df)),
        "start": str(df.index[0]),
        "end": str(df.index[-1]),
        "n_issues": len(issues),
        "n_warnings": len(warnings),
    }
    return ValidationReport(
        ok=ok, quality_score=quality, issues=issues, warnings=warnings, stats=stats
    )


def assert_no_lookahead(feature_fn, df: pd.DataFrame, col: str) -> bool:
    """Verify a feature at time t is unchanged by future data.

    Recomputes ``feature_fn`` on a truncated history and checks the value at the
    truncation point matches the full-history value. Returns True if no leakage.
    """
    full = feature_fn(df)
    cut = max(10, len(df) // 2)
    truncated = feature_fn(df.iloc[:cut])
    a = full[col].iloc[cut - 1]
    b = truncated[col].iloc[cut - 1]
    if pd.isna(a) and pd.isna(b):
        return True
    return bool(np.isclose(a, b, rtol=1e-9, atol=1e-9, equal_nan=True))
