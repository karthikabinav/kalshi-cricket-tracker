from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


Side = Literal["YES", "NO"]
Action = Literal["OPEN_YES", "OPEN_NO", "CLOSE_YES", "CLOSE_NO", "HOLD"]


@dataclass
class OpenPosition:
    event_id: str
    side: Side
    entry_prob: float
    entry_ts: pd.Timestamp
    stake_usd: float


@dataclass
class ArbConfig:
    entry_edge_bps: float = 250.0
    exit_edge_bps: float = 40.0
    take_profit_bps: float = 120.0
    stop_loss_bps: float = 150.0
    max_holding_minutes: int = 180


def _edge_bps(model_prob_team1: float, market_prob_team1: float) -> float:
    return (float(model_prob_team1) - float(market_prob_team1)) * 10000.0


def decide_action(
    event_id: str,
    ts: pd.Timestamp,
    model_prob_team1: float,
    market_prob_team1: float,
    cfg: ArbConfig,
    position: OpenPosition | None,
) -> tuple[Action, dict]:
    edge_bps = _edge_bps(model_prob_team1, market_prob_team1)

    if position is None:
        if edge_bps >= cfg.entry_edge_bps:
            return "OPEN_YES", {"edge_bps": edge_bps, "reason": "underpriced_yes"}
        if -edge_bps >= cfg.entry_edge_bps:
            return "OPEN_NO", {"edge_bps": edge_bps, "reason": "overpriced_yes"}
        return "HOLD", {"edge_bps": edge_bps, "reason": "no_edge"}

    hold_mins = (ts - position.entry_ts).total_seconds() / 60.0
    if position.side == "YES":
        pnl_bps = (market_prob_team1 - position.entry_prob) * 10000.0
        close_for_edge = edge_bps <= cfg.exit_edge_bps
        if pnl_bps >= cfg.take_profit_bps:
            return "CLOSE_YES", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "take_profit"}
        if pnl_bps <= -cfg.stop_loss_bps:
            return "CLOSE_YES", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "stop_loss"}
        if hold_mins >= cfg.max_holding_minutes:
            return "CLOSE_YES", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "max_holding"}
        if close_for_edge:
            return "CLOSE_YES", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "edge_normalized"}
        return "HOLD", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "hold_yes"}

    pnl_bps = (position.entry_prob - market_prob_team1) * 10000.0
    close_for_edge = -edge_bps <= cfg.exit_edge_bps
    if pnl_bps >= cfg.take_profit_bps:
        return "CLOSE_NO", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "take_profit"}
    if pnl_bps <= -cfg.stop_loss_bps:
        return "CLOSE_NO", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "stop_loss"}
    if hold_mins >= cfg.max_holding_minutes:
        return "CLOSE_NO", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "max_holding"}
    if close_for_edge:
        return "CLOSE_NO", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "edge_normalized"}
    return "HOLD", {"edge_bps": edge_bps, "pnl_bps": pnl_bps, "reason": "hold_no"}


def backtest_from_snapshots(snapshots: pd.DataFrame, cfg: ArbConfig, stake_usd: float = 100.0) -> tuple[pd.DataFrame, dict]:
    required = {"ts", "event_id", "model_prob_team1", "market_prob_team1"}
    missing = required - set(snapshots.columns)
    if missing:
        raise ValueError(f"Snapshot data missing columns: {sorted(missing)}")

    df = snapshots.copy()
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    df = df.dropna(subset=["ts", "event_id", "model_prob_team1", "market_prob_team1"]).sort_values(["event_id", "ts"])

    positions: dict[str, OpenPosition] = {}
    trades: list[dict] = []

    for _, row in df.iterrows():
        event_id = str(row["event_id"])
        ts = row["ts"]
        model_p = float(row["model_prob_team1"])
        market_p = float(row["market_prob_team1"])
        position = positions.get(event_id)

        action, meta = decide_action(event_id, ts, model_p, market_p, cfg, position)
        if action == "OPEN_YES":
            positions[event_id] = OpenPosition(event_id=event_id, side="YES", entry_prob=market_p, entry_ts=ts, stake_usd=stake_usd)
            trades.append({"ts": ts, "event_id": event_id, "action": action, "price": market_p, **meta})
        elif action == "OPEN_NO":
            positions[event_id] = OpenPosition(event_id=event_id, side="NO", entry_prob=market_p, entry_ts=ts, stake_usd=stake_usd)
            trades.append({"ts": ts, "event_id": event_id, "action": action, "price": market_p, **meta})
        elif action in {"CLOSE_YES", "CLOSE_NO"} and position is not None:
            pnl_bps = float(meta.get("pnl_bps", 0.0))
            pnl_usd = position.stake_usd * (pnl_bps / 10000.0)
            trades.append(
                {
                    "ts": ts,
                    "event_id": event_id,
                    "action": action,
                    "price": market_p,
                    "entry_price": position.entry_prob,
                    "stake_usd": position.stake_usd,
                    "pnl_bps": pnl_bps,
                    "pnl_usd": pnl_usd,
                    **meta,
                }
            )
            positions.pop(event_id, None)

    trades_df = pd.DataFrame(trades)
    closes = trades_df[trades_df["action"].isin(["CLOSE_YES", "CLOSE_NO"])] if not trades_df.empty else trades_df
    total_pnl = float(closes["pnl_usd"].sum()) if not closes.empty else 0.0
    win_rate = float((closes["pnl_usd"] > 0).mean()) if not closes.empty else 0.0

    metrics = {
        "closed_trades": int(len(closes)),
        "total_pnl_usd": total_pnl,
        "avg_pnl_usd": float(closes["pnl_usd"].mean()) if not closes.empty else 0.0,
        "win_rate": win_rate,
        "open_positions_end": int(len(positions)),
    }
    return trades_df, metrics
