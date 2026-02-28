from __future__ import annotations

import os

from kalshi_cricket_tracker.config import TradingConfig

LIVE_CONFIRMATION_PHRASE = "I_UNDERSTAND_AND_ACCEPT_LIVE_TRADING_RISK"


class LiveTradingGuardrailError(RuntimeError):
    pass


def validate_trading_mode(cfg: TradingConfig) -> None:
    """Prevent accidental live execution unless explicit multi-step enablement is set."""
    if cfg.mode == "paper":
        return

    if cfg.mode != "live":
        raise LiveTradingGuardrailError(f"Unknown trading mode: {cfg.mode}")

    if not cfg.enable_live_trading:
        raise LiveTradingGuardrailError(
            "Live mode requested but trading.enable_live_trading=false. Refusing to proceed."
        )

    if cfg.live_confirmation_phrase != LIVE_CONFIRMATION_PHRASE:
        raise LiveTradingGuardrailError(
            "Live mode requested without required confirmation phrase. Refusing to proceed."
        )

    if not os.getenv(cfg.kalshi_api_key_env) or not os.getenv(cfg.kalshi_api_secret_env):
        raise LiveTradingGuardrailError(
            "Live mode requested but Kalshi credentials are missing from environment. "
            f"Set {cfg.kalshi_api_key_env} and {cfg.kalshi_api_secret_env}."
        )
