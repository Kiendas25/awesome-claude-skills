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

from ..app.config import QTMSConfig, get_config, set_config
from ..app.safety import KILL_SWITCH
from ..app.paper_engine import PaperTradingEngine
from ..data.market_data import MarketDataAdapter
from ..data.storage import load_json, save_json
from ..reports import obsidian_exporter as obs
from . import post_trade_analyzer
from .strategy_optimizer import discover_and_promote


def _acquire_data(cfg: QTMSConfig, symbol: str, seed: int, data_source: str,
                  n_candles: int, drift: float, timeframe: str, source: str, limit: int):
    """Return (df, source_used, note). Live falls back to synthetic on error."""
    if data_source == "live":
        try:
            df = MarketDataAdapter(cfg).live(symbol, timeframe=timeframe, limit=limit, source=source)
            return df, f"live:{df.attrs.get('source', source)}", "real market data"
        except Exception as e:
            df = MarketDataAdapter(cfg).synthetic(symbol, n=n_candles, seed=seed, drift=drift)
            return df, "synthetic(fallback)", (
                f"live fetch failed ({type(e).__name__}: {str(e)[:80]}); used synthetic")
    df = MarketDataAdapter(cfg).synthetic(symbol, n=n_candles, seed=seed, drift=drift)
    return df, "synthetic", "synthetic data"


