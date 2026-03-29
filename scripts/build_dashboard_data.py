from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS = ROOT / "artifacts"
OUT = ROOT / "dashboard" / "data" / "dashboard-data.json"
INITIAL_CAPITAL_USD = 100.0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def parse_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def volume_usd(trade: dict[str, Any]) -> float:
    raw = trade.get("raw_response") or {}
    stake = parse_float(raw.get("stake_usd"))
    if stake is not None:
        return stake
    size = parse_float(trade.get("filled_size")) or 0.0
    limit_price = parse_float(trade.get("limit_price")) or 0.0
    return round(size * limit_price / 100.0, 4)


def normalize_trade(trade: dict[str, Any]) -> dict[str, Any]:
    pnl = parse_float(trade.get("pnl"))
    exit_price = parse_float(trade.get("exit_price"))
    status = "OPEN" if pnl is None and exit_price is None else "CLOSED"
    return {
        "entryTime": trade.get("entry_time"),
        "ticker": trade.get("ticker"),
        "side": trade.get("side"),
        "limitPriceCents": parse_float(trade.get("limit_price")),
        "filledSize": parse_float(trade.get("filled_size")),
        "fillQuality": trade.get("fill_quality"),
        "exitPriceCents": exit_price,
        "pnlUsd": pnl,
        "status": status,
        "classification": trade.get("classification"),
        "volumeUsd": volume_usd(trade),
    }


def normalize_decision(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "loggedAt": row.get("logged_at"),
        "decision": row.get("decision"),
        "ticker": row.get("ticker"),
        "side": row.get("side"),
        "confidence": row.get("confidence"),
        "reason": row.get("reason"),
        "timeRemainingMin": row.get("time_remaining_min"),
        "expectedEdgeCents": row.get("expected_edge_cents"),
    }


def sort_key(ts: str | None) -> tuple[int, str]:
    if not ts:
        return (1, "")
    return (0, ts)


def to_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def hourly_average_pnl(realized: list[dict[str, Any]]) -> float | None:
    if not realized:
        return None
    times = [to_dt(t.get("entryTime")) for t in realized]
    times = [t for t in times if t is not None]
    if not times:
        return None
    span_hours = max((max(times) - min(times)).total_seconds() / 3600.0, 1.0)
    total = sum(float(t["pnlUsd"]) for t in realized)
    return round(total / span_hours, 4)


def current_capital_usd(realized_total: float, risk_state: dict[str, Any] | None) -> float:
    if risk_state:
        capital = parse_float(risk_state.get("current_capital_usd"))
        if capital is not None:
            return round(capital, 4)
    return round(INITIAL_CAPITAL_USD + realized_total, 4)


def build_payload(artifact_dir: Path = DEFAULT_ARTIFACTS) -> dict[str, Any]:
    executed_trades = [normalize_trade(r) for r in read_jsonl(artifact_dir / "btc15m_executed_trades.jsonl")]
    decisions = [normalize_decision(r) for r in read_jsonl(artifact_dir / "btc15m_candidate_decisions.jsonl")]
    state_trace = read_jsonl(artifact_dir / "btc15m_state_trace.jsonl")
    risk_state = read_json(artifact_dir / "btc15m_risk_state.json")
    _paper_fills = read_csv_rows(artifact_dir / "paper_fills.csv")

    executed_trades.sort(key=lambda row: sort_key(row.get("entryTime")), reverse=True)
    decisions.sort(key=lambda row: sort_key(row.get("loggedAt")), reverse=True)

    realized = [t for t in executed_trades if t.get("pnlUsd") is not None]
    realized_total = round(sum(float(t["pnlUsd"]) for t in realized), 4)
    total_volume = round(sum(float(t.get("volumeUsd") or 0.0) for t in executed_trades), 4)
    open_count = sum(1 for t in executed_trades if t.get("status") == "OPEN")
    closed_count = sum(1 for t in executed_trades if t.get("status") == "CLOSED")
    hourly_avg_pnl = hourly_average_pnl(realized)
    capital_now = current_capital_usd(realized_total, risk_state)
    hourly_avg_trades = round(len(executed_trades) / max(1.0, ((max([to_dt(t.get("entryTime")) for t in executed_trades if to_dt(t.get("entryTime"))] or [datetime.now(timezone.utc)]) - min([to_dt(t.get("entryTime")) for t in executed_trades if to_dt(t.get("entryTime"))] or [datetime.now(timezone.utc)])).total_seconds() / 3600.0 or 1.0)), 4) if executed_trades else None

    cumulative = 0.0
    pnl_series = []
    for trade in sorted(realized, key=lambda row: sort_key(row.get("entryTime"))):
        cumulative += float(trade["pnlUsd"])
        pnl_series.append({"at": trade.get("entryTime"), "cumulativePnlUsd": round(cumulative, 4), "ticker": trade.get("ticker")})

    assumptions = [
        f"Current capital uses `{artifact_dir / 'btc15m_risk_state.json'}` when present; otherwise it falls back to initial capital plus realized PnL.",
        "Overall PnL is realized-only: numeric `pnl` values from `btc15m_executed_trades.jsonl` are summed, while null/unknown values remain open/unrealized.",
        "Hourly average PnL is realized PnL divided by observed realized-trade time span in hours, floored at 1 hour to avoid noisy division.",
        "Transaction volume uses `raw_response.stake_usd` when present; otherwise it falls back to `filled_size * limit_price / 100`.",
        "The payload is a static snapshot generated at build time, so Vercel serves the last exported artifact state rather than reading live logs at runtime.",
    ]

    latest_state = state_trace[-1] if state_trace else None

    return {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "dataSource": str(artifact_dir),
            "artifactFiles": [
                str(artifact_dir / "btc15m_executed_trades.jsonl"),
                str(artifact_dir / "btc15m_candidate_decisions.jsonl"),
                str(artifact_dir / "btc15m_risk_state.json"),
                str(artifact_dir / "btc15m_state_trace.jsonl"),
                str(artifact_dir / "paper_fills.csv"),
            ],
        },
        "summary": {
            "currentCapitalUsd": capital_now,
            "overallPnlUsd": realized_total,
            "hourlyAveragePnlUsd": hourly_avg_pnl,
            "hourlyAverageTrades": hourly_avg_trades,
            "realizedPnlUsd": realized_total,
            "totalTransactionVolumeUsd": total_volume,
            "executedTradeCount": len(executed_trades),
            "openTradeCount": open_count,
            "closedTradeCount": closed_count,
            "tradesWithRealizedPnl": len(realized),
            "lastDecision": decisions[0] if decisions else None,
            "latestState": latest_state,
        },
        "assumptions": assumptions,
        "trades": executed_trades,
        "decisions": decisions[:8],
        "pnlSeries": pnl_series,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dashboard payload from BTC15 paper artifacts.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACTS), help="Artifact directory to read from.")
    parser.add_argument("--out", default=str(OUT), help="Output JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir)
    out = Path(args.out)
    payload = build_payload(artifact_dir=artifact_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
