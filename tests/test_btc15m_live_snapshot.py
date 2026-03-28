from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kalshi_cricket_tracker.execution.btc15m import discover_btc15m_tickers, fetch_live_snapshot, resolve_btc15m_ticker, snapshot_from_market_data
from kalshi_cricket_tracker.execution.kalshi import MockKalshiPaperClient


def test_discover_btc15m_tickers_sorts_nearest_close_first():
    now = datetime.now(timezone.utc)
    client = MockKalshiPaperClient(
        list_markets_response={
            "markets": [
                {"ticker": "KXBTCD-15M-LATER", "close_time": (now + timedelta(minutes=15)).isoformat(), "status": "open"},
                {"ticker": "KXBTCD-15M-SOON", "close_time": (now + timedelta(minutes=8)).isoformat(), "status": "open"},
                {"ticker": "NOTBTC-15M", "close_time": (now + timedelta(minutes=6)).isoformat(), "status": "open"},
            ]
        }
    )
    assert discover_btc15m_tickers(client)[:2] == ["KXBTCD-15M-SOON", "KXBTCD-15M-LATER"]


def test_snapshot_from_market_data_builds_crossed_binary_book_correctly():
    market = {
        "market": {
            "ticker": "KXBTCD-15M-TEST",
            "close_time": (datetime.now(timezone.utc) + timedelta(minutes=8)).isoformat(),
            "status": "active",
            "yes_bid_dollars": "0.57",
            "yes_ask_dollars": "0.58",
            "no_bid_dollars": "0.42",
            "no_ask_dollars": "0.43",
            "yes_bid_size_fp": "60",
            "yes_ask_size_fp": "50",
            "previous_yes_bid_dollars": "0.56",
            "rules_primary": "BTC settles above threshold.",
            "rules_secondary": "Uses exchange settlement auction.",
        }
    }
    orderbook = {
        "orderbook_fp": {
            "yes_dollars": [["0.57", "60"]],
            "no_dollars": [["0.42", "65"]],
        }
    }
    snap = snapshot_from_market_data(market, orderbook, thesis_price_cents=63)
    assert snap.ticker == "KXBTCD-15M-TEST"
    assert snap.yes_bid_cents == 57
    assert snap.no_bid_cents == 42
    assert snap.yes_ask_cents == 58
    assert snap.no_ask_cents == 43
    assert snap.best_yes_ask_size == 65
    assert snap.best_no_ask_size == 60
    assert "BTC settles above threshold" in snap.rules


def test_resolve_btc15m_event_ticker_to_market_ticker():
    now = datetime.now(timezone.utc)
    market = {
        "ticker": "KXBTC15M-26MAR242015-15",
        "event_ticker": "KXBTC15M-26MAR242015",
        "close_time": (now + timedelta(minutes=8)).isoformat(),
        "status": "active",
        "title": "BTC price up in next 15 mins?",
    }
    client = MockKalshiPaperClient(list_markets_response={"markets": [market]})
    assert resolve_btc15m_ticker(client, "KXBTC15M-26MAR242015") == "KXBTC15M-26MAR242015-15"


def test_fetch_live_snapshot_uses_discovery_when_ticker_missing():
    now = datetime.now(timezone.utc)
    market_map = {
        "KXBTCD-15M-SOON": {
            "ticker": "KXBTCD-15M-SOON",
            "close_time": (now + timedelta(minutes=8)).isoformat(),
            "status": "active",
            "yes_bid_dollars": "0.57",
            "yes_ask_dollars": "0.58",
            "no_bid_dollars": "0.42",
            "no_ask_dollars": "0.43",
            "yes_bid_size_fp": "60",
            "yes_ask_size_fp": "50",
            "previous_yes_bid_dollars": "0.56",
            "rules_primary": "rule",
            "rules_secondary": "",
        }
    }
    orderbook_map = {"KXBTCD-15M-SOON": {"yes_dollars": [["0.57", "60"]], "no_dollars": [["0.42", "65"]]}}
    client = MockKalshiPaperClient(
        market_map=market_map,
        orderbook_map=orderbook_map,
        list_markets_response={"markets": [market_map["KXBTCD-15M-SOON"]]},
    )
    snap = fetch_live_snapshot(client, thesis_price_cents=61)
    assert snap.ticker == "KXBTCD-15M-SOON"
    assert snap.thesis_price_cents == 61
