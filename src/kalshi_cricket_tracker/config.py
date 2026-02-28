from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class DataConfig(BaseModel):
    cricsheet_results_url: str = "https://cricsheet.org/downloads/t20s_json.zip"
    fixtures_url: str = "https://site.web.api.espn.com/apis/v2/sports/cricket/scoreboard"
    competitions: list[str] = Field(default_factory=lambda: ["intl-t20", "t20-league"])
    lookback_matches: int = 4000


class StrategyConfig(BaseModel):
    min_edge_bps: float = 250.0
    min_model_prob: float = 0.53
    max_position_usd: float = 250.0
    daily_risk_budget_usd: float = 1000.0
    fee_bps: float = 10.0
    kelly_fraction: float = 0.25


class FeatureConfig(BaseModel):
    elo_k: float = 20.0
    home_advantage_elo: float = 25.0
    recent_form_window: int = 5


class BanditConfig(BaseModel):
    alpha: float = 1.5
    risk_lambda: float = 0.15
    l2_reg: float = 1.0
    stake_arms: list[float] = Field(default_factory=lambda: [0.0, 25.0, 50.0, 100.0, 150.0, 250.0])


class RuntimeConfig(BaseModel):
    base_currency: Literal["USD"] = "USD"
    artifact_dir: str = "artifacts"
    timezone: str = "UTC"


class AppConfig(BaseModel):
    data: DataConfig = DataConfig()
    strategy: StrategyConfig = StrategyConfig()
    features: FeatureConfig = FeatureConfig()
    bandit: BanditConfig = BanditConfig()
    runtime: RuntimeConfig = RuntimeConfig()



def load_config(path: str | Path) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AppConfig(**raw)
