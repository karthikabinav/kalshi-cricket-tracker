import pandas as pd

from kalshi_cricket_tracker.config import StrategyConfig
from kalshi_cricket_tracker.strategy.signals import generate_signals


def test_generate_signals_handles_empty_fixtures():
    fixtures = pd.DataFrame(columns=["date", "team1", "team2", "venue", "competition", "event_id"])
    out = generate_signals(fixtures=fixtures, ratings={}, cfg=StrategyConfig(), home_advantage_elo=25.0)
    assert out.empty
    assert "event_id" in out.columns
    assert "action" in out.columns
