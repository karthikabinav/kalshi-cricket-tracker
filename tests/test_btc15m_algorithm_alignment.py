from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from kalshi_cricket_tracker.config import BTC15mExecConfig
from kalshi_cricket_tracker.execution.btc15m import BTC15mExecutionAgent, BTC15mMarketSnapshot, RiskState
from kalshi_cricket_tracker.execution.kalshi import MockKalshiPaperClient


MID_CFG = BTC15mExecConfig(
    enabled=True,
    manual_paper_enabled=False,
    min_time_to_close_min=3.0,
    max_time_to_close_min=12.0,
    min_depth_contracts=25,
    max_spread_cents=2,
    max_orderbook_instability_bps=60.0,
    min_confidence=20,
    min_ev_to_trade_cents=0.2,
)


def make_snapshot(**overrides):
    base = dict(
        ticker="KXBTC15M-TEST-15",
        rules="Resolves to YES if BTC settles above threshold at close.",
        status="open",
        close_time=datetime.now(timezone.utc) + timedelta(minutes=8),
        yes_ask_cents=80,
        yes_bid_cents=80,
        no_ask_cents=22,
        no_bid_cents=20,
        best_yes_ask_size=90,
        best_yes_bid_size=90,
        best_no_ask_size=90,
        best_no_bid_size=90,
        orderbook_stability_bps=10,
        thesis_price_cents=90,
        realized_vol_bps=20,
        microprice_cents=88.0,
        orderbook_imbalance=0.25,
        depth_contracts=90,
        recent_trades_count=20,
        recent_trade_buy_ratio=0.7,
        settlement_signal_strength=0.2,
    )
    base.update(overrides)
    return BTC15mMarketSnapshot(**base)


def test_algorithm_blocks_final_three_minute_region():
    agent = BTC15mExecutionAgent(MID_CFG)
    decision = agent.evaluate(make_snapshot(close_time=datetime.now(timezone.utc) + timedelta(minutes=2, seconds=30)), RiskState())
    assert decision.decision == "NO TRADE"
    assert "final 3-minute" in decision.reason.lower()


def test_algorithm_allows_middle_window_when_market_quality_is_good():
    agent = BTC15mExecutionAgent(MID_CFG)
    decision = agent.evaluate(make_snapshot(close_time=datetime.now(timezone.utc) + timedelta(minutes=8)), RiskState())
    assert decision.decision == "TRADE"
    assert decision.action in {"enter_long_yes", "buy_yes", "ENTER_LONG_YES".lower(), "ENTER_LONG_YES"} or "yes" in decision.action.lower() or decision.side == "YES"


def test_algorithm_blocks_wide_spread_even_in_middle_window():
    agent = BTC15mExecutionAgent(MID_CFG)
    decision = agent.evaluate(make_snapshot(yes_ask_cents=85, yes_bid_cents=80, no_ask_cents=21, no_bid_cents=15), RiskState())
    assert decision.decision == "NO TRADE"
    assert "spread too wide" in decision.reason.lower()


def test_algorithm_blocks_low_depth_even_in_middle_window():
    agent = BTC15mExecutionAgent(MID_CFG)
    decision = agent.evaluate(make_snapshot(yes_bid_cents=80, depth_contracts=5, best_yes_ask_size=5, best_yes_bid_size=5, best_no_ask_size=5, best_no_bid_size=5), RiskState())
    assert decision.decision == "NO TRADE"
    assert "insufficient top-of-book depth" in decision.reason.lower()


def test_algorithm_blocks_unstable_book_even_in_middle_window():
    agent = BTC15mExecutionAgent(MID_CFG)
    decision = agent.evaluate(make_snapshot(orderbook_stability_bps=500), RiskState())
    assert decision.decision == "NO TRADE"
    assert "unstable" in decision.reason.lower()


def test_algorithm_blocks_when_risk_limits_hit():
    agent = BTC15mExecutionAgent(MID_CFG)
    decision = agent.evaluate(make_snapshot(), RiskState(daily_realized_pnl_usd=-200.0))
    assert decision.decision == "NO TRADE"
    assert "daily loss" in decision.reason.lower()


def test_algorithm_exits_open_position_when_signal_turns_negative():
    agent = BTC15mExecutionAgent(MID_CFG)
    snapshot = make_snapshot(
        current_position_side="YES",
        current_position_entry_cents=82,
        thesis_price_cents=70,
        microprice_cents=70,
        orderbook_imbalance=-0.5,
        recent_trade_buy_ratio=0.1,
        settlement_signal_strength=-0.3,
    )
    action = agent.decide_trade(snapshot, RiskState(open_positions=1, inventory_state="LONG_YES", inventory_qty=1, entry_price_cents=82))
    assert action == "EXIT"


def test_algorithm_no_trade_does_not_log_executable_buy_action_when_blocked():
    cfg = MID_CFG.model_copy(update={"manual_paper_enabled": True})
    agent = BTC15mExecutionAgent(cfg)
    decision = agent.evaluate(make_snapshot(orderbook_stability_bps=500), RiskState())
    assert decision.decision == "NO TRADE"
    assert decision.action in {"skip", "hold"}
    assert decision.state_context.get("manual_action") in {"skip", "hold"}


