"""Smoke tests for the FastAPI app and key endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from qtms.app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["live_trading_enabled"] is False


def test_dashboard_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "QTMS" in r.text


def test_live_disabled_status():
    r = client.post("/live/disabled-status")
    assert r.status_code == 200
    assert r.json()["is_disabled"] is True


def test_live_request_approval_never_enables():
    r = client.post("/live/request-approval")
    assert r.status_code == 200
    assert r.json()["approved"] is False


def test_synthetic_then_backtest():
    r = client.post("/data/synthetic", json={"symbol": "BTC/USDT", "n": 300})
    assert r.status_code == 200
    assert r.json()["rows"] == 300
    r2 = client.post("/backtest/run", json={"symbol": "BTC/USDT", "strategy": "trend_following"})
    assert r2.status_code == 200
    assert "passed" in r2.json()
