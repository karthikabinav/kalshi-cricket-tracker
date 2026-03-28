from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PositionState = Literal["FLAT", "LONG_YES", "LONG_NO"]
ActionName = Literal[
    "buy_yes_15",
    "buy_yes_8",
    "hold",
    "buy_no_8",
    "buy_no_15",
    "sell_yes",
    "sell_no",
    "hold_position",
    "skip",
]


@dataclass(frozen=True)
class FeeSchedule:
    maker_fee_bps: float = 10.0
    taker_fee_bps: float = 10.0

    def maker_fee(self, price_cents: float, qty: int) -> float:
        return max(0.0, float(price_cents) * max(0, int(qty)) * self.maker_fee_bps / 10000.0)

    def taker_fee(self, price_cents: float, qty: int) -> float:
        return max(0.0, float(price_cents) * max(0, int(qty)) * self.taker_fee_bps / 10000.0)

    def buy_cost(self, ask_cents: float, qty: int) -> float:
        return float(ask_cents) * qty + self.maker_fee(ask_cents, qty)

    def sell_cost(self, bid_cents: float, qty: int) -> float:
        return -(float(bid_cents) * qty - self.taker_fee(bid_cents, qty))

    def sell_reward(self, entry_cents: float, bid_cents: float, qty: int) -> float:
        return (float(bid_cents) - float(entry_cents)) * qty - self.maker_fee(entry_cents, qty) - self.taker_fee(bid_cents, qty)

    def round_trip_friction(self, entry_cents: float, exit_cents: float, qty: int) -> float:
        return self.maker_fee(entry_cents, qty) + self.taker_fee(exit_cents, qty)


@dataclass(frozen=True)
class VolSnapshot:
    yes_bid_cents: int
    yes_ask_cents: int
    no_bid_cents: int
    no_ask_cents: int
    spread_cents: int
    depth_contracts: int
    time_remaining_min: float
    distance_from_target_cents: float | None = None
    microprice_cents: float | None = None
    orderbook_imbalance: float | None = None
    recent_trade_buy_ratio: float | None = None
    realized_vol_bps: float | None = None
    local_mean_reversion_zscore: float | None = None


@dataclass(frozen=True)
class Position:
    state: PositionState = "FLAT"
    qty: int = 0
    entry_cents: float | None = None


@dataclass(frozen=True)
class BwKActionEvaluation:
    action: ActionName
    reward: float
    cost: float
    lagrangian_score: float
    next_state: PositionState
    fee_load: float
    rationale: str


FLAT_ACTIONS: tuple[ActionName, ...] = ("buy_yes_15", "buy_yes_8", "hold", "buy_no_8", "buy_no_15")
LONG_YES_ACTIONS: tuple[ActionName, ...] = ("sell_yes", "hold_position")
LONG_NO_ACTIONS: tuple[ActionName, ...] = ("sell_no", "hold_position")


