import pandas as pd

from kalshi_cricket_tracker.config import StrategyConfig
from kalshi_cricket_tracker.strategy.risk import apply_risk


def test_apply_risk_respects_daily_budget():
    cfg = StrategyConfig(daily_risk_budget_usd=100, max_position_usd=80)
    sigs = pd.DataFrame(
        [
            {"action": "BUY_YES", "model_prob_team1": 0.6},
            {"action": "BUY_YES", "model_prob_team1": 0.6},
            {"action": "BUY_YES", "model_prob_team1": 0.6},
        ]
    )
    out = apply_risk(sigs, cfg)
    assert out["stake_usd"].sum() <= 100 + 1e-9


def test_apply_risk_handles_invalid_probabilities():
    cfg = StrategyConfig(daily_risk_budget_usd=100, max_position_usd=80)
    sigs = pd.DataFrame(
        [
            {"action": "BUY_YES", "model_prob_team1": 2.5},
            {"action": "BUY_NO", "model_prob_team1": -3.0},
            {"action": "BUY_YES", "model_prob_team1": float("nan")},
        ]
    )
    out = apply_risk(sigs, cfg)
    assert (out["stake_usd"] >= 0).all()
    assert out["stake_usd"].sum() <= 100 + 1e-9
