"""Drawdown guard: tracks equity peak and daily loss, trips the kill switch.

This is the automated circuit breaker. When max drawdown or daily-loss limits
are breached it trips the global kill switch, which overrides everything.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..app.config import QTMSConfig, get_config
from ..app.safety import KILL_SWITCH


@dataclass
class DrawdownGuard:
    cfg: QTMSConfig = field(default_factory=get_config)
    peak_equity: float = 0.0
    day_start_equity: float = 0.0
    current_day: str | None = None
    halted_for_day: bool = False

    def init(self, equity: float, day: str) -> None:
        self.peak_equity = equity
        self.day_start_equity = equity
        self.current_day = day
        self.halted_for_day = False

    def update(self, equity: float, day: str) -> dict:
        if self.current_day != day:
            # New trading day: reset daily loss tracking.
            self.current_day = day
            self.day_start_equity = equity
            self.halted_for_day = False
        self.peak_equity = max(self.peak_equity, equity)

        drawdown = (
            (self.peak_equity - equity) / self.peak_equity
            if self.peak_equity > 0
            else 0.0
        )
        daily_loss = (
            (self.day_start_equity - equity) / self.day_start_equity
            if self.day_start_equity > 0
            else 0.0
        )

        status = {
            "drawdown": drawdown,
            "daily_loss": daily_loss,
            "halted_for_day": self.halted_for_day,
            "kill_switch": KILL_SWITCH.active,
        }

        if drawdown >= self.cfg.risk.max_drawdown_pct:
            KILL_SWITCH.trip(
                f"max drawdown breached: {drawdown:.3f} >= {self.cfg.risk.max_drawdown_pct}"
            )
            status["kill_switch"] = True
        if daily_loss >= self.cfg.risk.max_daily_loss_pct:
            self.halted_for_day = True
            status["halted_for_day"] = True
        return status

    def can_open_new(self) -> bool:
        return not KILL_SWITCH.active and not self.halted_for_day
