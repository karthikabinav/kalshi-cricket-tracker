from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from kalshi_cricket_tracker.config import BTC15mExecConfig
from kalshi_cricket_tracker.execution.btc15m import BTC15mExecutionAgent, BTC15mMarketSnapshot, RiskState
from kalshi_cricket_tracker.execution.kalshi import MockKalshiPaperClient


def make_snapshot(**overrides):
    base = dict(
        ticker="KXBTCD-15M-TEST",
        rules="Resolves to YES if BTC settles above threshold at close.",
        status="open",
        close_time=datetime.now(timezone.utc) + timedelta(minutes=8),
        yes_ask_cents=58,
        yes_bid_cents=57,
        no_ask_cents=43,
        no_bid_cents=42,
        best_yes_ask_size=50,
        best_yes_bid_size=60,
        best_no_ask_size=55,
        best_no_bid_size=65,
        orderbook_stability_bps=20,
        thesis_price_cents=63,
    )
    base.update(overrides)
    return BTC15mMarketSnapshot(**base)


def test_btc15m_defaults_to_no_trade_when_disabled():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=False))
    decision = agent.evaluate(make_snapshot(), RiskState())
    assert decision.decision == "NO TRADE"
    assert "disabled" in decision.reason.lower()


def test_btc15m_abstains_when_too_close_to_close():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True, min_time_to_close_min=4))
    snapshot = make_snapshot(close_time=datetime.now(timezone.utc) + timedelta(minutes=2))
    decision = agent.evaluate(snapshot, RiskState())
    assert decision.decision == "NO TRADE"
    assert "late-entry chaos" in decision.reason.lower()


def test_btc15m_returns_trade_when_all_checks_pass():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True, min_confidence=20, min_edge_cents=3))
    decision = agent.evaluate(make_snapshot(), RiskState())
    assert decision.decision == "TRADE"
    assert decision.side == "YES"
    assert decision.planned_entry_cents == 58


def test_btc15m_blocks_on_risk_state():
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True))
    decision = agent.evaluate(make_snapshot(), RiskState(open_positions=1))
    assert decision.decision == "NO TRADE"
    assert "max simultaneous" in decision.reason.lower()


def test_btc15m_logs_candidate_and_trade(tmp_path):
    agent = BTC15mExecutionAgent(BTC15mExecConfig(enabled=True, min_confidence=20, min_edge_cents=3))
    decision = agent.evaluate(make_snapshot(), RiskState())
    out = agent.execute_candidate(decision, MockKalshiPaperClient(), tmp_path, live_enabled=False)
    assert out is not None

    candidate_lines = (tmp_path / "btc15m_candidate_decisions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    trade_lines = (tmp_path / "btc15m_executed_trades.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(candidate_lines[0])["decision"] == "TRADE"
    assert json.loads(trade_lines[0])["classification"] == "paper_trade"
