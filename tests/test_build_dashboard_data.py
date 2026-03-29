from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_dashboard_data", ROOT / "scripts" / "build_dashboard_data.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_payload = MODULE.build_payload


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_build_payload_uses_explicit_artifact_dir(tmp_path: Path):
    isolated = tmp_path / "isolated"
    isolated.mkdir()

    _write_jsonl(
        isolated / "btc15m_executed_trades.jsonl",
        [
            {
                "entry_time": "2026-03-29T00:00:00+00:00",
                "ticker": "KXBTC15M-ISO-15",
                "side": "YES",
                "limit_price": 60,
                "filled_size": 1,
                "fill_quality": "FILLED",
                "exit_price": 62,
                "pnl": 2.5,
                "classification": "paper_trade",
                "raw_response": {"stake_usd": 100.0},
            }
        ],
    )
    _write_jsonl(
        isolated / "btc15m_candidate_decisions.jsonl",
        [
            {
                "logged_at": "2026-03-29T00:00:00+00:00",
                "decision": "TRADE",
                "ticker": "KXBTC15M-ISO-15",
                "side": "YES",
                "confidence": 80,
                "reason": "isolated-test",
                "time_remaining_min": 8,
                "expected_edge_cents": 3,
            }
        ],
    )
    _write_jsonl(
        isolated / "btc15m_state_trace.jsonl",
        [{"logged_at": "2026-03-29T00:00:00+00:00", "ticker": "KXBTC15M-ISO-15", "decision": "TRADE"}],
    )
    (isolated / "btc15m_risk_state.json").write_text(json.dumps({"current_capital_usd": 123.45}), encoding="utf-8")

    payload = build_payload(artifact_dir=isolated)

    assert payload["summary"]["currentCapitalUsd"] == 123.45
    assert payload["summary"]["overallPnlUsd"] == 2.5
    assert payload["trades"][0]["ticker"] == "KXBTC15M-ISO-15"
    assert payload["meta"]["dataSource"] == str(isolated)
    assert payload["meta"]["artifactFiles"][0].startswith(str(isolated))
