from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
OUT = ROOT / "dashboard" / "data" / "dashboard-data.json"


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


def build_payload() -> dict[str, Any]:
    executed_trades = [normalize_trade(r) for r in read_jsonl(ARTIFACTS / "btc15m_executed_trades.jsonl")]
    decisions = [normalize_decision(r) for r in read_jsonl(ARTIFACTS / "btc15m_candidate_decisions.jsonl")]
    _paper_fills = read_csv_rows(ARTIFACTS / "paper_fills.csv")

    executed_trades.sort(key=lambda row: sort_key(row.get("entryTime")), reverse=True)
    decisions.sort(key=lambda row: sort_key(row.get("loggedAt")), reverse=True)

    realized = [t for t in executed_trades if t.get("pnlUsd") is not None]
    realized_total = round(sum(float(t["pnlUsd"]) for t in realized), 4)
    total_volume = round(sum(float(t.get("volumeUsd") or 0.0) for t in executed_trades), 4)
    open_count = sum(1 for t in executed_trades if t.get("status") == "OPEN")
    closed_count = sum(1 for t in executed_trades if t.get("status") == "CLOSED")

    cumulative = 0.0
    pnl_series = []
    for trade in sorted(realized, key=lambda row: sort_key(row.get("entryTime"))):
        cumulative += float(trade["pnlUsd"])
        pnl_series.append({"at": trade.get("entryTime"), "cumulativePnlUsd": round(cumulative, 4), "ticker": trade.get("ticker")})

    assumptions = [
        "PnL is realized-only: the dashboard sums numeric `pnl` values from `btc15m_executed_trades.jsonl` and excludes null/unknown values.",
        "Transaction volume uses `raw_response.stake_usd` when present; otherwise it falls back to `filled_size * limit_price / 100`.",
        "Trades with null `pnl` and null `exit_price` are labeled OPEN; everything else is treated as CLOSED for UI purposes.",
        "Decision context is sourced from `btc15m_candidate_decisions.jsonl`; it is informational and separate from executed trade accounting.",
        "The payload is a static snapshot generated at build time, so Vercel serves the last exported artifact state rather than reading live logs at runtime.",
    ]

    return {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "dataSource": "repo artifacts",
            "artifactFiles": [
                "artifacts/btc15m_executed_trades.jsonl",
                "artifacts/btc15m_candidate_decisions.jsonl",
                "artifacts/paper_fills.csv",
            ],
        },
        "summary": {
            "realizedPnlUsd": realized_total,
            "totalTransactionVolumeUsd": total_volume,
            "executedTradeCount": len(executed_trades),
            "openTradeCount": open_count,
            "closedTradeCount": closed_count,
            "tradesWithRealizedPnl": len(realized),
            "lastDecision": decisions[0] if decisions else None,
        },
        "assumptions": assumptions,
        "trades": executed_trades[:25],
        "decisions": decisions[:8],
        "pnlSeries": pnl_series,
    }


def main() -> None:
    payload = build_payload()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