class VolBanditsWithKnapsackPolicy:
    def __init__(self, fee_schedule: FeeSchedule, entry_qty: int = 1):
        self.fee_schedule = fee_schedule
        self.entry_qty = max(1, int(entry_qty))

    @staticmethod
    def feasible_actions(position: Position) -> tuple[ActionName, ...]:
        if position.state == "FLAT":
            return FLAT_ACTIONS
        if position.state == "LONG_YES":
            return LONG_YES_ACTIONS
        if position.state == "LONG_NO":
            return LONG_NO_ACTIONS
        raise ValueError(f"Unsupported position state: {position.state}")

    @staticmethod
    def transition(position: Position, action: ActionName, entry_price_cents: float | None = None) -> Position:
        if position.state == "FLAT":
            if action in {"buy_yes_15", "buy_yes_8"}:
                return Position(state="LONG_YES", qty=position.qty or 1, entry_cents=entry_price_cents)
            if action in {"buy_no_8", "buy_no_15"}:
                return Position(state="LONG_NO", qty=position.qty or 1, entry_cents=entry_price_cents)
            return position
        if position.state == "LONG_YES":
            return Position() if action == "sell_yes" else position
        if position.state == "LONG_NO":
            return Position() if action == "sell_no" else position
        raise ValueError(f"Unsupported position state: {position.state}")

    @staticmethod
    def mark_to_market(position: Position, snapshot: VolSnapshot) -> float:
        if position.qty <= 0 or position.entry_cents is None:
            return 0.0
        if position.state == "LONG_YES":
            return (snapshot.yes_bid_cents - position.entry_cents) * position.qty
        if position.state == "LONG_NO":
            return (snapshot.no_bid_cents - position.entry_cents) * position.qty
        return 0.0

    def evaluate_action(
        self,
        position: Position,
        snapshot: VolSnapshot,
        action: ActionName,
        lambda_cost: float,
        expected_recovery_cents: float = 0.0,
    ) -> BwKActionEvaluation:
        if action not in self.feasible_actions(position):
            raise ValueError(f"Action {action} is not feasible from state {position.state}")

        qty = position.qty or self.entry_qty
        reversion = snapshot.local_mean_reversion_zscore or 0.0
        imbalance = snapshot.orderbook_imbalance or 0.0
        trade_bias = (snapshot.recent_trade_buy_ratio or 0.5) - 0.5
        vol = snapshot.realized_vol_bps or 0.0
        micro_anchor = snapshot.microprice_cents if snapshot.microprice_cents is not None else (snapshot.yes_bid_cents + snapshot.yes_ask_cents) / 2.0
        depth_bonus = min(2.0, snapshot.depth_contracts / 100.0)
        fee_load = 0.0
        reward = 0.0
        rationale = ""
        next_state = position.state

        if action.startswith("buy_yes"):
            threshold = 15.0 if action.endswith("15") else 8.0
            dip = max(0.0, micro_anchor - snapshot.yes_ask_cents)
            signal = dip + 3.0 * max(0.0, -reversion) + 2.0 * max(0.0, -trade_bias) + depth_bonus - snapshot.spread_cents
            reward = expected_recovery_cents + signal - threshold / 10.0
            cost = self.fee_schedule.buy_cost(snapshot.yes_ask_cents, qty)
            fee_load = self.fee_schedule.maker_fee(snapshot.yes_ask_cents, qty)
            next_state = "LONG_YES"
            rationale = f"buy_yes on dip threshold {threshold}c with signal {signal:.2f}"
            entry_price = snapshot.yes_ask_cents
        elif action.startswith("buy_no"):
            threshold = 15.0 if action.endswith("15") else 8.0
            dip = max(0.0, (100.0 - micro_anchor) - snapshot.no_ask_cents)
            signal = dip + 3.0 * max(0.0, reversion) + 2.0 * max(0.0, trade_bias) + depth_bonus - snapshot.spread_cents
            reward = expected_recovery_cents + signal - threshold / 10.0
            cost = self.fee_schedule.buy_cost(snapshot.no_ask_cents, qty)
            fee_load = self.fee_schedule.maker_fee(snapshot.no_ask_cents, qty)
            next_state = "LONG_NO"
            rationale = f"buy_no on dip threshold {threshold}c with signal {signal:.2f}"
            entry_price = snapshot.no_ask_cents
        elif action == "sell_yes":
            if position.entry_cents is None:
                raise ValueError("sell_yes requires an entry price")
            reward = self.fee_schedule.sell_reward(position.entry_cents, snapshot.yes_bid_cents, qty)
            cost = self.fee_schedule.sell_cost(snapshot.yes_bid_cents, qty)
            fee_load = self.fee_schedule.taker_fee(snapshot.yes_bid_cents, qty)
            next_state = "FLAT"
            rationale = "exit yes position and recycle capital"
            entry_price = position.entry_cents
        elif action == "sell_no":
            if position.entry_cents is None:
                raise ValueError("sell_no requires an entry price")
            reward = self.fee_schedule.sell_reward(position.entry_cents, snapshot.no_bid_cents, qty)
            cost = self.fee_schedule.sell_cost(snapshot.no_bid_cents, qty)
            fee_load = self.fee_schedule.taker_fee(snapshot.no_bid_cents, qty)
            next_state = "FLAT"
            rationale = "exit no position and recycle capital"
            entry_price = position.entry_cents
        elif action in {"hold", "hold_position", "skip"}:
            reward = self.mark_to_market(position, snapshot) * 0.0 - max(0.0, vol / 200.0) - max(0.0, snapshot.spread_cents - 1)
            cost = 0.0
            rationale = "wait for cleaner mean-reversion / exit signal"
            entry_price = position.entry_cents
        else:
            raise ValueError(f"Unhandled action: {action}")

        lagrangian_score = reward - lambda_cost * cost
        next_position = self.transition(position, action, entry_price_cents=entry_price)
        return BwKActionEvaluation(
            action=action,
            reward=round(reward, 4),
            cost=round(cost, 4),
            lagrangian_score=round(lagrangian_score, 4),
            next_state=next_position.state,
            fee_load=round(fee_load, 4),
            rationale=rationale,
        )

    def choose_action(
        self,
        position: Position,
        snapshot: VolSnapshot,
        lambda_cost: float,
        budget_remaining: float,
        expected_recovery_cents: float = 0.0,
    ) -> BwKActionEvaluation:
        evaluations = []
        for action in self.feasible_actions(position):
            ev = self.evaluate_action(
                position=position,
                snapshot=snapshot,
                action=action,
                lambda_cost=lambda_cost,
                expected_recovery_cents=expected_recovery_cents,
            )
            if ev.cost > budget_remaining and ev.cost >= 0:
                continue
            evaluations.append(ev)
        if not evaluations:
            return BwKActionEvaluation(
                action="skip",
                reward=0.0,
                cost=0.0,
                lagrangian_score=0.0,
                next_state=position.state,
                fee_load=0.0,
                rationale="no feasible action within remaining budget",
            )
        return max(evaluations, key=lambda ev: (ev.lagrangian_score, ev.reward, -ev.cost))
