from __future__ import annotations

import json
from pathlib import Path

from kalshi_cricket_tracker.config import load_config
from kalshi_cricket_tracker.execution.btc15m_lifecycle import finalize_market_run


def test_finalize_market_run_writes_summary_and_learning(tmp_path: Path):
    cfg = load_config('configs/btc15m_paper.yaml')
    (tmp_path / cfg.btc15m.executed_log_jsonl).write_text(
        json.dumps({"ticker": "KXBTC15M-TEST-15", "action": "buy_no_8", "pnl": None}) + "\n" +
        json.dumps({"ticker": "KXBTC15M-TEST-15", "action": "sell_no", "pnl": 1.25}) + "\n",
        encoding='utf-8'
    )
    (tmp_path / cfg.btc15m.candidate_log_jsonl).write_text(
        json.dumps({"ticker": "KXBTC15M-TEST-15", "reason": "example reason"}) + "\n",
        encoding='utf-8'
    )
    (tmp_path / cfg.btc15m.state_log_jsonl).write_text(
        json.dumps({"ticker": "KXBTC15M-TEST-15", "decision": "TRADE"}) + "\n",
        encoding='utf-8'
    )
    (tmp_path / cfg.btc15m.risk_state_json).write_text(json.dumps({"current_capital_usd": 101.25}), encoding='utf-8')

    summary_path, learning_path = finalize_market_run(cfg, 'KXBTC15M-TEST-15', root_artifact_dir=tmp_path)
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    assert summary['executed_trade_count'] == 2
    assert summary['realized_pnl_usd'] == 1.25
    assert learning_path.exists()
    assert 'example reason' in learning_path.read_text(encoding='utf-8')


def test_finalize_market_run_uses_explicit_risk_state_path(tmp_path: Path):
    cfg = load_config('configs/btc15m_paper.yaml')
    (tmp_path / cfg.btc15m.executed_log_jsonl).write_text(
        json.dumps({"ticker": "KXBTC15M-TEST-15", "action": "sell_no", "pnl": -70.06}) + "\n",
        encoding='utf-8'
    )
    explicit_risk = tmp_path / 'clean_risk.json'
    explicit_risk.write_text(json.dumps({"current_capital_usd": 30.0, "daily_realized_pnl_usd": -70.06}), encoding='utf-8')
    (tmp_path / cfg.btc15m.risk_state_json).write_text(json.dumps({"current_capital_usd": 124.14, "daily_realized_pnl_usd": 85.9518}), encoding='utf-8')

    summary_path, _ = finalize_market_run(
        cfg,
        'KXBTC15M-TEST-15',
        root_artifact_dir=tmp_path,
        risk_state_path=explicit_risk,
    )
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    assert summary['realized_pnl_usd'] == -70.06
    assert summary['current_capital_usd'] == 30.0
    assert summary['risk_state']['daily_realized_pnl_usd'] == -70.06
