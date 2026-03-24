from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from kalshi_cricket_tracker.config import BTC15mExecConfig
from kalshi_cricket_tracker.execution.kalshi import KalshiClientInterface, KalshiOrder


@dataclass
class OrderBookLevel:
    price: int
    size: int


@dataclass
class BTC15mMarketSnapshot:
    ticker: str
    rules: str
    status: str
    close_time: datetime
    yes_ask_cents: int
    yes_bid_cents: int
    no_ask_cents: int
    no_bid_cents: int
    best_yes_ask_size: int
    best_yes_bid_size: int
    best_no_ask_size: int
    best_no_bid_size: int
    orderbook_stability_bps: float
    btc_spot: float | None = None
    thesis_price_cents: int | None = None
    metadata: dict[str, Any] | None = None

    @property
    def time_remaining(self) -> timedelta:
        return self.close_time - datetime.now(timezone.utc)

    @property
    def spread_cents(self) -> int:
        return max(self.yes_ask_cents - self.yes_bid_cents, self.no_ask_cents - self.no_bid_cents)

    @property
    def min_depth(self) -> int:
        return min(
            self.best_yes_ask_size,
            self.best_yes_bid_size,
            self.best_no_ask_size,
            self.best_no_bid_size,
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BTC15mMarketSnapshot":
        close_time = raw["close_time"]
        if isinstance(close_time, str):
            close_time = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
        return cls(
            ticker=raw["ticker"],
            rules=raw.get("rules", ""),
            status=raw["status"],
            close_time=close_time,
            yes_ask_cents=int(raw["yes_ask_cents"]),
            yes_bid_cents=int(raw["yes_bid_cents"]),
            no_ask_cents=int(raw["no_ask_cents"]),
            no_bid_cents=int(raw["no_bid_cents"]),
            best_yes_ask_size=int(raw["best_yes_ask_size"]),
            best_yes_bid_size=int(raw["best_yes_bid_size"]),
            best_no_ask_size=int(raw["best_no_ask_size"]),
            best_no_bid_size=int(raw["best_no_bid_size"]),
            orderbook_stability_bps=float(raw.get("orderbook_stability_bps", 0.0)),
            btc_spot=float(raw["btc_spot"]) if raw.get("btc_spot") is not None else None,
            thesis_price_cents=int(raw["thesis_price_cents"]) if raw.get("thesis_price_cents") is not None else None,
            metadata=raw.get("metadata"),
        )


@dataclass
class RiskState:
    daily_realized_pnl_usd: float = 0.0
    consecutive_losses: int = 0
    trades_last_hour: int = 0
    open_positions: int = 0
    two_consecutive_bad_slippage: bool = False


@dataclass
class CandidateDecision:
    decision: Literal["TRADE", "NO TRADE"]
    ticker: str
    side: Literal["YES", "NO", "NONE"]
    confidence: int
    reason: str
    time_remaining_min: float
    orderbook_summary: dict[str, Any]
    planned_entry_cents: int | None
    planned_profit_take_cents: int | None
    invalidation: str
    expected_edge_cents: int | None

    def render(self) -> str:
        if self.decision == "NO TRADE":
            return f"NO TRADE\nReason: {self.reason}\nConfidence: {self.confidence}"
        return (
            f"TRADE\n"
            f"Ticker: {self.ticker}\n"
            f"Side: {self.side}\n"
            f"Entry limit: {self.planned_entry_cents}\n"
            f"Size: 1\n"
            f"Profit-take plan: Exit if price improves to {self.planned_profit_take_cents}c or earlier if thesis/clock weakens\n"
            f"Invalidation / stop: {self.invalidation}\n"
            f"Why now: {self.reason}\n"
            f"Confidence: {self.confidence}"
        )


class BTC15mExecutionAgent:
    def __init__(self, cfg: BTC15mExecConfig):
        self.cfg = cfg

    def evaluate(self, snapshot: BTC15mMarketSnapshot, risk: RiskState) -> CandidateDecision:
        summary = {
            "yes_bid": snapshot.yes_bid_cents,
            "yes_ask": snapshot.yes_ask_cents,
            "no_bid": snapshot.no_bid_cents,
            "no_ask": snapshot.no_ask_cents,
            "spread_cents": snapshot.spread_cents,
            "min_depth": snapshot.min_depth,
            "stability_bps": snapshot.orderbook_stability_bps,
        }
        mins_left = snapshot.time_remaining.total_seconds() / 60.0

        def abstain(reason: str, confidence: int = 0) -> CandidateDecision:
            return CandidateDecision(
                decision="NO TRADE",
                ticker=snapshot.ticker,
                side="NONE",
                confidence=max(0, min(100, confidence)),
                reason=reason,
                time_remaining_min=round(mins_left, 2),
                orderbook_summary=summary,
                planned_entry_cents=None,
                planned_profit_take_cents=None,
                invalidation="Abstain",
                expected_edge_cents=None,
            )

        if self.cfg.enabled is False:
            return abstain("BTC 15m execution agent disabled in config; safe default is abstain.")
        if "BTC" not in snapshot.ticker.upper():
            return abstain("Ticker is not a BTC market.")
        if not any(token in snapshot.ticker.upper() for token in ("15M", "15MIN", "T15")):
            return abstain("Ticker does not look like a BTC 15-minute market.")
        if not snapshot.rules.strip():
            return abstain("Market rules missing or empty.")
        if snapshot.status.lower() not in {"open", "active", "trading"}:
            return abstain(f"Market status is {snapshot.status!r}, not open/tradable.")
        if mins_left <= self.cfg.min_time_to_close_min:
            return abstain("Too close to resolution; late-entry chaos filter triggered.")
        if mins_left > self.cfg.max_time_to_close_min:
            return abstain("Too early for the intended BTC 15m entry window.")
        if snapshot.spread_cents > self.cfg.max_spread_cents:
            return abstain("Spread too wide for controlled entry.")
        if snapshot.min_depth < self.cfg.min_depth_contracts:
            return abstain("Insufficient top-of-book depth.")
        if snapshot.orderbook_stability_bps > self.cfg.max_orderbook_instability_bps:
            return abstain("Order book is unstable / repricing too fast.")
        if risk.open_positions >= self.cfg.max_simultaneous_positions:
            return abstain("Max simultaneous position limit already reached.")
        if risk.daily_realized_pnl_usd <= -abs(self.cfg.max_daily_loss_usd):
            return abstain("Daily loss limit already hit.")
        if risk.consecutive_losses >= self.cfg.max_consecutive_losses:
            return abstain("Consecutive loss stop triggered.")
        if risk.trades_last_hour >= self.cfg.max_trades_per_hour:
            return abstain("Hourly trade limit reached.")
        if risk.two_consecutive_bad_slippage:
            return abstain("Recent slippage stop triggered.")
        if snapshot.thesis_price_cents is None:
            return abstain("No thesis price supplied; cannot identify a likely winning leg safely.")

        yes_edge = snapshot.thesis_price_cents - snapshot.yes_ask_cents
        no_theory = 100 - snapshot.thesis_price_cents
        no_edge = no_theory - snapshot.no_ask_cents
        side = "YES" if yes_edge >= no_edge else "NO"
        chosen_edge = yes_edge if side == "YES" else no_edge
        entry = snapshot.yes_ask_cents if side == "YES" else snapshot.no_ask_cents

        if chosen_edge < self.cfg.min_edge_cents:
            return abstain("Estimated edge is below threshold.", confidence=max(0, chosen_edge * 5))

        confidence = int(max(0, min(100, chosen_edge * 5 + (mins_left - self.cfg.min_time_to_close_min) * 2)))
        if confidence < self.cfg.min_confidence:
            return abstain("Confidence below minimum threshold.", confidence=confidence)

        reward_cents = min(self.cfg.target_take_profit_cents, max(1, chosen_edge - 1))
        planned_profit = min(99, entry + reward_cents)
        if reward_cents < self.cfg.min_reward_cents:
            return abstain("Reward-to-risk not attractive enough after spread and timing filters.", confidence=confidence)

        reason = (
            f"{side} leg has {chosen_edge}c estimated edge with {mins_left:.1f} minutes left, "
            f"{snapshot.spread_cents}c spread, depth {snapshot.min_depth}, and stable book."
        )
        invalidation = (
            f"Exit/avoid if edge compresses below {self.cfg.exit_edge_cents}c, spread widens above "
            f"{self.cfg.max_spread_cents}c, or time remaining falls below {self.cfg.min_time_to_close_min}m."
        )
        return CandidateDecision(
            decision="TRADE",
            ticker=snapshot.ticker,
            side=side,
            confidence=confidence,
            reason=reason,
            time_remaining_min=round(mins_left, 2),
            orderbook_summary=summary,
            planned_entry_cents=entry,
            planned_profit_take_cents=planned_profit,
            invalidation=invalidation,
            expected_edge_cents=chosen_edge,
        )

    def execute_candidate(
        self,
        decision: CandidateDecision,
        client: KalshiClientInterface,
        log_dir: str | Path,
        live_enabled: bool,
    ) -> dict[str, Any] | None:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        _append_jsonl(log_path / self.cfg.candidate_log_jsonl, {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            **asdict(decision),
        })
        if decision.decision != "TRADE":
            return None
        order = KalshiOrder(
            event_ticker=decision.ticker,
            side=decision.side,
            stake_usd=float(self.cfg.max_dollars_per_trade),
            limit_price=float(decision.planned_entry_cents) / 100.0,
        )
        response = client.place_order(order)
        trade_log = {
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "ticker": decision.ticker,
            "side": decision.side,
            "limit_price": decision.planned_entry_cents,
            "filled_size": response.get("count", 1),
            "fill_quality": response.get("status", "PAPER_PLACED" if not live_enabled else "LIVE_SENT"),
            "exit_price": None,
            "pnl": None,
            "classification": "paper_trade" if not live_enabled else "pending_review",
            "raw_response": response,
        }
        _append_jsonl(log_path / self.cfg.executed_log_jsonl, trade_log)
        return trade_log


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")


def load_snapshot(path: str | Path) -> BTC15mMarketSnapshot:
    return BTC15mMarketSnapshot.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def load_risk_state(path: str | Path | None) -> RiskState:
    if path is None:
        return RiskState()
    p = Path(path)
    if not p.exists():
        return RiskState()
    return RiskState(**json.loads(p.read_text(encoding="utf-8")))
