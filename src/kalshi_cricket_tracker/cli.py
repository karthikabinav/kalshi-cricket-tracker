from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import typer
from rich import print

from kalshi_cricket_tracker.api.pipeline import ensure_artifacts_dir, ingest_and_engineer
from kalshi_cricket_tracker.backtest.engine import run_backtest
from kalshi_cricket_tracker.config import load_config
from kalshi_cricket_tracker.execution.guards import validate_trading_mode
from kalshi_cricket_tracker.execution.kalshi import KalshiOrder, KalshiRestClient, MockKalshiPaperClient
from kalshi_cricket_tracker.strategy.contextual_bandit import run_bandit_backtest
from kalshi_cricket_tracker.strategy.risk import apply_risk

app = typer.Typer(help="Kalshi Cricket Tracker CLI")


@app.command()
def run_daily(config: str = "configs/default.yaml"):
    cfg = load_config(config)
    art = ensure_artifacts_dir(cfg)
    _, rated_matches, _, signals = ingest_and_engineer(cfg)

    signals.to_csv(art / "daily_signals.csv", index=False)
    rated_matches.to_csv(art / "rated_matches.csv", index=False)

    validate_trading_mode(cfg.trading)
    if cfg.trading.mode == "live":
        client = KalshiRestClient.from_env(cfg.trading)
        fills = []
        for _, row in signals.iterrows():
            if not row.get("allowed") or row.get("action") == "HOLD":
                continue
            fills.append(
                client.place_order(
                    KalshiOrder(
                        event_ticker=f"CRICKET-{row.get('event_id', 'NA')}",
                        side=row["action"],
                        stake_usd=float(row["stake_usd"]),
                        limit_price=float(row["proxy_market_prob_team1"]),
                    )
                )
            )
        fills = pd.DataFrame(fills)
        fills.to_csv(art / "live_order_responses.csv", index=False)
    else:
        fills = MockKalshiPaperClient().execute_from_signals(signals)
        fills.to_csv(art / "paper_fills.csv", index=False)

    print(f"[green]Saved daily outputs in {art}[/green]")


@app.command()
def backtest(config: str = "configs/default.yaml"):
    cfg = load_config(config)
    art = ensure_artifacts_dir(cfg)
    _, rated_matches, _, _ = ingest_and_engineer(cfg)

    bt_df = rated_matches.copy()
    bt_df["model_prob_team1"] = bt_df["team1_win_prob_pre"]
    bt_df["proxy_market_prob_team1"] = 0.5 + (bt_df["team1_win_prob_pre"] - 0.5) * 0.65
    bt_df["edge_bps"] = (bt_df["model_prob_team1"] - bt_df["proxy_market_prob_team1"]) * 10000
    bt_df["action"] = bt_df["edge_bps"].apply(lambda x: "BUY_YES" if x > cfg.strategy.min_edge_bps else "HOLD")
    bt_df = apply_risk(bt_df, cfg.strategy)

    trades, metrics = run_backtest(bt_df, fee_bps=cfg.strategy.fee_bps)
    trades.to_csv(art / "backtest_trades.csv", index=False)
    (art / "backtest_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(metrics)


@app.command("bandit-backtest")
def bandit_backtest(config: str = "configs/default.yaml"):
    cfg = load_config(config)
    art = ensure_artifacts_dir(cfg)
    _, rated_matches, _, _ = ingest_and_engineer(cfg)

    out, metrics = run_bandit_backtest(
        rated_matches,
        stake_arms=cfg.bandit.stake_arms,
        alpha=cfg.bandit.alpha,
        risk_lambda=cfg.bandit.risk_lambda,
        l2_reg=cfg.bandit.l2_reg,
        daily_budget=cfg.strategy.daily_risk_budget_usd,
        fee_bps=cfg.strategy.fee_bps,
    )

    out.to_csv(art / "bandit_backtest.csv", index=False)
    (art / "bandit_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(metrics)


@app.command()
def dashboard(config: str = "configs/default.yaml"):
    cfg = load_config(config)
    art = Path(cfg.runtime.artifact_dir)
    cmd = f"streamlit run scripts/dashboard.py -- --config {config}"
    print(f"Run manually: {cmd}")


if __name__ == "__main__":
    app()
