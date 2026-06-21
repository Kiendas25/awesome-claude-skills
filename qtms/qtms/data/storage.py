"""Local-first storage: Parquet for candles, JSON for state/reports.

No database server. Everything lives under ``config.data_dir``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from ..app.config import get_config


def _root() -> Path:
    root = Path(get_config().data_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_")


def save_candles(symbol: str, df: pd.DataFrame) -> str:
    path = _root() / f"candles_{_safe(symbol)}.parquet"
    try:
        df.to_parquet(path)
    except Exception:  # pragma: no cover - fallback when pyarrow missing
        path = path.with_suffix(".csv")
        df.to_csv(path)
    return str(path)


def load_candles(symbol: str) -> pd.DataFrame | None:
    pq = _root() / f"candles_{_safe(symbol)}.parquet"
    csv = _root() / f"candles_{_safe(symbol)}.csv"
    if pq.exists():
        try:
            return pd.read_parquet(pq)
        except Exception:  # pragma: no cover
            pass
    if csv.exists():
        return pd.read_csv(csv, index_col=0, parse_dates=True)
    return None


def save_json(name: str, obj: Any) -> str:
    path = _root() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
    return str(path)


def load_json(name: str, default: Any = None) -> Any:
    path = _root() / name
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)
