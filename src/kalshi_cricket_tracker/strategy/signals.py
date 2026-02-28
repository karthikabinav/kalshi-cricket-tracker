from __future__ import annotations

import pandas as pd

from kalshi_cricket_tracker.config import StrategyConfig


def generate_signals(fixtures: pd.DataFrame, ratings: dict[str, float], cfg: StrategyConfig, home_advantage_elo: float) -> pd.DataFrame:
    rows = []
    for _, fx in fixtures.iterrows():
        t1, t2 = fx["team1"], fx["team2"]
        r1, r2 = ratings.get(t1, 1500.0), ratings.get(t2, 1500.0)
        model_prob = 1.0 / (1.0 + 10 ** ((r2 - (r1 + home_advantage_elo)) / 400))

        # Free odds proxy: convert rating spread to a pseudo-market probability with mild shrinkage.
        proxy_market_prob = 0.5 + (model_prob - 0.5) * 0.65
        edge = model_prob - proxy_market_prob
        edge_bps = edge * 10000

        action = "HOLD"
        side = None
        if model_prob >= cfg.min_model_prob and edge_bps >= cfg.min_edge_bps:
            action = "BUY_YES"
            side = t1
        elif (1 - model_prob) >= cfg.min_model_prob and (-edge_bps) >= cfg.min_edge_bps:
            action = "BUY_NO"
            side = t1

        rows.append(
            {
                **fx.to_dict(),
                "team1_elo": r1,
                "team2_elo": r2,
                "model_prob_team1": model_prob,
                "proxy_market_prob_team1": proxy_market_prob,
                "edge_bps": edge_bps,
                "action": action,
                "market_side": side,
            }
        )
    return pd.DataFrame(rows)
