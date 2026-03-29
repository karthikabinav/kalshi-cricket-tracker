from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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
    realized_vol_bps: float | None = None
    microprice_cents: float | None = None
    orderbook_imbalance: float | None = None
    depth_contracts: int | None = None
    recent_trades_count: int | None = None
    recent_trade_buy_ratio: float | None = None
    settlement_signal_strength: float | None = None
    local_mean_reversion_zscore: float | None = None
    snapshot_sequence_id: str | None = None
    snapshot_index: int | None = None
    current_position_side: Literal["YES", "NO"] | None = None
    current_position_entry_cents: int | None = None
    metadata: dict[str, Any] | None = None

    @property
    def time_remaining(self) -> timedelta:
        return self.close_time - datetime.now(timezone.utc)

    @property
    def spread_cents(self) -> int:
        return max(self.yes_ask_cents - self.yes_bid_cents, self.no_ask_cents - self.no_bid_cents)

    @property
    def contract_price_cents(self) -> float:
        return (self.yes_bid_cents + self.yes_ask_cents) / 2.0

    @property
    def distance_from_target_cents(self) -> float | None:
        if self.thesis_price_cents is None:
            return None
        return float(self.thesis_price_cents) - self.contract_price_cents

    @property
    def min_depth(self) -> int:
        if self.depth_contracts is not None:
            return int(self.depth_contracts)
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
            realized_vol_bps=float(raw["realized_vol_bps"]) if raw.get("realized_vol_bps") is not None else None,
            microprice_cents=float(raw["microprice_cents"]) if raw.get("microprice_cents") is not None else None,
            orderbook_imbalance=float(raw["orderbook_imbalance"]) if raw.get("orderbook_imbalance") is not None else None,
            depth_contracts=int(raw["depth_contracts"]) if raw.get("depth_contracts") is not None else None,
            recent_trades_count=int(raw["recent_trades_count"]) if raw.get("recent_trades_count") is not None else None,
            recent_trade_buy_ratio=float(raw["recent_trade_buy_ratio"]) if raw.get("recent_trade_buy_ratio") is not None else None,
            settlement_signal_strength=float(raw["settlement_signal_strength"]) if raw.get("settlement_signal_strength") is not None else None,
            local_mean_reversion_zscore=float(raw["local_mean_reversion_zscore"]) if raw.get("local_mean_reversion_zscore") is not None else None,
            snapshot_sequence_id=raw.get("snapshot_sequence_id"),
            snapshot_index=int(raw["snapshot_index"]) if raw.get("snapshot_index") is not None else None,
            current_position_side=raw.get("current_position_side"),
            current_position_entry_cents=int(raw["current_position_entry_cents"]) if raw.get("current_position_entry_cents") is not None else None,
            metadata=raw.get("metadata"),
        )


@dataclass
class RiskState:
    daily_realized_pnl_usd: float = 0.0
    consecutive_losses: int = 0
    trades_last_hour: int = 0
    open_positions: int = 0
    two_consecutive_bad_slippage: bool = False
    current_capital_usd: float = 100.0
    reserved_capital_usd: float = 0.0
    recycled_capital_usd: float = 0.0
    inventory_state: Literal["FLAT", "LONG_YES", "LONG_NO"] = "FLAT"
    inventory_qty: int = 0
    entry_price_cents: float | None = None
    entry_notional_usd: float = 0.0
    realized_round_trip_pnl_usd: float = 0.0
    unrealized_pnl_usd: float = 0.0
    last_ticker: str | None = None
    updated_at: str | None = None
    last_btc_basis: float | None = None
    prev_btc_basis: float | None = None
    last_btc_slope: float | None = None



@dataclass
class EVEstimate:
    fair_prob: float
    tp_hit_prob: float
    stop_hit_prob: float
    expected_settlement_value: float
    gross_edge: float
    fees: float
    slippage: float
    net_ev: float
    recommended_size: int
    recommended_action: Literal["ENTER_LONG_YES", "ENTER_LONG_NO", "HOLD", "EXIT", "SKIP"]


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
    action: str = "skip"
    quantity: int = 0
    reward_cents: float | None = None
    cost_cents: float | None = None
    lagrangian_score: float | None = None
    fee_cents: float | None = None
    resulting_capital_usd: float | None = None
    realized_round_trip_pnl_usd: float | None = None
    unrealized_pnl_usd: float | None = None
    inventory_state_after: str | None = None
    state_context: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        if self.decision == "NO TRADE":
            return f"NO TRADE\nReason: {self.reason}\nConfidence: {self.confidence}"
        return (
            f"TRADE\n"
            f"Ticker: {self.ticker}\n"
            f"Side: {self.side}\n"
            f"Action: {self.action}\n"
            f"Entry limit: {self.planned_entry_cents}\n"
            f"Size: {self.quantity or 1}\n"
            f"Profit-take plan: Exit if price improves to {self.planned_profit_take_cents}c or earlier if thesis/clock weakens\n"
            f"Invalidation / stop: {self.invalidation}\n"
            f"Why now: {self.reason}\n"
            f"Confidence: {self.confidence}"
        )


