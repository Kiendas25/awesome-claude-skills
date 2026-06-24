"""Daily auto-curation scheduler (off-path, paper-only).

Runs the paper-test campaign automatically (default once per day) on live data,
appends each day's KEEP/IMPROVE/ERASE verdicts to a persistent history, and
computes a CONSENSUS verdict per strategy across many days. A strategy is only
flagged for removal when it is *consistently* ERASE over multiple days — so a
single unlucky day never erases anything. This is self-curation with the same
anti-overfitting discipline as the rest of QTMS.

It never trades real money and never enables live trading. Applying the
consensus to the active strategy set is a separate, operator-initiated action.
"""
from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..app.config import QTMSConfig, get_config
from ..app.safety import KILL_SWITCH
from ..data.storage import load_json, save_json
from .campaign import run_campaign

HISTORY_FILE = "agents/campaign_history.json"
MIN_RUNS_FOR_CONSENSUS = 3
ERASE_FRACTION = 0.80     # must be ERASE on >=80% of days to reach ERASE consensus
MIN_ACTIVE_AFTER_APPLY = 4


def compute_consensus(history: list[dict]) -> dict:
    counts: dict[str, Counter] = {}
    for run in history:
        for strat, verdict in (run.get("verdicts") or {}).items():
            counts.setdefault(strat, Counter())[verdict] += 1
    consensus = {}
    for strat, c in counts.items():
        total = sum(c.values())
        erase_frac = c["ERASE"] / total if total else 0.0
        keep_frac = c["KEEP"] / total if total else 0.0
        if total >= MIN_RUNS_FOR_CONSENSUS and erase_frac >= ERASE_FRACTION:
            verdict = "ERASE"
        elif keep_frac >= 0.5:
            verdict = "KEEP"
        else:
            verdict = "IMPROVE"
        consensus[strat] = {
            "verdict": verdict,
            "runs": total,
            "keep": c["KEEP"], "improve": c["IMPROVE"], "erase": c["ERASE"],
            "stability": round(max(c.values()) / total, 2) if total else 0.0,
        }
    return consensus


@dataclass
class SchedulerState:
    running: bool = False
    interval_hours: float = 24.0
    data_source: str = "live"
    days: int = 1
    n_candles: int = 1000
    last_run: str | None = None
    next_due: str | None = None
    n_runs: int = 0
    last_error: str | None = None


class DailyCampaignScheduler:
    CAN_ENABLE_LIVE = False

    def __init__(self, cfg: QTMSConfig | None = None):
        self.cfg = cfg or get_config()
        self.state = SchedulerState()
        self.history: list[dict] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # --- one campaign run (synchronous, testable) -------------------------
    def run_now(self) -> dict:
        if KILL_SWITCH.active:
            return {"skipped": True, "reason": f"kill switch active: {KILL_SWITCH.reason}"}
        self._load_history()
        report = run_campaign(
            days=self.state.days, cfg=self.cfg,
            data_source=self.state.data_source, n_candles=self.state.n_candles,
        )
        verdicts = {s["strategy"]: s["verdict"] for s in report["strategy_scorecards"]}
        entry = {
            "date": datetime.now(timezone.utc).isoformat(),
            "data_source": report["data_source"],
            "promotion_rate": report["promotion_rate"],
            "verdicts": verdicts,
        }
        with self._lock:
            self.history.append(entry)
            self.history = self.history[-90:]  # keep ~3 months of daily runs
            self.state.last_run = entry["date"]
            self.state.n_runs += 1
        self._persist()
        return {"ran": True, "verdicts": verdicts, "consensus": self.consensus()}

    def consensus(self) -> dict:
        return compute_consensus(self.history)

    # --- background scheduling --------------------------------------------
    def start(self, interval_hours: float = 24.0, data_source: str = "live",
              days: int = 1, n_candles: int = 1000) -> dict:
        if self.state.running:
            return {"running": True, "note": "scheduler already running"}
        self._load_history()
        self.state = SchedulerState(
            running=True, interval_hours=max(0.001, interval_hours),
            data_source=data_source, days=days, n_candles=n_candles,
            last_run=self.state.last_run, n_runs=self.state.n_runs,
        )
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return {"running": True, "interval_hours": self.state.interval_hours,
                "data_source": data_source}

    def _due(self) -> bool:
        if not self.state.last_run:
            return True
        last = datetime.fromisoformat(self.state.last_run)
        elapsed_h = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
        return elapsed_h >= self.state.interval_hours

    def _loop(self) -> None:
        # Re-check periodically so an always-off laptop still runs ~daily when on.
        check_seconds = max(60.0, min(self.state.interval_hours * 3600.0, 1800.0))
        while not self._stop.is_set():
            try:
                if self._due() and not KILL_SWITCH.active:
                    self.run_now()
            except Exception as e:
                with self._lock:
                    self.state.last_error = f"{type(e).__name__}: {e}"
            self._stop.wait(check_seconds)

    def stop(self) -> dict:
        self._stop.set()
        with self._lock:
            self.state.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        return self.status()

    # --- apply consensus (operator-initiated; paper config only) ----------
    def apply_consensus(self) -> dict:
        cons = self.consensus()
        erase = [s for s, v in cons.items() if v["verdict"] == "ERASE"]
        current = list(self.cfg.active_strategies)
        remaining = [s for s in current if s not in erase]
        if len(remaining) < MIN_ACTIVE_AFTER_APPLY:
            return {"applied": False, "reason": "would leave too few active strategies",
                    "would_erase": erase, "active": current}
        self.cfg.active_strategies = remaining
        return {"applied": True, "erased": erase, "active_now": remaining,
                "note": "Applied to PAPER research config only. Live trading still disabled."}

    # --- persistence + status ---------------------------------------------
    def _persist(self) -> None:
        with self._lock:
            save_json(HISTORY_FILE, {"history": self.history, "n_runs": self.state.n_runs,
                                     "last_run": self.state.last_run})

    def _load_history(self) -> None:
        data = load_json(HISTORY_FILE, default={}) or {}
        with self._lock:
            self.history = data.get("history", [])
            if data.get("last_run") and not self.state.last_run:
                self.state.last_run = data["last_run"]
            self.state.n_runs = max(self.state.n_runs, data.get("n_runs", 0))

    def status(self) -> dict:
        with self._lock:
            s = self.state
            next_due = None
            if s.last_run:
                last = datetime.fromisoformat(s.last_run)
                from datetime import timedelta
                next_due = (last + timedelta(hours=s.interval_hours)).isoformat()
            return {
                "running": s.running,
                "interval_hours": s.interval_hours,
                "data_source": s.data_source,
                "days_per_run": s.days,
                "last_run": s.last_run,
                "next_due": next_due,
                "n_runs": s.n_runs,
                "consensus": compute_consensus(self.history),
                "history_len": len(self.history),
                "last_error": s.last_error,
                "can_enable_live": self.CAN_ENABLE_LIVE,
            }


_SCHEDULER: DailyCampaignScheduler | None = None


def get_scheduler() -> DailyCampaignScheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = DailyCampaignScheduler()
    return _SCHEDULER
