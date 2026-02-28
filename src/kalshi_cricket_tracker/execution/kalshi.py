from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd


@dataclass
class KalshiOrder:
    event_ticker: str
    side: str
    stake_usd: float
    limit_price: float


class KalshiClientInterface:
    def place_order(self, order: KalshiOrder) -> dict:
        raise NotImplementedError


class MockKalshiPaperClient(KalshiClientInterface):
    """Paper-only executor. No live orders."""

    def __init__(self):
        self.orders: list[dict] = []

    def place_order(self, order: KalshiOrder) -> dict:
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_ticker": order.event_ticker,
            "side": order.side,
            "stake_usd": order.stake_usd,
            "limit_price": order.limit_price,
            "status": "PAPER_FILLED",
        }
        self.orders.append(rec)
        return rec

    def execute_from_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        fills = []
        for _, row in signals.iterrows():
            if not row.get("allowed"):
                continue
            if row.get("action") == "HOLD":
                continue
            order = KalshiOrder(
                event_ticker=f"CRICKET-{row.get('event_id', 'NA')}",
                side=row["action"],
                stake_usd=float(row["stake_usd"]),
                limit_price=float(row["proxy_market_prob_team1"]),
            )
            fills.append(self.place_order(order))
        return pd.DataFrame(fills)
