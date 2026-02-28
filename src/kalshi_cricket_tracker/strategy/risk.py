from __future__ import annotations

import pandas as pd

from kalshi_cricket_tracker.config import StrategyConfig


def apply_risk(signals: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    out = signals.copy()
    bankroll_left = cfg.daily_risk_budget_usd
    stakes = []

    for _, row in out.iterrows():
        if row["action"] == "HOLD":
            stakes.append(0.0)
            continue

        p = row["model_prob_team1"] if row["action"] == "BUY_YES" else 1 - row["model_prob_team1"]
        q = 1 - p
        b = 1.0
        kelly = max(0.0, (b * p - q) / b)
        suggested = cfg.kelly_fraction * kelly * cfg.daily_risk_budget_usd
        stake = min(cfg.max_position_usd, bankroll_left, max(0.0, suggested))
        stakes.append(stake)
        bankroll_left -= stake

    out["stake_usd"] = stakes
    out["allowed"] = out["stake_usd"] > 0
    return out
