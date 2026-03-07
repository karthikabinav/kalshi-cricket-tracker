from __future__ import annotations

import pandas as pd

from kalshi_cricket_tracker.strategy.live_arb import ArbConfig, OpenPosition, backtest_from_snapshots, decide_action


def test_open_no_when_yes_is_overpriced():
    cfg = ArbConfig(entry_edge_bps=200)
    ts = pd.Timestamp("2026-03-01T00:00:00Z")
    action, meta = decide_action("e1", ts, model_prob_team1=0.40, market_prob_team1=0.45, cfg=cfg, position=None)
    assert action == "OPEN_NO"
    assert meta["reason"] == "overpriced_yes"


def test_hold_when_edge_below_entry_threshold():
    cfg = ArbConfig(entry_edge_bps=250)
    ts = pd.Timestamp("2026-03-01T00:00:00Z")
    action, meta = decide_action("e1", ts, model_prob_team1=0.51, market_prob_team1=0.50, cfg=cfg, position=None)
    assert action == "HOLD"
    assert meta["reason"] == "no_edge"


def test_yes_position_stop_loss():
    cfg = ArbConfig(entry_edge_bps=100, stop_loss_bps=80, take_profit_bps=500)
    ts0 = pd.Timestamp("2026-03-01T00:00:00Z")
    pos = OpenPosition("e1", "YES", entry_prob=0.60, entry_ts=ts0, stake_usd=100)
    action, meta = decide_action("e1", ts0 + pd.Timedelta(minutes=10), 0.58, 0.59, cfg, pos)
    assert action == "CLOSE_YES"
    assert meta["reason"] == "stop_loss"


def test_no_position_take_profit():
    cfg = ArbConfig(entry_edge_bps=100, take_profit_bps=90)
    ts0 = pd.Timestamp("2026-03-01T00:00:00Z")
    pos = OpenPosition("e1", "NO", entry_prob=0.48, entry_ts=ts0, stake_usd=100)
    action, meta = decide_action("e1", ts0 + pd.Timedelta(minutes=15), 0.46, 0.47, cfg, pos)
    assert action == "CLOSE_NO"
    assert meta["reason"] in {"take_profit", "edge_normalized"}


def test_position_closes_on_max_holding():
    cfg = ArbConfig(entry_edge_bps=100, max_holding_minutes=5, take_profit_bps=1000, stop_loss_bps=1000)
    ts0 = pd.Timestamp("2026-03-01T00:00:00Z")
    pos = OpenPosition("e1", "YES", entry_prob=0.55, entry_ts=ts0, stake_usd=100)
    action, meta = decide_action("e1", ts0 + pd.Timedelta(minutes=6), 0.56, 0.551, cfg, pos)
    assert action == "CLOSE_YES"
    assert meta["reason"] == "max_holding"


def test_backtest_rejects_missing_columns():
    cfg = ArbConfig()
    snaps = pd.DataFrame([{"ts": "2026-03-01T00:00:00Z", "event_id": "m1"}])
    try:
        backtest_from_snapshots(snaps, cfg)
        raise AssertionError("Expected ValueError for missing columns")
    except ValueError as exc:
        assert "missing columns" in str(exc)


def test_backtest_handles_multiple_events_and_open_positions():
    cfg = ArbConfig(entry_edge_bps=150, exit_edge_bps=20, take_profit_bps=80, stop_loss_bps=200, max_holding_minutes=200)
    snaps = pd.DataFrame(
        [
            {"ts": "2026-03-01T00:00:00Z", "event_id": "m1", "model_prob_team1": 0.61, "market_prob_team1": 0.57},
            {"ts": "2026-03-01T00:10:00Z", "event_id": "m2", "model_prob_team1": 0.41, "market_prob_team1": 0.46},
            {"ts": "2026-03-01T00:30:00Z", "event_id": "m1", "model_prob_team1": 0.60, "market_prob_team1": 0.585},
            {"ts": "2026-03-01T00:40:00Z", "event_id": "m2", "model_prob_team1": 0.43, "market_prob_team1": 0.455},
            {"ts": "2026-03-01T01:00:00Z", "event_id": "m1", "model_prob_team1": 0.59, "market_prob_team1": 0.59},
        ]
    )
    trades, metrics = backtest_from_snapshots(snaps, cfg, stake_usd=100)
    assert not trades.empty
    assert metrics["closed_trades"] >= 1
    assert "total_pnl_usd" in metrics
