from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kalshi_cricket_tracker.config import AppConfig
from kalshi_cricket_tracker.execution.btc15m import BTC15mExecutionAgent, fetch_live_snapshot, load_risk_state
from kalshi_cricket_tracker.execution.kalshi import KalshiRestClient, MockKalshiPaperClient


@dataclass
class WorkerResult:
    ticker: str
    started_at: str
    finished_at: str
    polls: int
    decisions: int
    executed_trades: int
    realized_pnl_usd: float
    current_capital_usd: float
    summary_path: str
    learning_path: str


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_slug(value: str) -> str:
    return value.replace("/", "-")


def _market_dir(cfg: AppConfig, ticker: str) -> Path:
    return Path(cfg.runtime.artifact_dir) / "markets" / _safe_slug(ticker)


def finalize_market_run(cfg: AppConfig, ticker: str, root_artifact_dir: str | Path | None = None) -> tuple[Path, Path]:
    artifact_root = Path(root_artifact_dir or cfg.runtime.artifact_dir)
    market_dir = artifact_root / "markets" / _safe_slug(ticker)
    market_dir.mkdir(parents=True, exist_ok=True)

    trades = _read_jsonl(artifact_root / cfg.btc15m.executed_log_jsonl)
    decisions = _read_jsonl(artifact_root / cfg.btc15m.candidate_log_jsonl)
    state_trace = _read_jsonl(artifact_root / cfg.btc15m.state_log_jsonl)
    risk_state = _read_json(artifact_root / cfg.btc15m.risk_state_json)

    market_trades = [t for t in trades if t.get("ticker") == ticker]
    market_decisions = [d for d in decisions if d.get("ticker") == ticker]
    market_state = [s for s in state_trace if s.get("ticker") == ticker]

    realized = round(sum(float(t.get("pnl") or 0.0) for t in market_trades), 6)
    summary = {
        "ticker": ticker,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executed_trade_count": len(market_trades),
        "decision_count": len(market_decisions),
        "state_events": len(market_state),
        "realized_pnl_usd": realized,
        "current_capital_usd": risk_state.get("current_capital_usd"),
        "risk_state": risk_state,
    }
    summary_path = market_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    learning_lines = [
        f"# BTC15 market learning summary — {ticker}",
        "",
        f"- Decisions logged: {len(market_decisions)}",
        f"- Executed trades: {len(market_trades)}",
        f"- Realized PnL (USD): {realized}",
    ]
    if market_decisions:
        reasons: dict[str, int] = {}
        for d in market_decisions:
            reasons[d.get("reason", "unknown")] = reasons.get(d.get("reason", "unknown"), 0) + 1
        top_reasons = sorted(reasons.items(), key=lambda kv: kv[1], reverse=True)[:5]
        learning_lines.append("- Top decision reasons:")
        for reason, count in top_reasons:
            learning_lines.append(f"  - {count}x {reason}")
    learning_lines.append("")
    learning_lines.append("- Next tuning note: verify profit-target / forced-exit behavior against manual 10% principal rule.")
    learning_path = market_dir / "learning_note.md"
    learning_path.write_text("\n".join(learning_lines) + "\n", encoding="utf-8")

    return summary_path, learning_path


def run_market_worker(
    cfg: AppConfig,
    ticker: str | None = None,
    max_runtime_seconds: int = 900,
    poll_seconds: float = 2.0,
    risk_json: str | None = None,
) -> WorkerResult:
    artifact_root = Path(cfg.runtime.artifact_dir)
    artifact_root.mkdir(parents=True, exist_ok=True)
    client = KalshiRestClient.public(cfg.trading)
    snapshot = fetch_live_snapshot(client, ticker=ticker)
    market_ticker = snapshot.ticker
    started = datetime.now(timezone.utc)
    risk_path = Path(risk_json) if risk_json else artifact_root / cfg.btc15m.risk_state_json
    agent = BTC15mExecutionAgent(cfg.btc15m)
    paper_client = MockKalshiPaperClient()

    market_dir = _market_dir(cfg, market_ticker)
    market_dir.mkdir(parents=True, exist_ok=True)

    polls = 0
    while (datetime.now(timezone.utc) - started).total_seconds() < max_runtime_seconds:
        snapshot = fetch_live_snapshot(client, ticker=market_ticker)
        risk = load_risk_state(risk_path)
        decision = agent.evaluate(snapshot, risk)
        agent.execute_candidate(decision, client=paper_client, log_dir=artifact_root, live_enabled=False, risk=risk, persist_state_path=risk_path)
        polls += 1
        mins_left = snapshot.time_remaining.total_seconds() / 60.0
        if mins_left <= 0:
            break
        sleep_s = 1.0 if mins_left <= cfg.btc15m.max_time_to_close_min else poll_seconds
        time.sleep(max(0.5, sleep_s))

    summary_path, learning_path = finalize_market_run(cfg, market_ticker, artifact_root)
    try:
        import subprocess
        subprocess.run(
            [
                "python3",
                "scripts/build_dashboard_data.py",
                "--artifact-dir",
                str(artifact_root),
            ],
            cwd=Path(__file__).resolve().parents[3],
            check=False,
        )
    except Exception:
        pass

    trades = _read_jsonl(artifact_root / cfg.btc15m.executed_log_jsonl)
    market_trades = [t for t in trades if t.get("ticker") == market_ticker]
    realized = round(sum(float(t.get("pnl") or 0.0) for t in market_trades), 6)
    risk_state = _read_json(risk_path)
    return WorkerResult(
        ticker=market_ticker,
        started_at=started.isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        polls=polls,
        decisions=len([d for d in _read_jsonl(artifact_root / cfg.btc15m.candidate_log_jsonl) if d.get("ticker") == market_ticker]),
        executed_trades=len(market_trades),
        realized_pnl_usd=realized,
        current_capital_usd=float(risk_state.get("current_capital_usd", 0.0) or 0.0),
        summary_path=str(summary_path),
        learning_path=str(learning_path),
    )


def run_supervisor(cfg: AppConfig, markets: int = 1, poll_seconds: float = 2.0, max_runtime_seconds: int = 900) -> list[WorkerResult]:
    results: list[WorkerResult] = []
    seen: set[str] = set()
    client = KalshiRestClient.public(cfg.trading)
    while len(results) < markets:
        snapshot = fetch_live_snapshot(client)
        ticker = snapshot.ticker
        if ticker in seen:
            time.sleep(max(1.0, poll_seconds))
            continue
        seen.add(ticker)
        results.append(run_market_worker(cfg, ticker=ticker, max_runtime_seconds=max_runtime_seconds, poll_seconds=poll_seconds))
    return results