def compute_symbol(payload: dict) -> dict:
    """Pure, picklable unit of work for one symbol (runs in a worker process).

    Does data -> discover -> paper -> analyze and returns a plain summary dict.
    No shared state, no disk writes — the parent process merges the results.
    """
    cfg = payload["cfg"]
    if not isinstance(cfg, QTMSConfig):
        cfg = QTMSConfig(**cfg)
    set_config(cfg)
    cfg.monte_carlo.n_paths = payload["mc_paths"]
    symbol, seed, cycle = payload["symbol"], payload["seed"], payload["cycle"]

    df, data_used, data_note = _acquire_data(
        cfg, symbol, seed, payload["data_source"], payload["n_candles"],
        payload["drift"], payload["timeframe"], payload["source"], payload["limit"])

    promo = discover_and_promote(df, cfg)

    eng = PaperTradingEngine(cfg, mc_paths=payload["mc_paths"])
    eng.start(df, warmup=min(payload["warmup"], len(df) // 3))
    eng.run(max_steps=payload["paper_steps"])
    eng.stop()
    paper = eng.status()
    analysis = post_trade_analyzer.analyze_trades(eng.broker.closed_trades)

    from datetime import datetime, timezone
    return {
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
        "can_enable_live": False,
    }


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
    scoreboard: dict = field(default_factory=dict)  # per-symbol stats over time
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
        # Performance: scan the whole universe each round, in parallel threads.
        self.scan_all = True
        self.parallel = True
        self.max_workers = 4

    def _payload(self, symbol: str, seed: int, cycle: int) -> dict:
        return {
            "cfg": self.cfg, "symbol": symbol, "seed": seed, "cycle": cycle,
            "mc_paths": self.mc_paths, "n_candles": self.n_candles, "drift": self.drift,
            "paper_steps": self.paper_steps, "warmup": self.warmup,
            "data_source": self.data_source, "timeframe": self.timeframe,
            "source": self.source, "limit": self.limit,
        }

    def _merge(self, summary: dict) -> dict:
        """Apply a worker's result to shared state (scoreboard, pending, notes)."""
        symbol = summary["symbol"]
        if "failed" in (summary.get("data_note") or ""):
            with self._lock:
                self.state.last_error = summary["data_note"]
        self._update_scoreboard(symbol, summary["promoted"],
                                summary["holdout_metrics"], summary["survivors"])
        if summary["promoted"]:
            with self._lock:
                self.state.pending_approvals.append({
                    "cycle": summary["cycle"], "symbol": symbol,
                    "timestamp": summary["timestamp"], "survivors": summary["survivors"],
                    "weights": summary["weights"], "holdout_metrics": summary["holdout_metrics"],
                    "approved": False,
                })
            self._write_note(symbol, summary, promoted=True)
        return summary

    # --- per-symbol work (sequential unit) --------------------------------
    def _process_symbol(self, symbol: str, seed: int, cycle: int) -> dict:
        return self._merge(compute_symbol(self._payload(symbol, seed, cycle)))

    def _skip_if_killed(self) -> dict | None:
        if KILL_SWITCH.active:
            s = {"cycle": self.state.cycle, "skipped": True,
                 "reason": f"kill switch active: {KILL_SWITCH.reason}"}
            self._record(s)
            return s
        return None

    # --- one cycle: process ONE rotating symbol (synchronous, testable) ---
    def run_one_cycle(self) -> dict:
        skipped = self._skip_if_killed()
        if skipped:
            return skipped
        self.cfg.monte_carlo.n_paths = self.mc_paths
        with self._lock:
            self.state.cycle += 1
            cycle = self.state.cycle
        universe = self.symbols or [self.state.symbol or "BTC/USDT"]
        symbol = universe[(cycle - 1) % len(universe)]
        summary = self._process_symbol(symbol, self.seed_base + cycle, cycle)
        self._record(summary)
        save_json("agents/autopilot_latest.json", self._public_state())
        return summary

    # --- one round: scan the WHOLE universe (optionally in parallel) -------
    def run_one_round(self) -> dict:
        skipped = self._skip_if_killed()
        if skipped:
            return skipped
        self.cfg.monte_carlo.n_paths = self.mc_paths
        with self._lock:
            self.state.cycle += 1
            rnd = self.state.cycle
        universe = self.symbols or [self.state.symbol or "BTC/USDT"]
        payloads = [self._payload(s, self.seed_base + rnd * 100 + i, rnd)
                    for i, s in enumerate(universe)]

        results = None
        if self.parallel and len(payloads) > 1:
            # Real multi-core parallelism needs PROCESSES (numpy/pandas hold the
            # GIL). Compute in workers, then merge results in this process. Any
            # failure (pickling, spawn restrictions) falls back to sequential.
            try:
                from concurrent.futures import ProcessPoolExecutor
                computed = []
                with ProcessPoolExecutor(max_workers=self.max_workers) as ex:
                    computed = list(ex.map(compute_symbol, payloads))
                results = [self._merge(s) for s in computed]
            except Exception as e:
                with self._lock:
                    self.state.last_error = f"parallel fell back to sequential: {type(e).__name__}"
                results = None
        if results is None:
            results = [self._merge(compute_symbol(p)) for p in payloads]

        n_promoted = sum(1 for r in results if r["promoted"])
        promoted_syms = [r["symbol"] for r in results if r["promoted"]]
        equities = [r["paper_equity"] for r in results if r.get("paper_equity") is not None]
        round_summary = {
            "round": rnd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": f"round {rnd}: scanned {len(universe)} coins",
            "scanned": len(universe),
            "n_promoted": n_promoted,
            "promoted_symbols": promoted_syms,
            "promoted": n_promoted > 0,
            "paper_equity": (sum(equities) / len(equities)) if equities else None,
            "per_symbol": [{"symbol": r["symbol"], "promoted": r["promoted"]} for r in results],
            "can_enable_live": self.CAN_ENABLE_LIVE,
        }
        self._record(round_summary)
        save_json("agents/autopilot_latest.json", self._public_state())
        return round_summary

    def _get_data(self, symbol: str, seed: int):
        """Return (df, source_used, note); records last_error on live fallback."""
        df, used, note = _acquire_data(
            self.cfg, symbol, seed, self.data_source, self.n_candles, self.drift,
            self.timeframe, self.source, self.limit)
        if "failed" in note:
            with self._lock:
                self.state.last_error = note
        return df, used, note

    # --- background loop ---------------------------------------------------
    def start(self, symbol: str | None = None, symbols: list[str] | None = None,
              interval_seconds: float = 20.0,
              drift: float = 0.0008, n_candles: int = 1200, paper_steps: int = 12,
              data_source: str = "synthetic", timeframe: str = "5m",
              source: str = "auto", limit: int = 1000,
              scan_all: bool = True, parallel: bool = True, max_workers: int = 4) -> dict:
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
        self.scan_all = scan_all
        self.parallel = parallel
        self.max_workers = max_workers
        # Carry the per-coin leaderboard over from previous runs.
        self._load_persisted()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return {"running": True, "symbol": symbol, "interval_seconds": self.state.interval_seconds}

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_one_round() if self.scan_all else self.run_one_cycle()
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
        self._persist()
        save_json("agents/autopilot_latest.json", self._public_state())
        return {"approved": latest, "note": "approved for PAPER use only; live still disabled"}

    # --- helpers -----------------------------------------------------------
    def _update_scoreboard(self, symbol: str, promoted: bool,
                           holdout_metrics: dict, survivor_names: list) -> None:
        with self._lock:
            sb = self.state.scoreboard.setdefault(
                symbol, {"cycles": 0, "promotions": 0, "best_return": 0.0, "strategies": {}}
            )
            sb["cycles"] += 1
            if promoted:
                sb["promotions"] += 1
                r = float((holdout_metrics or {}).get("total_return", 0.0) or 0.0)
                sb["best_return"] = max(sb["best_return"], r)
                for name in survivor_names:
                    sb["strategies"][name] = sb["strategies"].get(name, 0) + 1
        self._persist()

    # --- persistence: leaderboard survives restarts ------------------------
    _STATE_FILE = "agents/autopilot_state.json"

    def _persist(self) -> None:
        with self._lock:
            save_json(self._STATE_FILE, {
                "scoreboard": self.state.scoreboard,
                "approved": self.state.approved,
            })

    def _load_persisted(self) -> None:
        saved = load_json(self._STATE_FILE, default={}) or {}
        with self._lock:
            self.state.scoreboard = saved.get("scoreboard", {})
            self.state.approved = saved.get("approved", [])

    def reset_leaderboard(self) -> dict:
        with self._lock:
            self.state.scoreboard = {}
            self.state.approved = []
        self._persist()
        return {"reset": True}

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
                "leaderboard": sorted(
                    [{"symbol": k, **v} for k, v in s.scoreboard.items()],
                    key=lambda x: (x["promotions"], x["best_return"]),
                    reverse=True,
                ),
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