class BTC15mExecutionAgent:
    def __init__(self, cfg: BTC15mExecConfig):
        self.cfg = cfg

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _check_tradeable(self, snapshot: BTC15mMarketSnapshot, risk: RiskState) -> str | None:
        mins_left = snapshot.time_remaining.total_seconds() / 60.0
        if self.cfg.enabled is False:
            return "BTC 15m execution agent disabled in config; safe default is abstain."
        if "BTC" not in snapshot.ticker.upper():
            return "Ticker is not a BTC market."
        if not any(token in snapshot.ticker.upper() for token in ("15M", "15MIN", "T15", "-15")):
            return "Ticker does not look like a BTC 15-minute market."
        if not snapshot.rules.strip():
            return "Market rules missing or empty."
        if snapshot.status.lower() not in {"open", "active", "trading"}:
            return f"Market status is {snapshot.status!r}, not open/tradable."
        if mins_left <= self.cfg.min_time_to_close_min:
            return "Too close to resolution; no-entry final 3-minute window."
        if snapshot.spread_cents > self.cfg.max_spread_cents:
            return "Spread too wide for controlled entry."
        if snapshot.min_depth < self.cfg.min_depth_contracts:
            return "Insufficient top-of-book depth."
        if snapshot.orderbook_stability_bps > self.cfg.max_orderbook_instability_bps:
            return "Order book is unstable / repricing too fast."
        if risk.open_positions >= self.cfg.max_simultaneous_positions and snapshot.current_position_side is None and risk.inventory_state == "FLAT":
            return "Max simultaneous position limit already reached."
        if risk.daily_realized_pnl_usd <= -abs(self.cfg.max_daily_loss_usd):
            return "Daily loss limit already hit."
        if risk.consecutive_losses >= self.cfg.max_consecutive_losses:
            return "Consecutive loss stop triggered."
        if risk.trades_last_hour >= self.cfg.max_trades_per_hour:
            return "Hourly trade limit reached."
        if risk.two_consecutive_bad_slippage:
            return "Recent slippage stop triggered."
        return None

    def _estimate_standard_ev(self, snapshot: BTC15mMarketSnapshot, risk: RiskState) -> EVEstimate:
        blocked_reason = self._check_tradeable(snapshot, risk)
        mins_left = max(0.0, snapshot.time_remaining.total_seconds() / 60.0)
        yes_mid = snapshot.contract_price_cents
        micro = snapshot.microprice_cents if snapshot.microprice_cents is not None else yes_mid
        imbalance = snapshot.orderbook_imbalance if snapshot.orderbook_imbalance is not None else 0.0
        trade_buy_ratio = snapshot.recent_trade_buy_ratio if snapshot.recent_trade_buy_ratio is not None else 0.5
        settlement_signal = snapshot.settlement_signal_strength if snapshot.settlement_signal_strength is not None else 0.0
        realized_vol = snapshot.realized_vol_bps if snapshot.realized_vol_bps is not None else 50.0

        base_fair = snapshot.thesis_price_cents if snapshot.thesis_price_cents is not None else yes_mid
        fair_cents = (
            0.80 * base_fair
            + 0.10 * micro
            + 4.0 * imbalance
            + 3.0 * (trade_buy_ratio - 0.5)
            + 5.0 * settlement_signal
        )
        vol_penalty = min(8.0, realized_vol / 75.0)
        chaos_penalty = max(0.0, self.cfg.min_time_to_close_min + 0.15 - mins_left) * 20.0
        fair_cents = self._clamp(fair_cents - vol_penalty - chaos_penalty, 1.0, 99.0)
        fair_prob = fair_cents / 100.0

        yes_edge = fair_cents - snapshot.yes_ask_cents
        no_fair_cents = 100.0 - fair_cents
        no_edge = no_fair_cents - snapshot.no_ask_cents
        take_yes = yes_edge >= no_edge
        entry_cents = float(snapshot.yes_ask_cents if take_yes else snapshot.no_ask_cents)
        gross_edge = yes_edge if take_yes else no_edge

        maker_fraction = self._clamp(self.cfg.maker_fill_fraction, 0.0, 1.0)
        taker_fraction = 1.0 - maker_fraction
        half_spread = snapshot.spread_cents / 2.0
        raw_slippage = taker_fraction * (0.75 * half_spread + min(1.0, 25.0 / max(snapshot.min_depth, 1)))
        slippage = min(self.cfg.max_slippage_cents, raw_slippage)
        fees = 2.0 * self.cfg.fee_bps_per_side * entry_cents / 10000.0

        tp_bonus = max(0.0, gross_edge - self.cfg.target_take_profit_cents)
        stop_risk = max(0.0, self.cfg.stop_loss_cents - gross_edge)
        tp_hit_prob = self._clamp(0.45 + tp_bonus / 10.0 - realized_vol / 400.0 + max(imbalance, 0.0) / 2.0, 0.05, 0.95)
        stop_hit_prob = self._clamp(0.20 + stop_risk / 8.0 + realized_vol / 300.0 + max(-imbalance, 0.0) / 2.0, 0.05, 0.95)

        net_ev = gross_edge - fees - slippage - self.cfg.safety_buffer_cents
        bankroll_cap_contracts = max(1, int(self.cfg.max_dollars_per_trade / max(entry_cents / 100.0, 0.01)))
        edge_fraction = max(0.0, net_ev) / 100.0
        kelly_size = int(bankroll_cap_contracts * self.cfg.size_kelly_fraction * min(1.0, edge_fraction / 0.05))
        recommended_size = max(0, min(bankroll_cap_contracts, kelly_size))

        if blocked_reason is not None:
            action: Literal["ENTER_LONG_YES", "ENTER_LONG_NO", "HOLD", "EXIT", "SKIP"] = "EXIT" if snapshot.current_position_side else "SKIP"
        elif snapshot.current_position_side is not None:
            current_side = snapshot.current_position_side
            aligned = (current_side == "YES" and take_yes) or (current_side == "NO" and not take_yes)
            action = "HOLD" if aligned and net_ev >= 0 else "EXIT"
        elif net_ev < self.cfg.min_ev_to_trade_cents or recommended_size <= 0:
            action = "SKIP"
        else:
            action = "ENTER_LONG_YES" if take_yes else "ENTER_LONG_NO"

        return EVEstimate(
            fair_prob=round(fair_prob, 4),
            tp_hit_prob=round(tp_hit_prob, 4),
            stop_hit_prob=round(stop_hit_prob, 4),
            expected_settlement_value=round(fair_cents, 3),
            gross_edge=round(gross_edge, 3),
            fees=round(fees, 3),
            slippage=round(slippage, 3),
            net_ev=round(net_ev, 3),
            recommended_size=recommended_size,
            recommended_action=action,
        )

    def _capital_remaining(self, risk: RiskState) -> float:
        return max(0.0, risk.current_capital_usd - risk.reserved_capital_usd)

    def _manual_paper_enabled(self) -> bool:
        return bool(self.cfg.manual_paper_enabled or self.cfg.vol_bwk_enabled)

    def _current_btc_basis(self, snapshot: BTC15mMarketSnapshot) -> tuple[float, str]:
        if snapshot.btc_spot is not None:
            return float(snapshot.btc_spot), "btc_spot"
        return float(snapshot.contract_price_cents), "contract_price"

    def _btc_trend_metrics(self, snapshot: BTC15mMarketSnapshot, risk: RiskState) -> tuple[float | None, float | None, str]:
        current_basis, source = self._current_btc_basis(snapshot)
        if risk.last_btc_basis is None:
            return None, None, source
        slope = current_basis - risk.last_btc_basis
        acceleration = None if risk.last_btc_slope is None else slope - risk.last_btc_slope
        return slope, acceleration, source

    def _btc_trend_blocks_entry(self, side: Literal["YES", "NO"], snapshot: BTC15mMarketSnapshot, risk: RiskState) -> str | None:
        if not self.cfg.btc_trend_filter_enabled:
            return None
        slope, acceleration, source = self._btc_trend_metrics(snapshot, risk)
        if slope is None or acceleration is None:
            return None
        if source == "btc_spot":
            slope_threshold = self.cfg.btc_spot_slope_threshold
            acceleration_threshold = self.cfg.btc_spot_acceleration_threshold
            units = "USD"
        else:
            slope_threshold = self.cfg.contract_slope_threshold_cents
            acceleration_threshold = self.cfg.contract_acceleration_threshold_cents
            units = "c"
        against_yes = side == "YES" and slope >= slope_threshold and acceleration >= acceleration_threshold
        against_no = side == "NO" and slope <= -slope_threshold and acceleration <= -acceleration_threshold
        if against_yes or against_no:
            return (
                f"BTC trend filter blocked {side}: {source} slope {slope:.2f}{units} and "
                f"acceleration {acceleration:.2f}{units} still move against the mean-reversion entry."
            )
        return None

    def _evaluate_manual_paper_state_machine(self, snapshot: BTC15mMarketSnapshot, risk: RiskState) -> tuple[EVEstimate, dict[str, Any]]:
        mins_left = max(0.0, snapshot.time_remaining.total_seconds() / 60.0)
        entry_fee_rate = 2.0 * self.cfg.fee_bps_per_side / 10000.0
        inventory_state = risk.inventory_state
        qty = max(1, risk.inventory_qty) if inventory_state != "FLAT" else max(1, int(self.cfg.max_dollars_per_trade / max(0.01, self.cfg.manual_entry_cents / 100.0)))
        target_exit_cents = max(self.cfg.manual_entry_cents, int(round(self.cfg.manual_entry_cents + self.cfg.manual_profit_target_usd / max(qty, 1) * 100.0)))

        action = "skip"
        next_state = inventory_state
        reward_cents = 0.0
        cost_cents = 0.0
        fee_cents = 0.0
        score_cents = 0.0
        rationale = f"manual state machine idle: no side offered at or below {self.cfg.manual_entry_cents}c"
        unrealized_cents = 0.0

        if inventory_state == "FLAT":
            candidates: list[tuple[int, Literal["YES", "NO"], int]] = []
            if snapshot.yes_ask_cents <= self.cfg.manual_entry_cents:
                candidates.append((abs(self.cfg.manual_entry_cents - snapshot.yes_ask_cents), "YES", snapshot.yes_ask_cents))
            if snapshot.no_ask_cents <= self.cfg.manual_entry_cents:
                candidates.append((abs(self.cfg.manual_entry_cents - snapshot.no_ask_cents), "NO", snapshot.no_ask_cents))
            if candidates:
                _, chosen_side, ask_cents = min(candidates, key=lambda item: item[0])
                trend_block = self._btc_trend_blocks_entry(chosen_side, snapshot, risk)
                if trend_block is not None:
                    rationale = trend_block
                else:
                    fee_cents = ask_cents * entry_fee_rate
                    cost_cents = ask_cents
                    reward_cents = max(0.0, target_exit_cents - ask_cents)
                    score_cents = reward_cents - fee_cents
                    rationale = f"manual entry: buy {chosen_side} at {ask_cents}c near {self.cfg.manual_entry_cents}c with ${qty * ask_cents / 100.0:.2f} paper notional"
                    action = "buy_yes" if chosen_side == "YES" else "buy_no"
                    next_state = "LONG_YES" if chosen_side == "YES" else "LONG_NO"
        else:
            is_yes = inventory_state == "LONG_YES"
            mark_bid = snapshot.yes_bid_cents if is_yes else snapshot.no_bid_cents
            side = "YES" if is_yes else "NO"
            entry_cents = float(risk.entry_price_cents or 0.0)
            action = "hold_position"
            next_state = inventory_state
            unrealized_cents = mark_bid - entry_cents
            unrealized_profit_usd = qty * unrealized_cents / 100.0
            rationale = f"manual hold: waiting for ${self.cfg.manual_profit_target_usd:.2f} paper PnL target or 3-minute forced exit"
            should_exit_for_profit = unrealized_profit_usd >= self.cfg.manual_profit_target_usd
            should_exit_for_time = mins_left <= self.cfg.min_time_to_close_min
            if should_exit_for_profit or should_exit_for_time:
                fee_cents = mark_bid * entry_fee_rate
                cost_cents = -mark_bid
                reward_cents = unrealized_cents - fee_cents
                score_cents = reward_cents
                exit_reason = f"net paper PnL ${qty * reward_cents / 100.0:.2f}"
                rationale = f"manual exit: sell {side} at {mark_bid}c with {exit_reason}"
                action = "sell_yes" if is_yes else "sell_no"
                next_state = "FLAT"

        if action == "buy_yes":
            rec_action = "ENTER_LONG_YES"
            fair_prob = min(0.99, max(0.01, target_exit_cents / 100.0))
        elif action == "buy_no":
            rec_action = "ENTER_LONG_NO"
            fair_prob = min(0.99, max(0.01, 1.0 - target_exit_cents / 100.0))
        elif action in {"sell_yes", "sell_no"}:
            rec_action = "EXIT"
            fair_prob = snapshot.contract_price_cents / 100.0
        elif action == "hold_position":
            rec_action = "HOLD"
            fair_prob = snapshot.contract_price_cents / 100.0
        else:
            rec_action = "SKIP"
            fair_prob = snapshot.contract_price_cents / 100.0

        est = EVEstimate(
            fair_prob=round(fair_prob, 4),
            tp_hit_prob=1.0 if action in {"sell_yes", "sell_no"} else 0.5,
            stop_hit_prob=1.0 if mins_left <= self.cfg.min_time_to_close_min and inventory_state != "FLAT" else 0.0,
            expected_settlement_value=round(snapshot.contract_price_cents, 3),
            gross_edge=round(reward_cents if action not in {"hold_position", "skip"} else unrealized_cents, 3),
            fees=round(fee_cents, 3),
            slippage=0.0,
            net_ev=round(score_cents if action not in {"hold_position", "skip"} else unrealized_cents, 3),
            recommended_size=qty,
            recommended_action=rec_action,
        )
        slope, acceleration, basis_source = self._btc_trend_metrics(snapshot, risk)
        current_basis, _ = self._current_btc_basis(snapshot)
        return est, {
            "manual_action": action,
            "manual_reward_cents": reward_cents,
            "manual_cost_cents": cost_cents,
            "manual_lagrangian_score": score_cents if action not in {"hold_position", "skip"} else unrealized_cents,
            "manual_fee_cents": fee_cents,
            "manual_next_state": next_state,
            "manual_rationale": rationale,
            "manual_target_exit_cents": target_exit_cents,
            "unrealized_cents": unrealized_cents,
            "btc_basis_source": basis_source,
            "btc_basis_value": current_basis,
            "btc_basis_slope": slope,
            "btc_basis_acceleration": acceleration,
        }

    def estimate_trade_ev(self, snapshot: BTC15mMarketSnapshot, risk: RiskState) -> EVEstimate:
        if self._manual_paper_enabled():
            est, _ = self._evaluate_manual_paper_state_machine(snapshot, risk)
            return est
        return self._estimate_standard_ev(snapshot, risk)

    def decide_trade(self, snapshot: BTC15mMarketSnapshot, risk: RiskState) -> Literal["ENTER_LONG_YES", "ENTER_LONG_NO", "HOLD", "EXIT", "SKIP"]:
        return self.estimate_trade_ev(snapshot, risk).recommended_action

    def evaluate(self, snapshot: BTC15mMarketSnapshot, risk: RiskState) -> CandidateDecision:
        snapshot.current_position_side = snapshot.current_position_side or ({"LONG_YES": "YES", "LONG_NO": "NO"}.get(risk.inventory_state))
        snapshot.current_position_entry_cents = snapshot.current_position_entry_cents or (int(risk.entry_price_cents) if risk.entry_price_cents is not None else None)
        summary = {
            "yes_bid": snapshot.yes_bid_cents,
            "yes_ask": snapshot.yes_ask_cents,
            "no_bid": snapshot.no_bid_cents,
            "no_ask": snapshot.no_ask_cents,
            "spread_cents": snapshot.spread_cents,
            "min_depth": snapshot.min_depth,
            "stability_bps": snapshot.orderbook_stability_bps,
            "contract_price_cents": snapshot.contract_price_cents,
            "distance_from_target_cents": snapshot.distance_from_target_cents,
            "realized_vol_bps": snapshot.realized_vol_bps,
            "microprice_cents": snapshot.microprice_cents,
            "orderbook_imbalance": snapshot.orderbook_imbalance,
            "recent_trades_count": snapshot.recent_trades_count,
            "recent_trade_buy_ratio": snapshot.recent_trade_buy_ratio,
            "settlement_signal_strength": snapshot.settlement_signal_strength,
            "inventory_state": risk.inventory_state,
            "inventory_qty": risk.inventory_qty,
            "entry_price_cents": risk.entry_price_cents,
            "capital_remaining_usd": round(self._capital_remaining(risk), 4),
        }
        mins_left = snapshot.time_remaining.total_seconds() / 60.0

        def abstain(reason: str, confidence: int = 0, extra: dict[str, Any] | None = None) -> CandidateDecision:
            payload = extra or {}
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
                action=payload.get("action", "skip"),
                quantity=payload.get("quantity", 0),
                reward_cents=payload.get("reward_cents"),
                cost_cents=payload.get("cost_cents"),
                lagrangian_score=payload.get("lagrangian_score"),
                fee_cents=payload.get("fee_cents"),
                resulting_capital_usd=payload.get("resulting_capital_usd"),
                realized_round_trip_pnl_usd=payload.get("realized_round_trip_pnl_usd"),
                unrealized_pnl_usd=payload.get("unrealized_pnl_usd"),
                inventory_state_after=payload.get("inventory_state_after"),
                state_context=payload,
            )

        blocked_reason = self._check_tradeable(snapshot, risk)
        manual_info: dict[str, Any] = {}
        ev = self.estimate_trade_ev(snapshot, risk)
        if self._manual_paper_enabled():
            ev, manual_info = self._evaluate_manual_paper_state_machine(snapshot, risk)
        action = ev.recommended_action
        dominant_bid = max(snapshot.yes_bid_cents, snapshot.no_bid_cents)
        if blocked_reason is None and snapshot.current_position_side is None and dominant_bid < self.cfg.dominant_side_min_cents and not self._manual_paper_enabled():
            blocked_reason = f"Dominant side bid {dominant_bid}c is below {self.cfg.dominant_side_min_cents}c trigger."
        confidence = int(self._clamp(100.0 * max(0.0, ev.net_ev + self.cfg.safety_buffer_cents) / 8.0, 0.0, 100.0))
        side = "YES" if action == "ENTER_LONG_YES" else "NO" if action == "ENTER_LONG_NO" else "NONE"
        entry = snapshot.yes_ask_cents if side == "YES" else snapshot.no_ask_cents if side == "NO" else None

        qty = risk.inventory_qty or ev.recommended_size or 1
        if self._manual_paper_enabled():
            next_inventory = manual_info.get("manual_next_state", risk.inventory_state)
            entry_basis_cents = snapshot.yes_ask_cents if manual_info.get("manual_action", "").startswith("buy_yes") else snapshot.no_ask_cents if manual_info.get("manual_action", "").startswith("buy_no") else snapshot.yes_bid_cents if manual_info.get("manual_action") == "sell_yes" else snapshot.no_bid_cents if manual_info.get("manual_action") == "sell_no" else 100
            sized_qty = max(1, int(self.cfg.max_dollars_per_trade / max(0.01, entry_basis_cents / 100.0)))
            qty = risk.inventory_qty or sized_qty
            resulting_capital = risk.current_capital_usd - qty * (manual_info.get("manual_cost_cents") or 0.0) / 100.0
            visible_action = manual_info.get("manual_action", "skip")
            if blocked_reason is not None:
                visible_action = "hold" if snapshot.current_position_side or risk.inventory_state != "FLAT" else "skip"
            extra = {
                "action": visible_action,
                "quantity": qty,
                "reward_cents": manual_info.get("manual_reward_cents"),
                "cost_cents": manual_info.get("manual_cost_cents"),
                "lagrangian_score": manual_info.get("manual_lagrangian_score"),
                "fee_cents": manual_info.get("manual_fee_cents"),
                "resulting_capital_usd": round(resulting_capital, 4),
                "realized_round_trip_pnl_usd": round(risk.realized_round_trip_pnl_usd, 4),
                "unrealized_pnl_usd": round((manual_info.get("unrealized_cents") or 0.0) / 100.0, 4),
                "inventory_state_after": next_inventory,
                **manual_info,
            }
            if blocked_reason is not None:
                extra["manual_action"] = visible_action
                extra["manual_next_state"] = risk.inventory_state
        else:
            extra = {
                "action": action.lower(),
                "quantity": ev.recommended_size,
                "reward_cents": round(ev.gross_edge, 4),
                "cost_cents": round(ev.fees + ev.slippage, 4),
                "lagrangian_score": round(ev.net_ev, 4),
                "fee_cents": round(ev.fees, 4),
                "resulting_capital_usd": round(risk.current_capital_usd, 4),
                "realized_round_trip_pnl_usd": round(risk.realized_round_trip_pnl_usd, 4),
                "unrealized_pnl_usd": round(risk.unrealized_pnl_usd, 4),
                "inventory_state_after": risk.inventory_state,
            }

        if blocked_reason is not None:
            if snapshot.current_position_side is not None and mins_left <= self.cfg.min_time_to_close_min:
                forced_action = "sell_yes" if snapshot.current_position_side == "YES" else "sell_no"
                extra["action"] = forced_action
                extra["inventory_state_after"] = "FLAT"
                return abstain("Forced time exit at 3-minute cutoff.", confidence=confidence, extra=extra)
            return abstain(blocked_reason, confidence=confidence, extra=extra)
        if action not in {"ENTER_LONG_YES", "ENTER_LONG_NO"}:
            if action == "EXIT":
                return abstain("Open-position EV turned negative or timing/rule checks deteriorated; exit is preferred.", confidence=confidence, extra=extra)
            if self._manual_paper_enabled() and manual_info.get("manual_rationale"):
                return abstain(str(manual_info["manual_rationale"]), confidence=confidence, extra=extra)
            return abstain("Net EV after fees, slippage, and safety buffer is not strong enough to trade.", confidence=confidence, extra=extra)

        planned_profit = min(99, int(entry or 0) + self.cfg.target_take_profit_cents)
        reason = (
            f"{side} has positive net EV ({ev.net_ev:.2f}c) after fees/slippage, fair value {ev.expected_settlement_value:.1f}c, "
            f"spread {snapshot.spread_cents}c, depth {snapshot.min_depth}, and time-to-cutoff {mins_left:.2f}m."
        )
        if self._manual_paper_enabled():
            reason = f"Manual paper action {extra['action']} selected with score {extra['lagrangian_score']:.2f}; {manual_info.get('manual_rationale', 'simple paper state machine')}"
        invalidation = (
            f"Exit/avoid if recomputed EV drops below 0c, spread widens above {self.cfg.max_spread_cents}c, "
            f"or time remaining leaves the allowed window."
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
            expected_edge_cents=int(round(ev.net_ev)),
            action=extra.get("action", "skip"),
            quantity=extra.get("quantity", 0),
            reward_cents=extra.get("reward_cents"),
            cost_cents=extra.get("cost_cents"),
            lagrangian_score=extra.get("lagrangian_score"),
            fee_cents=extra.get("fee_cents"),
            resulting_capital_usd=extra.get("resulting_capital_usd"),
            realized_round_trip_pnl_usd=extra.get("realized_round_trip_pnl_usd"),
            unrealized_pnl_usd=extra.get("unrealized_pnl_usd"),
            inventory_state_after=extra.get("inventory_state_after"),
            state_context=extra,
        )

    def apply_execution_to_risk(self, decision: CandidateDecision, risk: RiskState, fill_count: int = 1) -> RiskState:
        now = datetime.now(timezone.utc).isoformat()
        next_state = RiskState(**asdict(risk))
        next_state.updated_at = now
        next_state.last_ticker = decision.ticker
        qty = max(1, fill_count or decision.quantity or 1)
        next_state.unrealized_pnl_usd = decision.unrealized_pnl_usd or 0.0
        basis_value = decision.state_context.get("btc_basis_value") if decision.state_context else None
        if basis_value is not None:
            previous_basis = next_state.last_btc_basis
            next_state.prev_btc_basis = previous_basis
            next_state.last_btc_basis = float(basis_value)
            next_state.last_btc_slope = None if previous_basis is None else float(basis_value) - float(previous_basis)

        if decision.decision != "TRADE" and decision.action not in {"sell_yes", "sell_no"}:
            return next_state

        action = decision.action
        cost_usd = qty * (decision.cost_cents or 0.0) / 100.0
        reward_usd = qty * (decision.reward_cents or 0.0) / 100.0
        fee_usd = qty * (decision.fee_cents or 0.0) / 100.0

        if action.startswith("buy_yes") or action == "enter_long_yes":
            next_state.inventory_state = "LONG_YES"
            next_state.inventory_qty = qty
            next_state.entry_price_cents = float(decision.planned_entry_cents or 0)
            next_state.entry_notional_usd = max(0.0, cost_usd)
            next_state.reserved_capital_usd += max(0.0, cost_usd)
            next_state.current_capital_usd -= max(0.0, cost_usd)
            next_state.open_positions = 1
        elif action.startswith("buy_no") or action == "enter_long_no":
            next_state.inventory_state = "LONG_NO"
            next_state.inventory_qty = qty
            next_state.entry_price_cents = float(decision.planned_entry_cents or 0)
            next_state.entry_notional_usd = max(0.0, cost_usd)
            next_state.reserved_capital_usd += max(0.0, cost_usd)
            next_state.current_capital_usd -= max(0.0, cost_usd)
            next_state.open_positions = 1
        elif action in {"sell_yes", "sell_no"}:
            released = max(0.0, -cost_usd)
            next_state.current_capital_usd += released
            if self.cfg.recycle_released_capital:
                next_state.recycled_capital_usd += released
            realized = reward_usd
            next_state.daily_realized_pnl_usd += realized
            next_state.realized_round_trip_pnl_usd += realized
            next_state.consecutive_losses = next_state.consecutive_losses + 1 if realized < 0 else 0
            next_state.inventory_state = "FLAT"
            next_state.inventory_qty = 0
            next_state.entry_price_cents = None
            next_state.entry_notional_usd = 0.0
            next_state.reserved_capital_usd = 0.0
            next_state.unrealized_pnl_usd = 0.0
            next_state.open_positions = 0

        next_state.trades_last_hour += 1
        if fee_usd > 0 and abs(cost_usd) > 0 and abs(fee_usd) / max(abs(cost_usd), 1e-9) > self.cfg.max_bad_slippage_cents / 100.0:
            next_state.two_consecutive_bad_slippage = True
        return next_state

    def execute_candidate(
        self,
        decision: CandidateDecision,
        client: KalshiClientInterface,
        log_dir: str | Path,
        live_enabled: bool,
        risk: RiskState | None = None,
        persist_state_path: str | Path | None = None,
    ) -> dict[str, Any] | None:
        if self._manual_paper_enabled() and self.cfg.paper_only_vol_bwk and live_enabled:
            raise RuntimeError("manual BTC15 paper path is paper-only; refusing live execution.")
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        state = risk or RiskState(current_capital_usd=self.cfg.initial_capital_usd)
        _append_jsonl(log_path / self.cfg.candidate_log_jsonl, {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            **asdict(decision),
        })
        _append_jsonl(log_path / self.cfg.state_log_jsonl, {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "ticker": decision.ticker,
            "decision": decision.decision,
            "action": decision.action,
            "state_before": asdict(state),
            "decision_metrics": {
                "reward_cents": decision.reward_cents,
                "cost_cents": decision.cost_cents,
                "lagrangian_score": decision.lagrangian_score,
                "fee_cents": decision.fee_cents,
                "resulting_capital_usd": decision.resulting_capital_usd,
                "realized_round_trip_pnl_usd": decision.realized_round_trip_pnl_usd,
                "unrealized_pnl_usd": decision.unrealized_pnl_usd,
            },
        })
        should_execute = decision.decision == "TRADE" or decision.action in {"sell_yes", "sell_no"}
        if not should_execute:
            next_state = self.apply_execution_to_risk(decision, state, fill_count=1)
            if persist_state_path is not None:
                save_risk_state(persist_state_path, next_state)
            return None
        order_side = decision.side
        limit_cents = decision.planned_entry_cents
        if decision.action == "sell_yes":
            order_side = "YES"
            limit_cents = decision.orderbook_summary.get("yes_bid")
        elif decision.action == "sell_no":
            order_side = "NO"
            limit_cents = decision.orderbook_summary.get("no_bid")
        order = KalshiOrder(
            event_ticker=decision.ticker,
            side=order_side,
            stake_usd=float(self.cfg.max_dollars_per_trade),
            limit_price=float(limit_cents) / 100.0,
        )
        response = client.place_order(order)
        execution_fill_count = decision.quantity or int(response.get("count", 1))
        next_state = self.apply_execution_to_risk(decision, state, fill_count=execution_fill_count)
        if persist_state_path is not None:
            save_risk_state(persist_state_path, next_state)
        realized_delta = round(next_state.realized_round_trip_pnl_usd - state.realized_round_trip_pnl_usd, 6)
        exit_price = limit_cents if decision.action in {"sell_yes", "sell_no"} else None
        trade_log = {
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "ticker": decision.ticker,
            "side": order_side,
            "action": decision.action,
            "limit_price": limit_cents,
            "filled_size": execution_fill_count,
            "reward_cents": decision.reward_cents,
            "cost_cents": decision.cost_cents,
            "lagrangian_score": decision.lagrangian_score,
            "fees_cents": decision.fee_cents,
            "resulting_capital_usd": next_state.current_capital_usd,
            "realized_round_trip_pnl_usd": next_state.realized_round_trip_pnl_usd,
            "unrealized_pnl_usd": next_state.unrealized_pnl_usd,
            "inventory_state_after": next_state.inventory_state,
            "fill_quality": response.get("status", "PAPER_PLACED" if not live_enabled else "LIVE_SENT"),
            "exit_price": exit_price,
            "pnl": realized_delta if decision.action in {"sell_yes", "sell_no"} else None,
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


def load_snapshot_sequence(path: str | Path) -> list[BTC15mMarketSnapshot]:
    p = Path(path)
    raw_text = p.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []
    if p.suffix.lower() == ".jsonl":
        items = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    else:
        payload = json.loads(raw_text)
        items = payload if isinstance(payload, list) else payload.get("snapshots", [])
    return [BTC15mMarketSnapshot.from_dict(item) for item in items]


def load_risk_state(path: str | Path | None) -> RiskState:
    if path is None:
        return RiskState()
    p = Path(path)
    if not p.exists():
        return RiskState()
    payload = json.loads(p.read_text(encoding="utf-8"))
    if "current_capital_usd" not in payload:
        payload["current_capital_usd"] = 100.0
    return RiskState(**payload)


def save_risk_state(path: str | Path, risk: RiskState) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(risk), indent=2, default=str), encoding="utf-8")


