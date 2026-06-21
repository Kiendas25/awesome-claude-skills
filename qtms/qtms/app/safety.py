"""Safety subsystem: kill switch and the multi-gate live trading approval.

Design rule: live trading is *impossible* unless EVERY independent gate is
satisfied. The gates are deliberately redundant (env vars + approval phrase +
validation + paper sample + risk thresholds + kill switch). Any single failure
keeps the system in paper/research mode.

Nothing here promises profit; the gates only verify that an edge has been
demonstrated to a minimal bar and that the operator explicitly consented.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import QTMSConfig, get_config


@dataclass
class KillSwitch:
    """Global override. When active, NO order (paper or live) may be placed."""

    active: bool = False
    reason: str = ""
    triggered_at: datetime | None = None

    def trip(self, reason: str) -> None:
        self.active = True
        self.reason = reason
        self.triggered_at = datetime.now(timezone.utc)

    def reset(self) -> None:
        self.active = False
        self.reason = ""
        self.triggered_at = None


# Module-level singleton kill switch — checked everywhere orders are routed.
KILL_SWITCH = KillSwitch()


@dataclass
class SafetyViolation:
    code: str
    message: str
    severity: str = "warning"  # warning | critical


@dataclass
class LiveGateInputs:
    """Everything the live gate needs to make a decision. Populated by callers
    from validation reports and paper-trading stats — never fabricated."""

    validation_passed: bool = False
    paper_trade_count: int = 0
    observed_max_drawdown: float = 1.0
    observed_risk_of_ruin: float = 1.0
    broker_configured: bool = False
    open_safety_violations: list[SafetyViolation] = field(default_factory=list)


def approval_phrase(cfg: QTMSConfig | None = None) -> str:
    """Deterministic approval phrase the operator must echo back via env var.

    Derived from the config seed and symbols so it is stable per-config but not
    guessable without the running config. This is a *consent* mechanism, not a
    security boundary.
    """
    cfg = cfg or get_config()
    raw = f"QTMS-LIVE-APPROVAL::{cfg.seed}::{','.join(sorted(cfg.symbols))}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"I-APPROVE-LIVE-{digest}"


@dataclass
class LiveGateDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)


def evaluate_live_gate(
    inputs: LiveGateInputs, cfg: QTMSConfig | None = None
) -> LiveGateDecision:
    """Return whether a live order may be sent. Default outcome is *blocked*."""
    cfg = cfg or get_config()
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    # Gate 1: config flag
    checks["config_live_enabled"] = bool(cfg.live.live_trading_enabled)
    # Gate 2: explicit env opt-in
    checks["env_enable_live"] = os.environ.get("QTMS_ENABLE_LIVE") == "true"
    # Gate 3: manual approval phrase must match exactly
    expected = approval_phrase(cfg)
    checks["manual_approval_phrase"] = (
        os.environ.get("QTMS_MANUAL_LIVE_APPROVAL") == expected
    )
    # Gate 4: validation report passed
    checks["validation_passed"] = (
        inputs.validation_passed or not cfg.live.require_validation_pass
    )
    # Gate 5: minimum paper-trading sample
    checks["paper_sample_size"] = (
        inputs.paper_trade_count >= cfg.live.min_paper_trades
    )
    # Gate 6: drawdown within tolerance
    checks["drawdown_ok"] = (
        inputs.observed_max_drawdown <= cfg.risk.max_drawdown_pct
    )
    # Gate 7: risk of ruin within tolerance
    checks["risk_of_ruin_ok"] = (
        inputs.observed_risk_of_ruin <= cfg.risk.max_risk_of_ruin
    )
    # Gate 8: no open critical safety violations
    checks["no_critical_violations"] = not any(
        v.severity == "critical" for v in inputs.open_safety_violations
    )
    # Gate 9: kill switch must be inactive
    checks["kill_switch_inactive"] = not KILL_SWITCH.active
    # Gate 10: a broker adapter must be explicitly configured
    checks["broker_configured"] = bool(inputs.broker_configured)

    for name, ok in checks.items():
        if not ok:
            reasons.append(f"BLOCKED: gate '{name}' not satisfied")

    allowed = all(checks.values())
    if not allowed and not reasons:  # pragma: no cover - defensive
        reasons.append("BLOCKED: unknown gate failure")
    return LiveGateDecision(allowed=allowed, reasons=reasons, checks=checks)


def assert_can_trade(live: bool, inputs: LiveGateInputs | None = None) -> None:
    """Raise if an order is not permitted. Paper orders only require that the
    kill switch is inactive; live orders require the full gate."""
    if KILL_SWITCH.active:
        raise PermissionError(f"Kill switch active: {KILL_SWITCH.reason}")
    if not live:
        return
    decision = evaluate_live_gate(inputs or LiveGateInputs())
    if not decision.allowed:
        raise PermissionError("Live trading blocked: " + "; ".join(decision.reasons))