def test_band_logic_blocks_buy_above_entry_band():
    cfg = MID_CFG.model_copy(update={"manual_paper_enabled": True, "manual_entry_cents": 60})
    agent = BTC15mExecutionAgent(cfg)
    decision = agent.evaluate(make_snapshot(yes_ask_cents=67, yes_bid_cents=64, no_ask_cents=36, no_bid_cents=33), RiskState())
    assert decision.decision == "NO TRADE"
    assert decision.action == "skip"


def test_band_logic_prefers_side_closest_to_entry_band():
    cfg = MID_CFG.model_copy(update={"manual_paper_enabled": True, "manual_entry_cents": 60})
    agent = BTC15mExecutionAgent(cfg)
    decision = agent.evaluate(make_snapshot(yes_bid_cents=57, yes_ask_cents=58, no_bid_cents=17, no_ask_cents=18), RiskState())
    assert decision.decision == "TRADE"
    assert decision.action == "buy_yes"


def test_algorithm_paper_execution_persists_logs_and_state(tmp_path):
    cfg = MID_CFG.model_copy(update={"candidate_log_jsonl": "cand.jsonl", "executed_log_jsonl": "trades.jsonl", "state_log_jsonl": "state.jsonl", "risk_state_json": "risk.json"})
    agent = BTC15mExecutionAgent(cfg)
    risk = RiskState(current_capital_usd=100.0)
    decision = agent.evaluate(make_snapshot(yes_bid_cents=80), risk)
    agent.execute_candidate(decision, MockKalshiPaperClient(), tmp_path, live_enabled=False, risk=risk, persist_state_path=tmp_path / cfg.risk_state_json)

    assert (tmp_path / cfg.candidate_log_jsonl).exists()
    assert (tmp_path / cfg.executed_log_jsonl).exists()
    assert (tmp_path / cfg.state_log_jsonl).exists()
    saved_risk = json.loads((tmp_path / cfg.risk_state_json).read_text(encoding="utf-8"))
    assert "current_capital_usd" in saved_risk


def test_hold_exits_when_profit_target_reached():
    cfg = MID_CFG.model_copy(update={"manual_paper_enabled": True, "profit_target_fraction": 0.10, "max_dollars_per_trade": 100.0})
    agent = BTC15mExecutionAgent(cfg)
    risk = RiskState(current_capital_usd=100.0, inventory_state="LONG_NO", inventory_qty=100, entry_price_cents=15.0)
    decision = agent.evaluate(make_snapshot(yes_bid_cents=10, yes_ask_cents=11, no_bid_cents=90, no_ask_cents=91, current_position_side="NO", current_position_entry_cents=15), risk)
    assert decision.action == "sell_no"


def test_forced_time_exit_at_three_minutes():
    cfg = MID_CFG.model_copy(update={"manual_paper_enabled": True, "min_time_to_close_min": 3.0})
    agent = BTC15mExecutionAgent(cfg)
    risk = RiskState(current_capital_usd=100.0, inventory_state="LONG_NO", inventory_qty=100, entry_price_cents=60.0)
    decision = agent.evaluate(make_snapshot(close_time=datetime.now(timezone.utc) + timedelta(minutes=2, seconds=30), current_position_side="NO", current_position_entry_cents=60, no_bid_cents=65, no_ask_cents=66), risk)
    assert decision.action == "sell_no"
    assert "forced time exit" in decision.reason.lower()


def test_sell_trade_logs_realized_pnl(tmp_path):
    from kalshi_cricket_tracker.execution.btc15m import CandidateDecision

    cfg = MID_CFG.model_copy(update={"manual_paper_enabled": True, "candidate_log_jsonl": "cand.jsonl", "executed_log_jsonl": "trades.jsonl", "state_log_jsonl": "state.jsonl", "risk_state_json": "risk.json"})
    agent = BTC15mExecutionAgent(cfg)
    risk = RiskState(current_capital_usd=100.0, inventory_state="LONG_NO", inventory_qty=1, entry_price_cents=18.0, reserved_capital_usd=0.18)
    decision = CandidateDecision(
        decision="NO TRADE",
        ticker="KXBTC15M-TEST-15",
        side="NONE",
        confidence=20,
        reason="Exit preferred.",
        time_remaining_min=8.0,
        orderbook_summary={"no_bid": 20, "yes_bid": 80},
        planned_entry_cents=None,
        planned_profit_take_cents=None,
        invalidation="Abstain",
        expected_edge_cents=None,
        action="sell_no",
        quantity=1,
        reward_cents=0.0,
        cost_cents=0.0,
        lagrangian_score=0.1,
        fee_cents=0.018,
        resulting_capital_usd=100.0,
        realized_round_trip_pnl_usd=0.0,
        unrealized_pnl_usd=0.0,
        inventory_state_after="FLAT",
        state_context={},
    )
    agent.execute_candidate(decision, MockKalshiPaperClient(), tmp_path, live_enabled=False, risk=risk, persist_state_path=tmp_path / cfg.risk_state_json)
    trades = [json.loads(line) for line in (tmp_path / cfg.executed_log_jsonl).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(trades) == 1
    assert trades[-1]["action"] == "sell_no"
    assert trades[-1]["pnl"] is not None
