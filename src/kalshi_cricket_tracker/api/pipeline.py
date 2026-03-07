from __future__ import annotations

from pathlib import Path

import pandas as pd

from kalshi_cricket_tracker.config import AppConfig
from kalshi_cricket_tracker.data.ingest import CricSheetIngestor, FixtureIngestor
from kalshi_cricket_tracker.features.engineering import add_recent_form, build_team_ratings
from kalshi_cricket_tracker.odds import create_odds_adapter
from kalshi_cricket_tracker.strategy.risk import apply_risk
from kalshi_cricket_tracker.strategy.signals import generate_signals
from kalshi_cricket_tracker.winprob import create_winprob_adapter


def ingest_and_engineer(cfg: AppConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], pd.DataFrame]:
    cs = CricSheetIngestor(cfg.data.cricsheet_results_url)
    zip_path = cs.download_zip(force=False)
    matches = cs.parse_matches(zip_path, limit=cfg.data.lookback_matches)

    rated_matches, ratings = build_team_ratings(matches, k=cfg.features.elo_k)
    rated_matches = add_recent_form(rated_matches, window=cfg.features.recent_form_window)
    rated_matches["proxy_market_prob_team1"] = (
        0.5 + (rated_matches["team1_win_prob_pre"] - 0.5) * cfg.odds.proxy_shrinkage
    )

    fixtures = FixtureIngestor(cfg.data.fixtures_url).fetch(limit=25)

    winprob_adapter = create_winprob_adapter(cfg.winprob)
    external_probs = winprob_adapter.fetch_probabilities(fixtures)
    if not external_probs.empty:
        fixtures = fixtures.merge(external_probs[["event_id", "external_prob_team1"]], on="event_id", how="left")

    odds_adapter = create_odds_adapter(cfg.odds)
    sigs = generate_signals(
        fixtures,
        ratings,
        cfg.strategy,
        home_advantage_elo=cfg.features.home_advantage_elo,
        odds_adapter=odds_adapter,
    )
    sigs = apply_risk(sigs, cfg.strategy)

    return matches, rated_matches, ratings, sigs


def ensure_artifacts_dir(cfg: AppConfig) -> Path:
    p = Path(cfg.runtime.artifact_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p
