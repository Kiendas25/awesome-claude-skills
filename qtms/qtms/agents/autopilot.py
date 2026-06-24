"""Research Autopilot (off-path, paper-only).

A background loop that autonomously cycles:

    refresh data -> discover & promote (judged on UNSEEN data) -> paper-trade a
    pass -> analyze -> write reports -> surface any promotion for MANUAL approval

Hard safety invariants:
* ``CAN_ENABLE_LIVE = False`` — it imports no live broker and cannot trade live.
* The global kill switch is checked every cycle; if active, the loop stops.
* Promotions are *surfaced*, never auto-applied — a human must approve.
* No LLM in the loop; everything is deterministic analytics.

One cycle is a single synchronous method (``run_one_cycle``) so it can be unit
tested without threads; the background thread just repeats it on an interval.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..app.config import QTMSConfig, get_config
from ..app.safety import KILL_SWITCH
from ..app.paper_engine import PaperTradingEngine
from ..data.market_data import MarketDataAdapter
from ..data.storage import save_json
from ..reports import obsidian_exporter as obs
from . import post_trade_analyzer
from .strategy_optimizer import discover_and_promote


@dataclass
class AutopilotState:
    running: bool = False
    cycle: int = 0
    symbol: str = "BTC/USDT"
    interval_seconds: float = 20.0
    last_summary: dict | None = None
    history: list[dict] = field(default_factory=list)
    pending_approvals: list[dict] = field(default_factory=list)
    approved: list[dict] = field(default_factory=list)
    last_error: str | None = None
    started_at: str | None = None


class Autopilot:
    CAN_ENABLE_LIVE = False  # asserted by tests; never trades live

    def __init__(self, cfg: QTMSConfig | None = None):
        self.cfg = cfg or get_config()
        self.state = AutopilotState()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # Autopilot params (set on start).
        self.n_candles = 1200
        self.drift = 0.0008
        self.seed_base = 1000
        self.paper_steps = 12
        self.mc_paths = 20
        self.warmup = 150
        # Symbol universe to rotate through (one symbol per cycle).
        self.symbols = ["BTC/USDT"]
        # Data source: "synthetic" or "live" (real public OHLCV).
        self.data_source = "synthetic"
        self.timeframe = "5m"
        self.source = "auto"        # exchange or 'auto' for live data
        self.limit = 1000

    # --- one cycle (synchronous, testable) --------------------------------
    def run_one_cycle(self) -> dict:
        if KILL_SWITCH.active:
            summary = {
                "cycle": self.state.cycle,
                "skipped": True,
                "reason": f"kill switch active: {KILL_SWITCH.reason}",
            }
            self._record(summary)
            return summary

        cfg = self.cfg
        cfg.monte_carlo.n_paths = self.mc_paths
        with self._lock:
            self.state.cycle += 1
            cycle = self.state.cycle
        seed = self.seed_base + cycle
        # Rotate through the symbol universe — one coin per cycle.
        universe = self.symbols or [self.state.symbol or "BTC/USDT"]
        symbol = universe[(cycle - 1) % len(universe)]

        df, data_used, data_note = self._get_data(symbol, seed)

        # 1) discover & promote (judged on unseen holdout)
        promo = discover_and_promote(df, cfg)

        # 2) paper-trade a short pass (virtual money only)
        eng = PaperTradingEngine(cfg, mc_paths=self.mc_paths)
        eng.start(df, warmup=min(self.warmup, len(df) // 3))
        eng.run(max_steps=self.paper_steps)
        eng.stop()
        paper = eng.status()

        # 3) quick analysis of any closed paper trades
        analysis = post_trade_analyzer.analyze_trades(eng.broker.closed_trades)

        summary = {
            "cycle": cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "seed": seed,
            "data_source": data_used,
            "data_note": data_note,
            "promoted": promo.promoted,
            "survivors": [s["name"] for s in promo.survivors],
            "weights": promo.weights,
            "holdout_metrics": promo.holdout_metrics,
            "promotion_reasons": promo.reasons,
            "paper_equity": paper.get("equity"),
            "paper_trades": paper.get("n_trades"),
            "trade_analysis": analysis.get("summary", {}),
            "can_enable_live": self.CAN_ENABLE_LIVE,
        }

        # 4) surface a promotion for MANUAL approval (never auto-applied)
        if promo.promoted:
            with self._lock:
                self.state.pending_approvals.append({
                    "cycle": cycle,
                    "symbol": symbol,
                    "timestamp": summary["timestamp"],
                    "survivors": summary["survivors"],
                    "weights": promo.weights,
                    "holdout_metrics": promo.holdout_metrics,
                    "approved": False,
                })
            self._write_note(symbol, summary, promoted=True)

        self._record(summary)
        save_json("agents/autopilot_latest.json", self._public_state())
        return summary

    def _get_data(self, symbol: str, seed: int):
        """Return (df, source_used, note). For live, fetch real OHLCV and fall
        back to synthetic on any network/error so the loop never dies."""
        cfg = self.cfg
        if self.data_source == "live":
            try:
                df = MarketDataAdapter(cfg).live(
                    symbol, timeframe=self.timeframe, limit=self.limit, source=self.source
                )
                return df, f"live:{df.attrs.get('source', self.source)}", "real market data"
            except Exception as e:
                note = f"live fetch failed ({type(e).__name__}: {str(e)[:80]}); used synthetic"
                with self._lock:
                    self.state.last_error = note
                df = MarketDataAdapter(cfg).synthetic(
                    symbol, n=self.n_candles, seed=seed, drift=self.drift
                )
                return df, "synthetic(fallback)", note
        df = MarketDataAdapter(cfg).synthetic(
            symbol, n=self.n_candles, seed=seed, drift=self.drift
        )
        return df, "synthetic", "synthetic data"

    # --- background loop ---------------------------------------------------
    def start(self, symbol: str | None = None, symbols: list[str] | None = None,
              interval_seconds: float = 20.0,
              drift: float = 0.0008, n_candles: int = 1200, paper_steps: int = 12,
              data_source: str = "synthetic", timeframe: str = "5m",
              source: str = "auto", limit: int = 1000) -> dict:
        if self.state.running:
            return {"running": True, "note": "autopilot already running"}
        # Resolve the symbol universe: explicit list > single symbol > config.
        universe = symbols or ([symbol] if symbol else list(self.cfg.symbols))
        self.symbols = universe
        label = universe[0] + (f" +{len(universe) - 1} more" if len(universe) > 1 else "")
        self.state = AutopilotState(
            running=True, symbol=label, interval_seconds=max(3.0, interval_seconds),
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.drift = drift
        self.n_candles = n_candles
        self.paper_steps = paper_steps
        self.data_source = data_source
        self.timeframe = timeframe
        self.source = source
        self.limit = limit
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return {"running": True, "symbol": symbol, "interval_seconds": self.state.interval_seconds}

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_one_cycle()
            except Exception as e:  # keep the loop alive; record the error
                with self._lock:
                    self.state.last_error = f"{type(e).__name__}: {e}"
            if KILL_SWITCH.active:
                with self._lock:
                    self.state.running = False
                break
            self._stop.wait(self.state.interval_seconds)

    def stop(self) -> dict:
        self._stop.set()
        with self._lock:
            self.state.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        return self.status()

    def approve_latest(self) -> dict:
        """Manually approve the most recent pending promotion. This records the
        operator's approval for paper use only — it does NOT enable live."""
        with self._lock:
            pending = [p for p in self.state.pending_approvals if not p["approved"]]
            if not pending:
                return {"approved": None, "note": "no pending promotions to approve"}
            latest = pending[-1]
            latest["approved"] = True
            latest["approved_at"] = datetime.now(timezone.utc).isoformat()
            self.state.approved.append(latest)
        save_json("agents/autopilot_latest.json", self._public_state())
        return {"approved": latest, "note": "approved for PAPER use only; live still disabled"}

    # --- helpers -----------------------------------------------------------
    def _record(self, summary: dict) -> None:
        with self._lock:
            self.state.last_summary = summary
            self.state.history.append(summary)
            self.state.history = self.state.history[-30:]

    def _write_note(self, symbol: str, summary: dict, promoted: bool) -> None:
        body = [
            f"## Autopilot cycle {summary['cycle']} — {symbol}\n",
            f"- **Promotion:** {'PROMOTED ✅ (awaiting manual approval)' if promoted else 'none'}",
            f"- survivors: {summary['survivors']}",
            f"- holdout metrics: {summary['holdout_metrics']}",
            f"- paper equity: {summary['paper_equity']}  trades: {summary['paper_trades']}\n",
            "> Autonomous RESEARCH only. Paper money. Live trading stays disabled. "
            "A promotion needs manual approval before it is used even on paper.",
        ]
        obs.write_note(f"Autopilot Cycle {summary['cycle']} {symbol}", "\n".join(body),
                       tags=["autopilot", "research", "qtms"], subfolder="autopilot")

    def _public_state(self) -> dict:
        with self._lock:
            s = self.state
            return {
                "running": s.running,
                "cycle": s.cycle,
                "symbol": s.symbol,
                "symbols": self.symbols,
                "last_symbol": (s.last_summary or {}).get("symbol"),
                "data_source": self.data_source,
                "timeframe": self.timeframe,
                "interval_seconds": s.interval_seconds,
                "started_at": s.started_at,
                "last_summary": s.last_summary,
                "pending_approvals": [p for p in s.pending_approvals if not p["approved"]],
                "n_approved": len(s.approved),
                "recent_cycles": s.history[-8:],
                "last_error": s.last_error,
                "can_enable_live": self.CAN_ENABLE_LIVE,
            }

    def status(self) -> dict:
        return self._public_state()


_AUTOPILOT: Autopilot | None = None


def get_autopilot() -> Autopilot:
    global _AUTOPILOT
    if _AUTOPILOT is None:
        _AUTOPILOT = Autopilot()
    return _AUTOPILOT
