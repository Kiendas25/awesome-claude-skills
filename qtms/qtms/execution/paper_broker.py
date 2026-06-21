"""Paper broker: virtual account, positions, and a full trade journal.

No real money, ever. Uses a clean PnL-accounting model:

* ``cash`` holds realized equity. Opening a position only pays the entry fee;
  the notional is NOT deducted (positions are tracked separately).
* ``equity(marks)`` = cash + unrealized PnL of open positions.
* Closing realizes ``(exit - entry) * qty * sign - exit_fee`` into cash.

Every closed trade produces a complete ``TradeRecord``.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from ..app.config import QTMSConfig, get_config
from ..app.schemas import Signal, TradeRecord
from .simulator import simulate_fill


def _signed_pnl(direction: Signal, entry: float, exit_: float, qty: float) -> float:
    gross = (exit_ - entry) * qty
    return -gross if direction == Signal.SHORT else gross


@dataclass
class OpenPosition:
    trade_id: str
    symbol: str
    direction: Signal
    qty: float
    entry_price: float
    entry_time: datetime
    stop_loss: float | None
    take_profit: float | None
    entry_fee: float
    entry_slippage: float
    entry_reason: list[str]
    strategy_weights: dict[str, float]
    signal_snapshot: dict
    monte_carlo_summary: dict
    risk_state: dict
    mae: float = 0.0  # max adverse excursion (fraction, <= 0)
    mfe: float = 0.0  # max favorable excursion (fraction, >= 0)

    def update_excursions(self, price: float) -> None:
        move = (price - self.entry_price) / self.entry_price
        if self.direction == Signal.SHORT:
            move = -move
        self.mfe = max(self.mfe, move)
        self.mae = min(self.mae, move)

    def unrealized(self, price: float) -> float:
        return _signed_pnl(self.direction, self.entry_price, price, self.qty)


class PaperBroker:
    def __init__(self, cfg: QTMSConfig | None = None):
        self.cfg = cfg or get_config()
        self.cash = self.cfg.risk.starting_balance
        self.starting_balance = self.cfg.risk.starting_balance
        self.positions: dict[str, OpenPosition] = {}
        self.closed_trades: list[TradeRecord] = []

    def open_notional(self) -> dict[str, float]:
        return {s: p.qty * p.entry_price for s, p in self.positions.items()}

    def equity(self, marks: dict[str, float]) -> float:
        eq = self.cash
        for s, p in self.positions.items():
            eq += p.unrealized(marks.get(s, p.entry_price))
        return eq

    def open(
        self,
        symbol: str,
        direction: Signal,
        qty: float,
        ref_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        volatility_pct: float = 0.0,
        seed: int | None = None,
        entry_reason: list[str] | None = None,
        strategy_weights: dict | None = None,
        signal_snapshot: dict | None = None,
        monte_carlo_summary: dict | None = None,
        risk_state: dict | None = None,
        timestamp: datetime | None = None,
    ) -> OpenPosition:
        fill = simulate_fill(
            symbol, direction, qty, ref_price, volatility_pct, seed=seed, cfg=self.cfg
        )
        self.cash -= fill["fee"]  # pay entry fee only
        pos = OpenPosition(
            trade_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            direction=direction,
            qty=qty,
            entry_price=fill["fill_price"],
            entry_time=timestamp or datetime.utcnow(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_fee=fill["fee"],
            entry_slippage=fill["slippage_cost"],
            entry_reason=entry_reason or [],
            strategy_weights=strategy_weights or {},
            signal_snapshot=signal_snapshot or {},
            monte_carlo_summary=monte_carlo_summary or {},
            risk_state=risk_state or {},
        )
        self.positions[symbol] = pos
        return pos

    def close(
        self,
        symbol: str,
        ref_price: float,
        exit_reason: list[str] | None = None,
        seed: int | None = None,
        timestamp: datetime | None = None,
    ) -> TradeRecord | None:
        pos = self.positions.pop(symbol, None)
        if pos is None:
            return None
        close_dir = Signal.SHORT if pos.direction == Signal.LONG else Signal.LONG
        fill = simulate_fill(symbol, close_dir, pos.qty, ref_price, seed=seed, cfg=self.cfg)

        gross = _signed_pnl(pos.direction, pos.entry_price, fill["fill_price"], pos.qty)
        self.cash += gross - fill["fee"]  # realize pnl minus exit fee

        total_fees = pos.entry_fee + fill["fee"]
        total_slip = pos.entry_slippage + fill["slippage_cost"]
        pnl = gross - total_fees
        pnl_pct = pnl / (pos.entry_price * pos.qty) if pos.qty else 0.0

        record = TradeRecord(
            trade_id=pos.trade_id,
            symbol=symbol,
            direction=pos.direction,
            qty=pos.qty,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=timestamp or datetime.utcnow(),
            exit_price=fill["fill_price"],
            fees=total_fees,
            slippage=total_slip,
            pnl=pnl,
            pnl_pct=pnl_pct,
            max_adverse_excursion=pos.mae,
            max_favorable_excursion=pos.mfe,
            entry_reason=pos.entry_reason,
            exit_reason=exit_reason or [],
            strategy_weights=pos.strategy_weights,
            signal_snapshot=pos.signal_snapshot,
            monte_carlo_summary=pos.monte_carlo_summary,
            risk_state=pos.risk_state,
        )
        self.closed_trades.append(record)
        return record

    def mark(self, marks: dict[str, float]) -> None:
        for s, p in self.positions.items():
            if s in marks:
                p.update_excursions(marks[s])

    def snapshot(self, marks: dict[str, float] | None = None) -> dict:
        marks = marks or {}
        return {
            "cash": self.cash,
            "equity": self.equity(marks),
            "starting_balance": self.starting_balance,
            "open_positions": {
                s: {
                    "direction": p.direction.value,
                    "qty": p.qty,
                    "entry_price": p.entry_price,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "mae": p.mae,
                    "mfe": p.mfe,
                }
                for s, p in self.positions.items()
            },
            "n_closed": len(self.closed_trades),
        }
