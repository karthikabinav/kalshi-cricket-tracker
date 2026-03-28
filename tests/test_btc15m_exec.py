from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from kalshi_cricket_tracker.config import BTC15mExecConfig
from kalshi_cricket_tracker.execution.btc15m import BTC15mExecutionAgent, BTC15mMarketSnapshot, RiskState, load_snapshot_sequence
from kalshi_cricket_tracker.execution.kalshi import MockKalshiPaperClient


def make_snapshot(**overrides):
    base = dict(
        ticker="KXBTC15M-TEST-15",
        rules="Resolves to YES if BTC settles above threshold at close.",
        status="open",
        close_time=datetime.now(timezone.utc) + timedelta(seconds=70),
        yes_ask_cents=80,
        yes_bid_cents=80,
        no_ask_cents=22,
        no_bid_cents=20,
        best_yes_ask_size=50,
        best_yes_bid_size=60,
        best_no_ask_size=55,
        best_no_bid_size=65,
        orderbook_stability_bps=20,
        thesis_price_cents=90,
        realized_vol_bps=25,
        microprice_cents=88.0,
        orderbook_imbalance=0.25,
        depth_contracts=50,
        recent_trades_count=12,
        recent_trade_buy_ratio=0.7,
        settlement_signal_strength=0.2,
    )
    base.update(overrides)
    return BTC15mMarketSnapshot(**base)


def test_btc15m_defaults_to_no_trade_when_disabled():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=False))
    decision = agent.evaluate(make_snapshot(), RiskState())
    assert decision.decision == "NO TRADE"
    assert "disabled" in decision.reason.lower()


def test_btc15m_abstains_when_too_close_to_close():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True, min_time_to_close_min=20 / 60))
    snapshot = make_snapshot(close_time=datetime.now(timezone.utc) + timedelta(seconds=10))
    decision = agent.evaluate(snapshot, RiskState())
    assert decision.decision == "NO TRADE"
    assert "late-entry chaos" in decision.reason.lower()


def test_btc15m_abstains_when_too_early_for_window():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True, max_time_to_close_min=2.0))
    snapshot = make_snapshot(close_time=datetime.now(timezone.utc) + timedelta(minutes=5))
    decision = agent.evaluate(snapshot, RiskState())
    assert decision.decision == "NO TRADE"
    assert "too early" in decision.reason.lower()


def test_btc15m_estimate_trade_ev_prefers_positive_yes_entry():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True, min_ev_to_trade_cents=0.2))
    ev = agent.estimate_trade_ev(make_snapshot(), RiskState())
    assert ev.recommended_action == "ENTER_LONG_YES"
    assert ev.fair_prob > 0.8
    assert ev.net_ev > 0
    assert ev.recommended_size > 0


def test_btc15m_returns_trade_when_all_checks_pass():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True, min_confidence=20, dominant_side_min_cents=80))
    decision = agent.evaluate(make_snapshot(), RiskState())
    assert decision.decision == "TRADE"
    assert decision.side == "YES"
    assert decision.planned_entry_cents == 80


def test_btc15m_blocks_on_risk_state():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True))
    decision = agent.evaluate(make_snapshot(), RiskState(open_positions=1))
    assert decision.decision == "NO TRADE"
    assert "max simultaneous" in decision.reason.lower()


def test_btc15m_abstains_below_dominant_bid_threshold():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True, dominant_side_min_cents=80))
    decision = agent.evaluate(make_snapshot(yes_bid_cents=79, yes_ask_cents=81), RiskState())
    assert decision.decision == "NO TRADE"
    assert "below 80c trigger" in decision.reason.lower()


def test_btc15m_decide_trade_exits_when_open_position_turns_negative():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True))
    snapshot = make_snapshot(
        current_position_side="YES",
        current_position_entry_cents=82,
        thesis_price_cents=74,
        microprice_cents=74,
        orderbook_imbalance=-0.4,
        recent_trade_buy_ratio=0.2,
        settlement_signal_strength=-0.2,
    )
    assert agent.decide_trade(snapshot, RiskState(open_positions=1)) == "EXIT"


