"""Live data fetch: parsing, fallback chain, and autopilot resilience.

These tests NEVER hit the network — the single HTTP seam is monkeypatched.
"""
from __future__ import annotations

import numpy as np
import pytest

from qtms.data import live_data as L
from qtms.data.market_data import MarketDataAdapter


def _fake_binance_klines(n=300, start=1_700_000_000_000, step=300_000):
    rows = []
    price = 30000.0
    for i in range(n):
        o = price
        c = price * (1 + ((-1) ** i) * 0.001)
        h = max(o, c) * 1.001
        lo = min(o, c) * 0.999
        rows.append([start + i * step, f"{o}", f"{h}", f"{lo}", f"{c}", "12.5",
                     0, "0", 0, "0", "0", "0"])
        price = c
    return rows


def test_fetch_parses_binance(monkeypatch):
    monkeypatch.setattr(L, "_http_get_json", lambda url, timeout=10.0: _fake_binance_klines())
    df = L.fetch_ohlcv("BTC/USDT", timeframe="5m", limit=200, source="binance")
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "spread"]
    assert len(df) == 200  # trimmed to limit
    assert df.attrs["synthetic"] is False
    assert df.attrs["source"] == "binance"
    assert df.index.is_monotonic_increasing
    assert (df["close"] > 0).all()


def test_auto_falls_through_to_next_provider(monkeypatch):
    calls = {"n": 0}

    def flaky(url, timeout=10.0):
        calls["n"] += 1
        if "binance" in url:
            raise OSError("blocked")
        if "coinbase" in url:
            raise OSError("blocked")
        # kraken shape
        return {"error": [], "result": {"XXBTZUSD": [
            [1_700_000_000 + i * 300, "1", "2", "0.5", "1.5", "1.4", "10.0", 3]
            for i in range(50)
        ], "last": 1}}

    monkeypatch.setattr(L, "_http_get_json", flaky)
    df = L.fetch_ohlcv("BTC/USDT", timeframe="5m", source="auto")
    assert df.attrs["source"] == "kraken"
    assert len(df) == 50


def test_all_sources_fail_raises(monkeypatch):
    def boom(url, timeout=10.0):
        raise OSError("network down")
    monkeypatch.setattr(L, "_http_get_json", boom)
    with pytest.raises(L.LiveDataError):
        L.fetch_ohlcv("BTC/USDT", source="auto")


def test_adapter_live_delegates(monkeypatch, cfg):
    monkeypatch.setattr(L, "_http_get_json", lambda url, timeout=10.0: _fake_binance_klines())
    df = MarketDataAdapter(cfg).live("BTC/USDT", timeframe="5m", limit=100, source="binance")
    assert len(df) == 100 and df.attrs["source"] == "binance"


def test_autopilot_falls_back_when_live_fails(monkeypatch, cfg):
    # Force live fetch to fail; autopilot must fall back to synthetic, not crash.
    from qtms.agents.autopilot import Autopilot
    monkeypatch.setattr(L, "_http_get_json", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked")))
    cfg.monte_carlo.n_paths = 15
    ap = Autopilot(cfg)
    ap.data_source = "live"
    ap.n_candles = 400
    ap.paper_steps = 2
    df, used, note = ap._get_data("BTC/USDT", seed=1)
    assert used == "synthetic(fallback)"
    assert "live fetch failed" in note
    assert len(df) == 400
