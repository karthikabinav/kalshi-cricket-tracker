from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kalshi_cricket_tracker.config import load_config
from kalshi_cricket_tracker.execution.btc15m import BTC15mMarketSnapshot
from kalshi_cricket_tracker.execution.btc15m_lifecycle import finalize_market_run, run_market_worker, run_supervisor, wait_for_market_snapshot


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


def _snapshot(ticker: str, close_dt: datetime) -> BTC15mMarketSnapshot:
    return BTC15mMarketSnapshot(
        ticker=ticker,
        rules='rule',
        status='open',
        close_time=close_dt,
        yes_ask_cents=51,
        yes_bid_cents=50,
        no_ask_cents=50,
        no_bid_cents=49,
        best_yes_ask_size=10,
        best_yes_bid_size=10,
        best_no_ask_size=10,
        best_no_bid_size=10,
        orderbook_stability_bps=0.0,
        depth_contracts=10,
    )


class _DummyClient:
    pass


def test_wait_for_market_snapshot_uses_close_time_progression(monkeypatch):
    cfg = load_config('configs/btc15m_paper.yaml')
    base = datetime(2026, 3, 29, 5, 15, tzinfo=timezone.utc)
    stale = _snapshot('KXBTC15M-OLD-15', base)
    fresh = _snapshot('KXBTC15M-NEXT-15', base + timedelta(minutes=15))
    polls = iter([[stale], [stale], [stale, fresh]])

    monkeypatch.setattr(
        'kalshi_cricket_tracker.execution.btc15m_lifecycle._discover_candidate_snapshots',
        lambda client: next(polls),
    )
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.time.sleep', lambda _: None)

    chosen = wait_for_market_snapshot(cfg, _DummyClient(), after_close_time=base, poll_seconds=0.01, max_wait_seconds=1)
    assert chosen.ticker == 'KXBTC15M-NEXT-15'


def test_run_supervisor_can_anchor_on_next_market(monkeypatch):
    cfg = load_config('configs/btc15m_paper.yaml')
    base = datetime(2026, 3, 29, 5, 15, tzinfo=timezone.utc)
    current = _snapshot('KXBTC15M-CURRENT-15', base)
    nxt = _snapshot('KXBTC15M-NEXT-15', base + timedelta(minutes=15))

    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.KalshiRestClient.public', lambda trading: _DummyClient())
    calls: list[tuple[datetime | None, set[str]]] = []

    def fake_wait(cfg, client, after_close_time=None, exclude_tickers=None, poll_seconds=2.0, max_wait_seconds=None):
        calls.append((after_close_time, set(exclude_tickers or set())))
        if len(calls) == 1:
            return current
        return nxt

    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.wait_for_market_snapshot', fake_wait)
    monkeypatch.setattr(
        'kalshi_cricket_tracker.execution.btc15m_lifecycle.run_market_worker',
        lambda cfg, ticker, max_runtime_seconds, poll_seconds, risk_json=None, artifact_dir=None, clean_start=False: {'ticker': ticker},
    )

    results = run_supervisor(cfg, markets=1, poll_seconds=0.1, max_runtime_seconds=30, start_with_next_market=True, discovery_timeout_seconds=5)
    assert results == [{'ticker': 'KXBTC15M-NEXT-15'}]
    assert calls[0][0] is None
    assert calls[1][0] == current.close_time
    assert 'KXBTC15M-CURRENT-15' in calls[1][1]


