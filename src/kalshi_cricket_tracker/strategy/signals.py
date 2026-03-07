from __future__ import annotations

import pandas as pd

from kalshi_cricket_tracker.config import StrategyConfig
from kalshi_cricket_tracker.odds import OddsAdapter, ProxyOddsAdapter


def generate_signals(
    fixtures: pd.DataFrame,
    ratings: dict[str, float],
    cfg: StrategyConfig,
    home_advantage_elo: float,
    odds_adapter: OddsAdapter | None = None,
) -> pd.DataFrame:
    rows = []
    for idx, fx in fixtures.iterrows():
        t1, t2 = fx["team1"], fx["team2"]
        r1, r2 = ratings.get(t1, 1500.0), ratings.get(t2, 1500.0)
        elo_prob = 1.0 / (1.0 + 10 ** ((r2 - (r1 + home_advantage_elo)) / 400))
        external_prob = fx.get("external_prob_team1")
        use_external = external_prob is not None and pd.notna(external_prob)
        model_prob = float(external_prob) if use_external else float(elo_prob)

        rec = {
            **fx.to_dict(),
            "event_id": fx.get("event_id") or f"fixture-{idx}",
            "team1_elo": r1,
            "team2_elo": r2,
            "elo_prob_team1": float(elo_prob),
            "external_prob_team1": float(external_prob) if use_external else None,
            "model_prob_source": "external" if use_external else "elo",
            "model_prob_team1": model_prob,
        }
        rows.append(rec)

    base_cols = [
        "date",
        "team1",
        "team2",
        "venue",
        "competition",
        "event_id",
        "team1_elo",
        "team2_elo",
        "elo_prob_team1",
        "external_prob_team1",
        "model_prob_source",
        "model_prob_team1",
    ]
    sigs = pd.DataFrame(rows, columns=base_cols)
    if sigs.empty:
        sigs["market_prob_team1"] = pd.Series(dtype=float)
        sigs["proxy_market_prob_team1"] = pd.Series(dtype=float)
        sigs["edge_bps"] = pd.Series(dtype=float)
        sigs["action"] = pd.Series(dtype=str)
        sigs["market_side"] = pd.Series(dtype=object)
        return sigs

    adapter = odds_adapter or ProxyOddsAdapter()
    odds = adapter.fetch_probabilities(sigs)

    sigs = sigs.merge(odds, on="event_id", how="left")
    sigs["market_prob_team1"] = sigs["market_prob_team1"].fillna(0.5)
    sigs["proxy_market_prob_team1"] = sigs["market_prob_team1"]

    sigs["edge_bps"] = (sigs["model_prob_team1"] - sigs["market_prob_team1"]) * 10000

    sigs["action"] = "HOLD"
    sigs["market_side"] = None

    yes_mask = (sigs["model_prob_team1"] >= cfg.min_model_prob) & (sigs["edge_bps"] >= cfg.min_edge_bps)
    no_mask = ((1 - sigs["model_prob_team1"]) >= cfg.min_model_prob) & ((-sigs["edge_bps"]) >= cfg.min_edge_bps)

    sigs.loc[yes_mask, "action"] = "BUY_YES"
    sigs.loc[yes_mask, "market_side"] = sigs.loc[yes_mask, "team1"]
    sigs.loc[no_mask, "action"] = "BUY_NO"
    sigs.loc[no_mask, "market_side"] = sigs.loc[no_mask, "team1"]

    return sigs
