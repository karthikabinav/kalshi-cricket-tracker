from __future__ import annotations

import pandas as pd

from kalshi_cricket_tracker.strategy.live_arb import ArbConfig, backtest_from_snapshots, decide_action, OpenPosition


def test_open_yes_then_take_profit_close():
    cfg = ArbConfig(entry_edge_bps=200, exit_edge_bps=30, take_profit_bps=100, stop_loss_bps=120, max_holding_minutes=60)
    ts0 = pd.Timestamp("2026-03-01T00:00:00Z")
    action, meta = decide_action("e1", ts0, model_prob_team1=0.62, market_prob_team1=0.58, cfg=cfg, position=None)
    assert action == "OPEN_YES"

    pos = OpenPosition(event_id="e1", side="YES", entry_prob=0.58, entry_ts=ts0, stake_usd=100)
    action2, meta2 = decide_action(
        "e1", ts0 + pd.Timedelta(minutes=5), model_prob_team1=0.63, market_prob_team1=0.595, cfg=cfg, position=pos
    )
    assert action2 == "CLOSE_YES"
    assert meta2["reason"] in {"take_profit", "edge_normalized"}


def test_backtest_snapshots_generates_closed_trades():
    cfg = ArbConfig(entry_edge_bps=150, exit_edge_bps=20, take_profit_bps=80, stop_loss_bps=200, max_holding_minutes=120)
    snaps = pd.DataFrame(
        [
            {"ts": "2026-03-01T00:00:00Z", "event_id": "m1", "model_prob_team1": 0.60, "market_prob_team1": 0.56},
            {"ts": "2026-03-01T00:20:00Z", "event_id": "m1", "model_prob_team1": 0.59, "market_prob_team1": 0.57},
            {"ts": "2026-03-01T00:40:00Z", "event_id": "m1", "model_prob_team1": 0.58, "market_prob_team1": 0.58},
        ]
    )

    trades, metrics = backtest_from_snapshots(snaps, cfg, stake_usd=100)
    assert not trades.empty
    assert metrics["closed_trades"] >= 1
