"""Shared pytest fixtures.

Ensures the project root is importable and resets global safety state (kill
switch + config) between tests so they are independent and deterministic.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qtms.app.config import QTMSConfig, set_config  # noqa: E402
from qtms.app.safety import KILL_SWITCH  # noqa: E402
from qtms.data.market_data import MarketDataAdapter  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_state():
    # Reset kill switch and any live-related env before each test.
    KILL_SWITCH.reset()
    for k in ("QTMS_ENABLE_LIVE", "QTMS_MANUAL_LIVE_APPROVAL"):
        os.environ.pop(k, None)
    set_config(QTMSConfig())
    yield
    KILL_SWITCH.reset()


@pytest.fixture
def cfg():
    c = QTMSConfig()
    set_config(c)
    return c


@pytest.fixture
def df(cfg):
    return MarketDataAdapter(cfg).synthetic("BTC/USDT", n=400, seed=7)
