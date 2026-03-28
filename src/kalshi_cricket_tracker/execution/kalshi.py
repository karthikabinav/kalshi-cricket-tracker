from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

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

    def get_market(self, event_ticker: str) -> dict:
        raise NotImplementedError

    def get_orderbook(self, event_ticker: str) -> dict:
        raise NotImplementedError

    def list_markets(self, **params: Any) -> dict:
        raise NotImplementedError


class MockKalshiPaperClient(KalshiClientInterface):
    """Paper-only executor. No live orders."""

    def __init__(
        self,
        market_map: dict[str, dict] | None = None,
        orderbook_map: dict[str, dict] | None = None,
        list_markets_response: dict | None = None,
    ):
        self.orders: list[dict] = []
        self.market_map = market_map or {}
        self.orderbook_map = orderbook_map or {}
        self.list_markets_response = list_markets_response or {"markets": list(self.market_map.values())}

    def place_order(self, order: KalshiOrder) -> dict:
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_ticker": order.event_ticker,
            "side": order.side,
            "stake_usd": order.stake_usd,
            "limit_price": order.limit_price,
            "count": 1,
            "status": "PAPER_FILLED",
        }
        self.orders.append(rec)
        return rec

    def get_market(self, event_ticker: str) -> dict:
        market = self.market_map.get(event_ticker, {})
        return market if "market" in market else {"market": market} if market else {}

    def get_orderbook(self, event_ticker: str) -> dict:
        ob = self.orderbook_map.get(event_ticker, {})
        return ob if "orderbook_fp" in ob else {"orderbook_fp": ob} if ob else {}

    def list_markets(self, **params: Any) -> dict:
        return self.list_markets_response

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

    Public market-data endpoints may work without credentials; order placement requires credentials.
    """

    def __init__(self, base_url: str, api_key: str | None = None, api_secret: str | None = None, timeout_s: int = 20):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

        self.public_session = requests.Session()
        self.public_session.headers.update({"Content-Type": "application/json"})

        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        if api_key and api_secret:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {api_key}",
                    "X-Kalshi-API-Secret": api_secret,
                }
            )

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

    @classmethod
    def public(cls, cfg: TradingConfig) -> "KalshiRestClient":
        return cls(base_url=cfg.kalshi_api_base_url)

    def get_market(self, event_ticker: str) -> dict:
        url = f"{self.base_url}/markets/{event_ticker}"
        r = self.public_session.get(url, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def get_orderbook(self, event_ticker: str, depth: int = 10) -> dict:
        url = f"{self.base_url}/markets/{event_ticker}/orderbook"
        r = self.public_session.get(url, params={"depth": depth}, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def list_markets(self, **params: Any) -> dict:
        url = f"{self.base_url}/markets"
        r = self.public_session.get(url, params=params, timeout=self.timeout_s)
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