def test_btc15m_logs_candidate_trade_and_state(tmp_path):
    cfg = BTC15mExecConfig(enabled=True, min_confidence=20, dominant_side_min_cents=80)
    agent = BTC15mExecutionAgent(cfg)
    decision = agent.evaluate(make_snapshot(), RiskState())
    out = agent.execute_candidate(decision, MockKalshiPaperClient(), tmp_path, live_enabled=False, risk=RiskState())
    assert out is not None

    candidate_lines = (tmp_path / cfg.candidate_log_jsonl).read_text(encoding="utf-8").strip().splitlines()
    trade_lines = (tmp_path / cfg.executed_log_jsonl).read_text(encoding="utf-8").strip().splitlines()
    state_lines = (tmp_path / cfg.state_log_jsonl).read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(candidate_lines[0])["decision"] == "TRADE"
    assert json.loads(trade_lines[0])["classification"] == "paper_trade"
    assert json.loads(state_lines[0])["decision_metrics"]["resulting_capital_usd"] is not None


def test_btc15m_vol_bwk_buy_then_sell_updates_inventory_and_capital(tmp_path):
    cfg = BTC15mExecConfig(enabled=True, vol_bwk_enabled=True, initial_capital_usd=100.0)
    agent = BTC15mExecutionAgent(cfg)
    risk = RiskState(current_capital_usd=100.0)

    entry = make_snapshot(
        yes_bid_cents=46,
        yes_ask_cents=47,
        no_bid_cents=53,
        no_ask_cents=54,
        thesis_price_cents=50,
        microprice_cents=49.0,
        orderbook_imbalance=-0.2,
        recent_trade_buy_ratio=0.35,
        realized_vol_bps=65.0,
        local_mean_reversion_zscore=-1.4,
    )
    decision_in = agent.evaluate(entry, risk)
    assert decision_in.decision == "TRADE"
    assert decision_in.action.startswith("buy_yes")
    agent.execute_candidate(decision_in, MockKalshiPaperClient(), tmp_path, live_enabled=False, risk=risk, persist_state_path=tmp_path / cfg.risk_state_json)

    risk_after_buy = RiskState(**json.loads((tmp_path / cfg.risk_state_json).read_text(encoding="utf-8")))
    assert risk_after_buy.inventory_state == "LONG_YES"
    assert risk_after_buy.current_capital_usd < 100.0

    exit_snapshot = make_snapshot(
        yes_bid_cents=50,
        yes_ask_cents=51,
        no_bid_cents=49,
        no_ask_cents=50,
        thesis_price_cents=50,
        microprice_cents=50.0,
        orderbook_imbalance=0.3,
        recent_trade_buy_ratio=0.7,
        realized_vol_bps=40.0,
        local_mean_reversion_zscore=1.2,
        current_position_side="YES",
        current_position_entry_cents=47,
    )
    decision_out = agent.evaluate(exit_snapshot, risk_after_buy)
    assert decision_out.decision == "NO TRADE"
    assert decision_out.action == "sell_yes"
    agent.execute_candidate(decision_out, MockKalshiPaperClient(), tmp_path, live_enabled=False, risk=risk_after_buy, persist_state_path=tmp_path / cfg.risk_state_json)

    risk_after_sell = RiskState(**json.loads((tmp_path / cfg.risk_state_json).read_text(encoding="utf-8")))
    assert risk_after_sell.inventory_state == "FLAT"
    assert risk_after_sell.realized_round_trip_pnl_usd > 0
    assert risk_after_sell.current_capital_usd > risk_after_buy.current_capital_usd


def test_load_snapshot_sequence_supports_jsonl(tmp_path):
    payload = [
        {**make_snapshot(snapshot_index=0, snapshot_sequence_id="seq-1").__dict__, "close_time": make_snapshot().close_time.isoformat()},
        {**make_snapshot(snapshot_index=1, snapshot_sequence_id="seq-1").__dict__, "close_time": make_snapshot().close_time.isoformat()},
    ]
    path = tmp_path / "snaps.jsonl"
    path.write_text("\n".join(json.dumps(item, default=str) for item in payload), encoding="utf-8")
    seq = load_snapshot_sequence(path)
    assert len(seq) == 2
    assert seq[0].snapshot_sequence_id == "seq-1"
