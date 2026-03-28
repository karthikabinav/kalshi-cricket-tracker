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


class LiveArbConfig(BaseModel):
    entry_edge_bps: float = 250.0
    exit_edge_bps: float = 40.0
    take_profit_bps: float = 120.0
    stop_loss_bps: float = 150.0
    max_holding_minutes: int = 180


class FeatureConfig(BaseModel):
    elo_k: float = 20.0
    home_advantage_elo: float = 25.0
    recent_form_window: int = 5


class BanditConfig(BaseModel):
    alpha: float = 1.5
    risk_lambda: float = 0.15
    l2_reg: float = 1.0
    min_edge_bps: float = 0.0
    stake_arms: list[float] = Field(default_factory=lambda: [0.0, 25.0, 50.0, 100.0, 150.0, 250.0])


class RuntimeConfig(BaseModel):
    base_currency: Literal["USD"] = "USD"
    artifact_dir: str = "artifacts"
    timezone: str = "UTC"


class OddsConfig(BaseModel):
    provider: Literal["proxy", "provider_stub", "csv"] = "proxy"
    proxy_shrinkage: float = 0.65
    csv_path: str | None = None
    provider_stub_name: str = "provider_stub"


class WinProbConfig(BaseModel):
    provider: Literal["elo_only", "csv", "cricinfo"] = "elo_only"
    csv_path: str | None = None
    # Format with {event_id}; example:
    # https://hs-consumer-api.espncricinfo.com/v1/pages/match/details?lang=en&matchId={event_id}&latest=true
    cricinfo_endpoint_template: str | None = None
    cricinfo_timeout_s: int = 12


class TradingConfig(BaseModel):
    mode: Literal["paper", "live"] = "paper"
    enable_live_trading: bool = False
    live_confirmation_phrase: str = ""

    kalshi_api_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    kalshi_api_key_env: str = "KALSHI_API_KEY"
    kalshi_api_secret_env: str = "KALSHI_API_SECRET"


class BTC15mExecConfig(BaseModel):
    enabled: bool = False
    manual_paper_enabled: bool = False
    # Deprecated compatibility switches for older BTC15 paper configs/tests.
    vol_bwk_enabled: bool = False
    paper_only_vol_bwk: bool = True
    initial_capital_usd: float = 100.0
    recycle_released_capital: bool = True
    maker_fee_bps: float = 10.0
    taker_fee_bps: float = 10.0
    min_time_to_close_min: float = 3.0
    max_time_to_close_min: float = 15.0
    min_depth_contracts: int = 25
    max_spread_cents: int = 2
    max_orderbook_instability_bps: float = 60.0
    dominant_side_min_cents: int = 80
    exit_edge_cents: int = 1
    min_reward_cents: int = 1
    target_take_profit_cents: int = 2
    min_confidence: int = 60
    max_dollars_per_trade: float = 100.0
    profit_target_fraction: float = 0.10
    max_simultaneous_positions: int = 1
    max_daily_loss_usd: float = 150.0
    max_consecutive_losses: int = 3
    max_trades_per_hour: int = 4
    max_bad_slippage_cents: int = 2
    fee_bps_per_side: float = 10.0
    maker_fill_fraction: float = 0.0
    safety_buffer_cents: float = 1.0
    max_slippage_cents: float = 2.0
    stop_loss_cents: int = 3
    size_kelly_fraction: float = 0.1
    min_ev_to_trade_cents: float = 0.5
    bwk_lambda_cost: float = 0.02
    bwk_expected_recovery_cents: float = 1.5
    manual_entry_cents: int = 60
    manual_profit_target_usd: float = 10.0
    band_entry_cents: int = 60
    band_exit_cents: int = 80
    risk_state_json: str = "btc15m_risk_state.json"
    candidate_log_jsonl: str = "btc15m_candidate_decisions.jsonl"
    executed_log_jsonl: str = "btc15m_executed_trades.jsonl"
    state_log_jsonl: str = "btc15m_state_trace.jsonl"


class AppConfig(BaseModel):
    data: DataConfig = DataConfig()
    strategy: StrategyConfig = StrategyConfig()
    live_arb: LiveArbConfig = LiveArbConfig()
    features: FeatureConfig = FeatureConfig()
    bandit: BanditConfig = BanditConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    odds: OddsConfig = OddsConfig()
    winprob: WinProbConfig = WinProbConfig()
    trading: TradingConfig = TradingConfig()
    btc15m: BTC15mExecConfig = BTC15mExecConfig()



def load_config(path: str | Path) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config root must be a mapping/object, got: {type(raw).__name__}")
    return AppConfig(**raw)
