"""Paper trading engine — wires data → stack → risk → router, bar by bar.

This is the orchestrator that turns stack decisions into simulated trades while
enforcing risk limits, stops/takes, daily-loss halts and the kill switch. It
never touches real money and never calls a live broker.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..app.config import QTMSConfig, get_config
from ..app.schemas import Signal
from ..execution.order_router import OrderRouter
from ..execution.paper_broker import PaperBroker
from ..features.pipeline import compute_features
from ..risk.drawdown_guard import DrawdownGuard
from ..risk.exposure import check_exposure
from ..risk.stop_loss_take_profit import check_exit, compute_levels
from ..stacking.signal_stack import SignalStack


@dataclass
class PaperEngineState:
    symbol: str
    idx: int
    running: bool = False
    decisions: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)


class PaperTradingEngine:
    def __init__(self, cfg: QTMSConfig | None = None, mc_paths: int = 40):
        self.cfg = cfg or get_config()
        # Use a lighter Monte Carlo budget while stepping for responsiveness.
        self.cfg.monte_carlo.n_paths = mc_paths
        self.broker = PaperBroker(self.cfg)
        self.router = OrderRouter(self.broker)
        self.guard = DrawdownGuard(self.cfg)
        self.stack = SignalStack(self.cfg)
        self.df: pd.DataFrame | None = None
        self.features: pd.DataFrame | None = None
        self.state: PaperEngineState | None = None

    def start(self, df: pd.DataFrame, warmup: int = 150) -> dict:
        self.df = df
        self.features = compute_features(df)
        symbol = str(df.attrs.get("symbol", "UNKNOWN"))
        self.state = PaperEngineState(symbol=symbol, idx=min(warmup, len(df) - 1))
        self.state.running = True
        self.guard.init(self.broker.starting_balance, self._day(self.state.idx))
        return {"symbol": symbol, "start_idx": self.state.idx, "n_candles": len(df)}

    def _day(self, idx: int) -> str:
        return str(self.df.index[idx].date()) if self.df is not None else "0"

    def step(self) -> dict:
        if not self.state or not self.state.running or self.df is None:
            return {"done": True, "reason": "not running"}
        idx = self.state.idx
        if idx >= len(self.df) - 1:
            self.state.running = False
            return {"done": True, "reason": "end of data"}

        bar = self.df.iloc[idx]
        price = float(bar["close"])
        symbol = self.state.symbol
        marks = {symbol: price}
        self.broker.mark(marks)

        events: list[str] = []

        # 1) manage open position: stop/take exits.
        pos = self.broker.positions.get(symbol)
        if pos is not None:
            reason = check_exit(pos.direction, price, pos.stop_loss or 0.0, pos.take_profit or 1e18)
            if reason:
                self.router.route_close(symbol, price, exit_reason=[reason], seed=self.cfg.seed)
                events.append(f"exit:{reason}")

        # 2) drawdown / daily-loss guard.
        equity = self.broker.equity(marks)
        guard_status = self.guard.update(equity, self._day(idx))
        self.state.equity_curve.append({"idx": idx, "equity": equity})

        # 3) consider a new entry (only if flat in this symbol and allowed).
        decision_dict = None
        if symbol not in self.broker.positions and self.guard.can_open_new():
            slice_df = self.df.iloc[: idx + 1]
            slice_df.attrs["symbol"] = symbol
            decision = self.stack.decide(
                slice_df, equity=equity, seed=self.cfg.seed
            )
            decision_dict = decision.model_dump()
            self.state.decisions.append(decision_dict)
            if decision.approved and decision.final_signal != Signal.FLAT and decision.position_size > 0:
                exposure = check_exposure(
                    equity, self.broker.open_notional(), symbol,
                    decision.position_size * price, cfg=self.cfg,
                )
                if exposure["allowed"]:
                    atr = float(self.features["atr"].iloc[idx]) if "atr" in self.features else price * 0.01
                    levels = compute_levels(price, decision.final_signal, atr)
                    self.router.route_open(
                        symbol,
                        decision.final_signal,
                        decision.position_size,
                        price,
                        live=False,
                        stop_loss=levels["stop_loss"],
                        take_profit=levels["take_profit"],
                        seed=self.cfg.seed,
                        entry_reason=[f"conviction={decision.conviction:.2f}"],
                        strategy_weights=decision.strategy_weights,
                        signal_snapshot={"combined_signal": decision.explanation.get("combined_signal")},
                        monte_carlo_summary=decision.explanation.get("stacking_monte_carlo", {}),
                        risk_state=guard_status,
                    )
                    events.append(f"enter:{decision.final_signal.value}")
                else:
                    events.append("entry_blocked:exposure")

        self.state.idx += 1
        return {
            "done": False,
            "idx": idx,
            "price": price,
            "equity": equity,
            "events": events,
            "guard": guard_status,
            "approved": decision_dict["approved"] if decision_dict else None,
            "conviction": decision_dict["conviction"] if decision_dict else None,
        }

    def run(self, max_steps: int = 50) -> dict:
        results = []
        for _ in range(max_steps):
            r = self.step()
            results.append(r)
            if r.get("done"):
                break
        return {"steps": len(results), "last": results[-1] if results else None}

    def stop(self) -> dict:
        if self.state and self.df is not None and self.state.symbol in self.broker.positions:
            price = float(self.df.iloc[self.state.idx]["close"])
            self.router.route_close(self.state.symbol, price, exit_reason=["engine_stop"], seed=self.cfg.seed)
        if self.state:
            self.state.running = False
        return self.status()

    def status(self) -> dict:
        marks = {}
        if self.df is not None and self.state is not None:
            marks = {self.state.symbol: float(self.df.iloc[self.state.idx]["close"])}
        snap = self.broker.snapshot(marks)
        return {
            "running": self.state.running if self.state else False,
            "idx": self.state.idx if self.state else None,
            "n_decisions": len(self.state.decisions) if self.state else 0,
            "n_trades": len(self.broker.closed_trades),
            **snap,
        }
