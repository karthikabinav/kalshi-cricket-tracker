from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from kalshi_cricket_tracker.config import OddsConfig


class OddsAdapter(Protocol):
    """Interface for mapping fixtures to market-implied team1 probabilities."""

    def fetch_probabilities(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        """Return columns: event_id, market_prob_team1, odds_source."""


@dataclass
class ProxyOddsAdapter:
    shrinkage: float = 0.65

    def fetch_probabilities(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        if fixtures.empty:
            return pd.DataFrame(columns=["event_id", "market_prob_team1", "odds_source"])

        out = fixtures[["event_id"]].copy()
        if "model_prob_team1" in fixtures.columns:
            out["market_prob_team1"] = 0.5 + (fixtures["model_prob_team1"] - 0.5) * self.shrinkage
        else:
            out["market_prob_team1"] = 0.5
        out["odds_source"] = "proxy"
        return out


@dataclass
class ProviderStubOddsAdapter:
    provider_name: str = "provider_stub"

    def fetch_probabilities(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        if fixtures.empty:
            return pd.DataFrame(columns=["event_id", "market_prob_team1", "odds_source"])
        return pd.DataFrame(
            {
                "event_id": fixtures["event_id"],
                "market_prob_team1": [0.5] * len(fixtures),
                "odds_source": [self.provider_name] * len(fixtures),
            }
        )


@dataclass
class CsvOddsAdapter:
    csv_path: str

    def fetch_probabilities(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        p = Path(self.csv_path)
        if not p.exists():
            raise FileNotFoundError(f"CSV odds file not found: {p}")

        odds = pd.read_csv(p)
        required = {"event_id", "market_prob_team1"}
        missing = required - set(odds.columns)
        if missing:
            raise ValueError(f"CSV odds missing required columns: {sorted(missing)}")

        out = fixtures[["event_id"]].merge(
            odds[["event_id", "market_prob_team1"]],
            on="event_id",
            how="left",
        )
        out["market_prob_team1"] = out["market_prob_team1"].fillna(0.5)
        out["odds_source"] = "csv"
        return out


def create_odds_adapter(cfg: OddsConfig) -> OddsAdapter:
    if cfg.provider == "proxy":
        return ProxyOddsAdapter(shrinkage=cfg.proxy_shrinkage)
    if cfg.provider == "provider_stub":
        return ProviderStubOddsAdapter(provider_name=cfg.provider_stub_name)
    if cfg.provider == "csv":
        if not cfg.csv_path:
            raise ValueError("odds.csv_path must be set when odds.provider=csv")
        return CsvOddsAdapter(csv_path=cfg.csv_path)

    raise ValueError(f"Unsupported odds provider: {cfg.provider}")
