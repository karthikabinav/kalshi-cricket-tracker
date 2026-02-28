from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import requests

from kalshi_cricket_tracker.config import TradingConfig


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


class KalshiRestClient(KalshiClientInterface):
    """Optional live REST client scaffold.

    This client is intentionally minimal and only enabled via explicit live-mode config.
    """

    def __init__(self, base_url: str, api_key: str, api_secret: str, timeout_s: int = 20):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "X-Kalshi-API-Secret": api_secret,
                "Content-Type": "application/json",
            }
        )
        self.timeout_s = timeout_s

    @classmethod
    def from_env(cls, cfg: TradingConfig) -> "KalshiRestClient":
        api_key = os.getenv(cfg.kalshi_api_key_env)
        api_secret = os.getenv(cfg.kalshi_api_secret_env)
        if not api_key or not api_secret:
            raise RuntimeError(
                "Kalshi credentials are missing in environment. "
                f"Set {cfg.kalshi_api_key_env} and {cfg.kalshi_api_secret_env}."
            )
        return cls(base_url=cfg.kalshi_api_base_url, api_key=api_key, api_secret=api_secret)

    def get_market(self, event_ticker: str) -> dict:
        url = f"{self.base_url}/markets/{event_ticker}"
        r = self.session.get(url, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def place_order(self, order: KalshiOrder) -> dict:
        url = f"{self.base_url}/portfolio/orders"
        payload = {
            "ticker": order.event_ticker,
            "side": order.side,
            "count": 1,
            "client_order_id": f"kct-{int(datetime.now(timezone.utc).timestamp())}",
            "type": "limit",
            "yes_price": int(round(order.limit_price * 100)),
        }
        r = self.session.post(url, json=payload, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()