def _to_cents(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return int(round(float(value) * 100))
    return int(round(float(value) * 100)) if float(value) <= 1.0 else int(round(float(value)))


def _to_size(value: Any) -> int:
    if value is None:
        return 0
    return int(round(float(value)))


def _best_level(levels: list[Any] | None, prefer: Literal["max", "min"]) -> OrderBookLevel:
    parsed: list[OrderBookLevel] = []
    for level in levels or []:
        if not isinstance(level, (list, tuple)) or len(level) < 2:
            continue
        parsed.append(OrderBookLevel(price=_to_cents(level[0]), size=_to_size(level[1])))
    if not parsed:
        return OrderBookLevel(price=0, size=0)
    return max(parsed, key=lambda x: x.price) if prefer == "max" else min(parsed, key=lambda x: x.price)


def _btc15m_candidates_from_payload(payload: dict[str, Any]) -> list[str]:
    markets = payload.get("markets", []) if isinstance(payload, dict) else []
    out: list[tuple[datetime, str]] = []
    for item in markets:
        market = item.get("market", item) if isinstance(item, dict) else {}
        ticker = str(market.get("ticker", ""))
        event_ticker = str(market.get("event_ticker", ""))
        title = str(market.get("title", ""))
        ticker_upper = ticker.upper()
        event_upper = event_ticker.upper()
        title_upper = title.upper()
        looks_btc15m = (
            ticker_upper.startswith("KXBTC15M")
            or event_upper.startswith("KXBTC15M")
            or ticker_upper.startswith("KXBTCD")
            or event_upper.startswith("KXBTCD")
            or ("BTC" in title_upper and "15 MIN" in title_upper)
        )
        if not looks_btc15m:
            continue
        close_time_raw = market.get("close_time")
        try:
            close_time = datetime.fromisoformat(str(close_time_raw).replace("Z", "+00:00"))
        except Exception:
            close_time = datetime.max.replace(tzinfo=timezone.utc)
        out.append((close_time, ticker))
    out.sort(key=lambda x: x[0])
    return [ticker for _, ticker in out]


def discover_btc15m_tickers(client: KalshiClientInterface, limit: int = 20) -> list[str]:
    payload = client.list_markets(status="open", limit=limit, min_close_ts=int(datetime.now(timezone.utc).timestamp()))
    tickers = _btc15m_candidates_from_payload(payload)
    if tickers:
        return tickers
    series_payload = client.list_markets(status="open", limit=limit, series_ticker="KXBTC15M")
    return _btc15m_candidates_from_payload(series_payload)


def resolve_btc15m_ticker(client: KalshiClientInterface, ticker_or_event: str) -> str:
    raw = ticker_or_event.strip()
    raw_upper = raw.upper()
    if (raw_upper.startswith("KXBTC15M") or raw_upper.startswith("KXBTCD")) and raw_upper.endswith("-15"):
        return raw
    payload = client.list_markets(status="open", limit=20, event_ticker=raw)
    tickers = _btc15m_candidates_from_payload(payload)
    if tickers:
        return tickers[0]
    payload = client.list_markets(status="open", limit=20, series_ticker="KXBTC15M")
    markets = payload.get("markets", []) if isinstance(payload, dict) else []
    for item in markets:
        market = item.get("market", item) if isinstance(item, dict) else {}
        if str(market.get("event_ticker", "")) == raw or str(market.get("ticker", "")) == raw:
            return str(market.get("ticker", raw))
    return raw


def snapshot_from_market_data(
    market_payload: dict[str, Any],
    orderbook_payload: dict[str, Any],
    thesis_price_cents: int | None = None,
    btc_spot: float | None = None,
) -> BTC15mMarketSnapshot:
    market = market_payload.get("market", market_payload)
    orderbook = orderbook_payload.get("orderbook_fp", orderbook_payload)

    yes_levels = orderbook.get("yes_dollars", []) if isinstance(orderbook, dict) else []
    no_levels = orderbook.get("no_dollars", []) if isinstance(orderbook, dict) else []

    best_yes_bid = _best_level(yes_levels, prefer="max")
    best_no_bid = _best_level(no_levels, prefer="max")
    best_yes_ask = OrderBookLevel(price=100 - best_no_bid.price if best_no_bid.price else _to_cents(market.get("yes_ask_dollars")), size=best_no_bid.size or _to_size(market.get("yes_ask_size_fp")))
    best_no_ask = OrderBookLevel(price=100 - best_yes_bid.price if best_yes_bid.price else _to_cents(market.get("no_ask_dollars")), size=best_yes_bid.size or _to_size(market.get("no_ask_size_fp")))

    close_time = datetime.fromisoformat(str(market["close_time"]).replace("Z", "+00:00"))
    rules = "\n".join(x for x in [market.get("rules_primary", ""), market.get("rules_secondary", "")] if x).strip()
    stability_bps = abs(_to_cents(market.get("yes_bid_dollars")) - _to_cents(market.get("previous_yes_bid_dollars"))) * 100.0

    yes_bid_cents = best_yes_bid.price or _to_cents(market.get("yes_bid_dollars"))
    yes_ask_cents = best_yes_ask.price
    best_yes_bid_size = best_yes_bid.size or _to_size(market.get("yes_bid_size_fp"))
    best_yes_ask_size = best_yes_ask.size or _to_size(market.get("yes_ask_size_fp"))
    best_no_bid_size = best_no_bid.size or _to_size(market.get("yes_ask_size_fp"))
    best_no_ask_size = best_no_ask.size or _to_size(market.get("yes_bid_size_fp"))
    total_yes_depth = sum(level.size for level in [_best_level(yes_levels, prefer="max")]) if yes_levels else 0
    total_no_depth = sum(level.size for level in [_best_level(no_levels, prefer="max")]) if no_levels else 0
    imbalance = None
    denom = total_yes_depth + total_no_depth
    if denom > 0:
        imbalance = (total_yes_depth - total_no_depth) / denom
    microprice_cents = None
    if best_yes_bid_size + best_no_bid_size > 0:
        microprice_cents = (yes_bid_cents * best_no_bid_size + yes_ask_cents * best_yes_bid_size) / max(1, best_yes_bid_size + best_no_bid_size)

    return BTC15mMarketSnapshot(
        ticker=str(market["ticker"]),
        rules=rules,
        status=str(market.get("status", "unknown")),
        close_time=close_time,
        yes_ask_cents=yes_ask_cents,
        yes_bid_cents=yes_bid_cents,
        no_ask_cents=best_no_ask.price,
        no_bid_cents=best_no_bid.price or _to_cents(market.get("no_bid_dollars")),
        best_yes_ask_size=best_yes_ask_size,
        best_yes_bid_size=best_yes_bid_size,
        best_no_ask_size=best_no_ask_size,
        best_no_bid_size=best_no_bid_size,
        orderbook_stability_bps=stability_bps,
        btc_spot=btc_spot,
        thesis_price_cents=thesis_price_cents,
        realized_vol_bps=float(market.get("realized_vol_bps")) if market.get("realized_vol_bps") is not None else None,
        microprice_cents=microprice_cents,
        orderbook_imbalance=imbalance,
        depth_contracts=min(x for x in [best_yes_ask_size, best_yes_bid_size, best_no_ask_size, best_no_bid_size] if x > 0) if any(x > 0 for x in [best_yes_ask_size, best_yes_bid_size, best_no_ask_size, best_no_bid_size]) else None,
        recent_trades_count=int(orderbook.get("recent_trades_count", 0)) if isinstance(orderbook, dict) and orderbook.get("recent_trades_count") is not None else None,
        recent_trade_buy_ratio=float(orderbook.get("recent_trade_buy_ratio")) if isinstance(orderbook, dict) and orderbook.get("recent_trade_buy_ratio") is not None else None,
        settlement_signal_strength=float(market.get("settlement_signal_strength")) if market.get("settlement_signal_strength") is not None else None,
        metadata={"market": market, "orderbook": orderbook},
    )


def fetch_live_snapshot(
    client: KalshiClientInterface,
    ticker: str | None = None,
    thesis_price_cents: int | None = None,
    btc_spot: float | None = None,
) -> BTC15mMarketSnapshot:
    chosen = ticker
    if not chosen:
        tickers = discover_btc15m_tickers(client)
        if not tickers:
            raise RuntimeError("No open BTC 15m Kalshi markets found.")
        chosen = tickers[0]
    chosen = resolve_btc15m_ticker(client, chosen)
    try:
        market = client.get_market(chosen)
    except Exception:
        resolved = resolve_btc15m_ticker(client, chosen)
        if resolved != chosen:
            chosen = resolved
            market = client.get_market(chosen)
        else:
            series_payload = client.list_markets(status="open", limit=20, series_ticker="KXBTC15M")
            markets = series_payload.get("markets", []) if isinstance(series_payload, dict) else []
            matched = None
            for item in markets:
                m = item.get("market", item) if isinstance(item, dict) else {}
                if str(m.get("event_ticker", "")) == ticker or str(m.get("ticker", "")) == ticker:
                    matched = str(m.get("ticker", ""))
                    break
            if not matched:
                raise
            chosen = matched
            market = client.get_market(chosen)
    orderbook = client.get_orderbook(chosen)
    return snapshot_from_market_data(market, orderbook, thesis_price_cents=thesis_price_cents, btc_spot=btc_spot)
