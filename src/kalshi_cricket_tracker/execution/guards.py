from __future__ import annotations

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
