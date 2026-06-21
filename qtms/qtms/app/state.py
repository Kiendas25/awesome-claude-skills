"""In-memory application state for the API (single-process, local-first)."""
from __future__ import annotations

import pandas as pd

from .config import get_config
from .paper_engine import PaperTradingEngine


class AppState:
    def __init__(self):
        self.cfg = get_config()
        self.data: dict[str, pd.DataFrame] = {}
        self.engine: PaperTradingEngine | None = None

    def set_data(self, symbol: str, df: pd.DataFrame) -> None:
        df.attrs["symbol"] = symbol
        self.data[symbol] = df

    def get_data(self, symbol: str) -> pd.DataFrame | None:
        return self.data.get(symbol)

    def get_or_make(self, symbol: str) -> pd.DataFrame:
        """Return cached data for ``symbol`` or generate synthetic data."""
        from ..data.market_data import MarketDataAdapter

        df = self.data.get(symbol)
        if df is None:
            df = MarketDataAdapter(self.cfg).synthetic(symbol)
            self.set_data(symbol, df)
        return df


STATE = AppState()
