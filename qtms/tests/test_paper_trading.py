"""Paper broker + engine: fees/slippage applied, journal recorded, no real money."""
from __future__ import annotations

from qtms.app.schemas import Signal
from qtms.execution.paper_broker import PaperBroker
from qtms.app.paper_engine import PaperTradingEngine


def test_paper_broker_applies_fees_and_slippage(cfg):
    broker = PaperBroker(cfg)
    pos = broker.open("BTC/USDT", Signal.LONG, qty=0.1, ref_price=30_000.0, seed=1)
    # Buy slippage means fill above reference.
    assert pos.entry_price > 30_000.0
    assert pos.entry_fee > 0.0
    # Opening only pays the fee in the PnL-accounting model.
    assert broker.cash < broker.starting_balance


def test_paper_round_trip_records_trade(cfg):
    broker = PaperBroker(cfg)
    broker.open("BTC/USDT", Signal.LONG, qty=0.1, ref_price=30_000.0, seed=1,
                entry_reason=["test"], strategy_weights={"trend_following": 1.0})
    rec = broker.close("BTC/USDT", ref_price=31_000.0, exit_reason=["tp"], seed=1)
    assert rec is not None
    assert rec.exit_price is not None
    assert rec.fees > 0.0
    assert rec.slippage > 0.0
    assert len(broker.closed_trades) == 1
    assert rec.entry_reason == ["test"]
    assert "trend_following" in rec.strategy_weights


def test_paper_short_profits_when_price_falls(cfg):
    broker = PaperBroker(cfg)
    broker.open("BTC/USDT", Signal.SHORT, qty=0.1, ref_price=30_000.0, seed=2)
    rec = broker.close("BTC/USDT", ref_price=29_000.0, seed=2)
    assert rec.pnl > 0.0  # short gains as price drops (net of costs here)


def test_engine_runs_without_real_money(cfg, df):
    cfg.monte_carlo.n_paths = 15
    eng = PaperTradingEngine(cfg, mc_paths=15)
    eng.start(df, warmup=200)
    out = eng.run(max_steps=5)
    assert out["steps"] >= 1
    status = eng.status()
    # Equity tracked virtually; never references real funds.
    assert "equity" in status
    assert status["starting_balance"] == cfg.risk.starting_balance


def test_excursions_tracked(cfg):
    broker = PaperBroker(cfg)
    broker.open("BTC/USDT", Signal.LONG, qty=0.1, ref_price=30_000.0, seed=1)
    broker.mark({"BTC/USDT": 31_000.0})
    broker.mark({"BTC/USDT": 29_500.0})
    pos = broker.positions["BTC/USDT"]
    assert pos.mfe > 0.0
    assert pos.mae < 0.0
