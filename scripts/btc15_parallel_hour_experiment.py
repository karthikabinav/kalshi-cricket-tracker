from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kalshi_cricket_tracker.config import load_config
from kalshi_cricket_tracker.execution.btc15m import fetch_live_snapshot
from kalshi_cricket_tracker.execution.btc15m_lifecycle import wait_for_market_snapshot
from kalshi_cricket_tracker.execution.kalshi import KalshiRestClient


@dataclass
class RunHandle:
    ticker: str
    run_id: int
    artifact_dir: Path
    risk_json: Path
    log_path: Path
    process: subprocess.Popen[str]
    started_at: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_close_label(close_time: datetime) -> str:
    return close_time.strftime("%Y%m%dT%H%MZ")


def summarize_market_run(run: RunHandle) -> dict[str, Any]:
    summary_path = run.artifact_dir / "markets" / run.ticker / "summary.json"
    payload: dict[str, Any] = {
        "ticker": run.ticker,
        "run_id": run.run_id,
        "artifact_dir": str(run.artifact_dir),
        "risk_json": str(run.risk_json),
        "log_path": str(run.log_path),
        "started_at": run.started_at,
        "exit_code": run.process.returncode,
        "summary_path": str(summary_path),
    }
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "realized_pnl_usd": summary.get("realized_pnl_usd"),
                "executed_trade_count": summary.get("executed_trade_count"),
                "decision_count": summary.get("decision_count"),
                "current_capital_usd": summary.get("current_capital_usd"),
            }
        )
    return payload


def build_scoreboard(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    scoreboard: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(results, key=lambda item: (item["ticker"], item["run_id"])):
        scoreboard.setdefault(row["ticker"], []).append(
            {
                "run_id": row["run_id"],
                "pnl_usd": row.get("realized_pnl_usd"),
                "trade_count": row.get("executed_trade_count"),
                "ending_capital_usd": row.get("current_capital_usd"),
                "exit_code": row.get("exit_code"),
            }
        )
    return scoreboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch 3 isolated paper BTC15 runs per market over the next hour.")
    parser.add_argument("--config", default="configs/btc15m_paper.yaml")
    parser.add_argument("--markets", type=int, default=4, help="How many sequential BTC15 markets to cover.")
    parser.add_argument("--parallel-runs", type=int, default=3, help="How many isolated runs per market.")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--max-runtime-seconds", type=int, default=1200)
    parser.add_argument("--discovery-timeout-seconds", type=int, default=1800)
    parser.add_argument("--start-with-current-market", action="store_true", help="Attach to the current earliest open market instead of waiting for the next market first.")
    parser.add_argument("--experiment-root", default=None, help="Optional explicit artifact root for this experiment.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    client = KalshiRestClient.public(cfg.trading)

    started_at = utc_now()
    experiment_root = Path(args.experiment_root) if args.experiment_root else ROOT / "artifacts" / "experiments" / f"btc15-hour-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    experiment_root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "started_at": started_at.isoformat(),
        "config": args.config,
        "markets": args.markets,
        "parallel_runs": args.parallel_runs,
        "poll_seconds": args.poll_seconds,
        "max_runtime_seconds": args.max_runtime_seconds,
        "discovery_timeout_seconds": args.discovery_timeout_seconds,
        "start_with_current_market": args.start_with_current_market,
        "experiment_root": str(experiment_root),
        "launches": [],
        "results": [],
    }
    manifest_path = experiment_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    after_close_time = None
    seen: set[str] = set()
    if not args.start_with_current_market:
        anchor = wait_for_market_snapshot(cfg, client, poll_seconds=args.poll_seconds, max_wait_seconds=args.discovery_timeout_seconds)
        seen.add(anchor.ticker)
        after_close_time = anchor.close_time
        manifest["anchor_market"] = {"ticker": anchor.ticker, "close_time": anchor.close_time.isoformat()}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    all_results: list[dict[str, Any]] = []

    for market_index in range(args.markets):
        snapshot = wait_for_market_snapshot(
            cfg,
            client,
            after_close_time=after_close_time,
            exclude_tickers=seen,
            poll_seconds=args.poll_seconds,
            max_wait_seconds=args.discovery_timeout_seconds,
        )
        seen.add(snapshot.ticker)
        after_close_time = snapshot.close_time

        market_dir = experiment_root / safe_close_label(snapshot.close_time) / snapshot.ticker
        market_dir.mkdir(parents=True, exist_ok=True)
        handles: list[RunHandle] = []
        for run_id in range(1, args.parallel_runs + 1):
            run_dir = market_dir / f"run{run_id}"
            artifact_dir = run_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            risk_json = run_dir / "risk_state.json"
            log_path = run_dir / "run.log"
            cmd = [
                str(ROOT / ".venv" / "bin" / "python"),
                "-m",
                "kalshi_cricket_tracker.cli",
                "btc15m-paper-run-market",
                "--config",
                args.config,
                "--ticker",
                snapshot.ticker,
                "--max-runtime-seconds",
                str(args.max_runtime_seconds),
                "--poll-seconds",
                str(args.poll_seconds),
                "--artifact-dir",
                str(artifact_dir),
                "--risk-json",
                str(risk_json),
                "--clean-start",
            ]
            with log_path.open("w", encoding="utf-8") as log_fh:
                proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log_fh, stderr=subprocess.STDOUT, text=True)
            handle = RunHandle(
                ticker=snapshot.ticker,
                run_id=run_id,
                artifact_dir=artifact_dir,
                risk_json=risk_json,
                log_path=log_path,
                process=proc,
                started_at=utc_now().isoformat(),
            )
            handles.append(handle)
            manifest["launches"].append(
                {
                    "ticker": snapshot.ticker,
                    "close_time": snapshot.close_time.isoformat(),
                    "run_id": run_id,
                    "artifact_dir": str(artifact_dir),
                    "risk_json": str(risk_json),
                    "log_path": str(log_path),
                    "pid": proc.pid,
                    "command": cmd,
                }
            )
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        for handle in handles:
            handle.process.wait()
            result = summarize_market_run(handle)
            all_results.append(result)
            manifest["results"] = all_results
            manifest["scoreboard"] = build_scoreboard(all_results)
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({
        "experiment_root": str(experiment_root),
        "manifest_path": str(manifest_path),
        "scoreboard": build_scoreboard(all_results),
    }, indent=2))


if __name__ == "__main__":
    main()