def test_run_supervisor_threads_explicit_isolation_params(monkeypatch, tmp_path: Path):
    cfg = load_config('configs/btc15m_paper.yaml')
    base = datetime(2026, 3, 29, 5, 15, tzinfo=timezone.utc)
    current = _snapshot('KXBTC15M-CURRENT-15', base)
    nxt = _snapshot('KXBTC15M-NEXT-15', base + timedelta(minutes=15))

    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.KalshiRestClient.public', lambda trading: _DummyClient())

    calls: list[dict[str, object]] = []

    def fake_wait(cfg, client, after_close_time=None, exclude_tickers=None, poll_seconds=2.0, max_wait_seconds=None):
        return current if after_close_time is None else nxt

    def fake_run_market_worker(cfg, ticker, max_runtime_seconds, poll_seconds, risk_json=None, artifact_dir=None, clean_start=False):
        calls.append({
            'ticker': ticker,
            'risk_json': risk_json,
            'artifact_dir': artifact_dir,
            'clean_start': clean_start,
            'cfg_artifact_dir': cfg.runtime.artifact_dir,
        })
        return {'ticker': ticker}

    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.wait_for_market_snapshot', fake_wait)
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.run_market_worker', fake_run_market_worker)

    risk_path = tmp_path / 'isolated' / 'risk.json'
    artifact_dir = tmp_path / 'isolated' / 'artifacts'
    results = run_supervisor(
        cfg,
        markets=1,
        poll_seconds=0.1,
        max_runtime_seconds=30,
        start_with_next_market=True,
        discovery_timeout_seconds=5,
        risk_json=str(risk_path),
        artifact_dir=str(artifact_dir),
        clean_start=True,
    )

    assert results == [{'ticker': 'KXBTC15M-NEXT-15'}]
    assert calls == [{
        'ticker': 'KXBTC15M-NEXT-15',
        'risk_json': str(risk_path),
        'artifact_dir': str(artifact_dir),
        'clean_start': True,
        'cfg_artifact_dir': str(artifact_dir),
    }]


def test_run_market_worker_clean_start_overwrites_stale_risk(monkeypatch, tmp_path: Path):
    cfg = load_config('configs/btc15m_paper.yaml')
    close_dt = datetime(2026, 3, 29, 5, 15, tzinfo=timezone.utc)
    snapshot = _snapshot('KXBTC15M-TEST-15', close_dt)
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.KalshiRestClient.public', lambda trading: _DummyClient())
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.fetch_live_snapshot', lambda client, ticker=None: snapshot)
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.time.sleep', lambda _: None)

    class _FakeAgent:
        def __init__(self, cfg):
            self.seen_risks: list[object] = []

        def evaluate(self, snapshot, risk):
            self.seen_risks.append(risk)
            return type('Decision', (), {'action': 'skip'})()

        def execute_candidate(self, decision, client, log_dir, live_enabled, risk, persist_state_path):
            return None

    fake_agent = _FakeAgent(cfg.btc15m)
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.BTC15mExecutionAgent', lambda _: fake_agent)
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle.finalize_market_run', lambda cfg, ticker, root_artifact_dir=None, risk_state_path=None: (tmp_path / 'summary.json', tmp_path / 'learning.md'))
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle._read_jsonl', lambda path: [])
    monkeypatch.setattr('kalshi_cricket_tracker.execution.btc15m_lifecycle._read_json', lambda path: json.loads(Path(path).read_text(encoding='utf-8')))

    risk_path = tmp_path / 'stale-risk.json'
    risk_path.write_text(json.dumps({'daily_realized_pnl_usd': -18.564, 'consecutive_losses': 3, 'trades_last_hour': 6, 'current_capital_usd': 981.0}), encoding='utf-8')

    result = run_market_worker(
        cfg,
        ticker='KXBTC15M-TEST-15',
        max_runtime_seconds=0,
        poll_seconds=0.1,
        risk_json=str(risk_path),
        artifact_dir=str(tmp_path / 'run-artifacts'),
        clean_start=True,
    )

    risk_payload = json.loads(risk_path.read_text(encoding='utf-8'))
    assert risk_payload['daily_realized_pnl_usd'] == 0.0
    assert risk_payload['consecutive_losses'] == 0
    assert risk_payload['trades_last_hour'] == 0
    assert risk_payload['current_capital_usd'] == cfg.btc15m.initial_capital_usd
    assert result.current_capital_usd == cfg.btc15m.initial_capital_usd
