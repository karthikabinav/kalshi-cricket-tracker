import pandas as pd
import pytest

from kalshi_cricket_tracker.config import OddsConfig, TradingConfig
from kalshi_cricket_tracker.execution.guards import LIVE_CONFIRMATION_PHRASE, LiveTradingGuardrailError, validate_trading_mode
from kalshi_cricket_tracker.odds import CsvOddsAdapter, ProxyOddsAdapter, create_odds_adapter


def test_odds_adapter_selection_default_proxy():
    adapter = create_odds_adapter(OddsConfig(provider="proxy"))
    assert isinstance(adapter, ProxyOddsAdapter)


def test_odds_adapter_selection_csv(tmp_path):
    csv_path = tmp_path / "odds.csv"
    pd.DataFrame(
        {
            "event_id": ["e1"],
            "market_prob_team1": [0.62],
        }
    ).to_csv(csv_path, index=False)

    adapter = create_odds_adapter(OddsConfig(provider="csv", csv_path=str(csv_path)))
    assert isinstance(adapter, CsvOddsAdapter)

    out = adapter.fetch_probabilities(pd.DataFrame({"event_id": ["e1", "e2"]}))
    assert out.loc[out["event_id"] == "e1", "market_prob_team1"].iloc[0] == pytest.approx(0.62)
    assert out.loc[out["event_id"] == "e2", "market_prob_team1"].iloc[0] == pytest.approx(0.5)


def test_live_mode_guardrail_blocks_without_opt_in():
    with pytest.raises(LiveTradingGuardrailError):
        validate_trading_mode(TradingConfig(mode="live", enable_live_trading=False))


def test_live_mode_guardrail_requires_confirmation_phrase():
    with pytest.raises(LiveTradingGuardrailError):
        validate_trading_mode(
            TradingConfig(mode="live", enable_live_trading=True, live_confirmation_phrase="wrong")
        )


def test_live_mode_guardrail_allows_explicit_enablement():
    validate_trading_mode(
        TradingConfig(
            mode="live",
            enable_live_trading=True,
            live_confirmation_phrase=LIVE_CONFIRMATION_PHRASE,
        )
    )
