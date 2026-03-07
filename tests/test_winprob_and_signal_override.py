from __future__ import annotations

import pandas as pd

from kalshi_cricket_tracker.config import StrategyConfig
from kalshi_cricket_tracker.strategy.signals import generate_signals
from kalshi_cricket_tracker.winprob import CsvWinProbAdapter


def test_generate_signals_prefers_external_prob_when_present():
    fixtures = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "date": pd.Timestamp("2026-03-01"),
                "team1": "India",
                "team2": "Australia",
                "venue": "X",
                "competition": "T20",
                "external_prob_team1": 0.71,
            }
        ]
    )
    ratings = {"India": 1500, "Australia": 1500}
    cfg = StrategyConfig(min_edge_bps=0, min_model_prob=0.5, max_position_usd=100, daily_risk_budget_usd=500, fee_bps=10, kelly_fraction=0.25)

    sigs = generate_signals(fixtures, ratings, cfg, home_advantage_elo=0)
    assert len(sigs) == 1
    assert sigs.iloc[0]["model_prob_source"] == "external"
    assert abs(float(sigs.iloc[0]["model_prob_team1"]) - 0.71) < 1e-9


def test_csv_winprob_adapter(tmp_path):
    csv_path = tmp_path / "wp.csv"
    pd.DataFrame([{"event_id": "e1", "external_prob_team1": 0.64}]).to_csv(csv_path, index=False)
    fixtures = pd.DataFrame([{"event_id": "e1"}, {"event_id": "e2"}])

    out = CsvWinProbAdapter(str(csv_path)).fetch_probabilities(fixtures)
    assert set(out.columns) == {"event_id", "external_prob_team1", "prob_source"}
    assert out.loc[out["event_id"] == "e1", "external_prob_team1"].iloc[0] == 0.64
