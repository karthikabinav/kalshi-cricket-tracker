from __future__ import annotations

import math

import pandas as pd

from kalshi_cricket_tracker.config import StrategyConfig


def _bounded_prob(x: float) -> float:
    if not math.isfinite(x):
        return 0.5
    return min(1.0, max(0.0, x))


def apply_risk(signals: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    out = signals.copy()
    bankroll_left = max(0.0, float(cfg.daily_risk_budget_usd))
    stakes = []

    for _, row in out.iterrows():
        action = row.get("action", "HOLD")
        if action == "HOLD" or bankroll_left <= 0:
            stakes.append(0.0)
            continue

        model_p = _bounded_prob(float(row.get("model_prob_team1", 0.5)))
        p = model_p if action == "BUY_YES" else 1 - model_p
        q = 1 - p
        b = 1.0
        kelly = max(0.0, (b * p - q) / b)
        suggested = max(0.0, cfg.kelly_fraction * kelly * cfg.daily_risk_budget_usd)
        stake = min(max(0.0, cfg.max_position_usd), bankroll_left, suggested)
        stakes.append(stake)
        bankroll_left = max(0.0, bankroll_left - stake)

    out["stake_usd"] = stakes
    out["allowed"] = out["stake_usd"] > 0
    return out
