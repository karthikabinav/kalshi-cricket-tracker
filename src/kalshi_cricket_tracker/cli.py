from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import typer
from rich import print

from kalshi_cricket_tracker.api.pipeline import ensure_artifacts_dir, ingest_and_engineer
from kalshi_cricket_tracker.backtest.engine import run_backtest
from kalshi_cricket_tracker.config import load_config
from kalshi_cricket_tracker.execution.btc15m import BTC15mExecutionAgent, load_risk_state, load_snapshot
from kalshi_cricket_tracker.execution.guards import validate_trading_mode
from kalshi_cricket_tracker.execution.kalshi import KalshiOrder, KalshiRestClient, MockKalshiPaperClient
from kalshi_cricket_tracker.strategy.contextual_bandit import run_bandit_backtest
from kalshi_cricket_tracker.strategy.copula_sim import (
    equicorr_matrix,
    joint_tail_metrics,
    simulate_clayton_outcomes,
    simulate_gaussian_outcomes,
    simulate_independent_outcomes,
    simulate_t_outcomes,
)
from kalshi_cricket_tracker.strategy.risk import apply_risk
from kalshi_cricket_tracker.strategy.live_arb import ArbConfig, backtest_from_snapshots

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
    bt_df["proxy_market_prob_team1"] = 0.5 + (bt_df["team1_win_prob_pre"] - 0.5) * cfg.odds.proxy_shrinkage
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
        min_edge_bps=cfg.bandit.min_edge_bps,
    )

    out.to_csv(art / "bandit_backtest.csv", index=False)
    (art / "bandit_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(metrics)


@app.command("copula-stress")
def copula_stress(
    probs: str = typer.Option("0.52,0.53,0.51,0.48,0.50", help="Comma-separated marginal probabilities"),
    rho: float = typer.Option(0.5, help="Equicorrelation for Gaussian/t copulas"),
    nu: float = typer.Option(4.0, help="Degrees of freedom for t-copula"),
    theta: float = typer.Option(2.0, help="Clayton copula theta"),
    n_paths: int = typer.Option(200000, help="Simulation paths"),
    seed: int = typer.Option(42, help="Random seed"),
):
    p = [float(x.strip()) for x in probs.split(",") if x.strip()]
    d = len(p)
    corr = equicorr_matrix(d, rho)

    indep = joint_tail_metrics(simulate_independent_outcomes(p, n=n_paths, seed=seed))
    gauss = joint_tail_metrics(simulate_gaussian_outcomes(p, corr=corr, n=n_paths, seed=seed + 1))
    tc = joint_tail_metrics(simulate_t_outcomes(p, corr=corr, nu=nu, n=n_paths, seed=seed + 2))
    clay = joint_tail_metrics(simulate_clayton_outcomes(p, theta=theta, n=n_paths, seed=seed + 3))

    def ratio(a: float, b: float) -> float:
        return float("inf") if b == 0 else a / b

    out = {
        "settings": {"probs": p, "rho": rho, "nu": nu, "theta": theta, "n_paths": n_paths},
        "independent": indep,
        "gaussian": gauss,
        "t_copula": tc,
        "clayton": clay,
        "tail_multipliers_vs_gaussian": {
            "all_win_t_over_gaussian": ratio(tc["p_all_win"], gauss["p_all_win"]),
            "all_lose_t_over_gaussian": ratio(tc["p_all_lose"], gauss["p_all_lose"]),
            "all_lose_clayton_over_gaussian": ratio(clay["p_all_lose"], gauss["p_all_lose"]),
        },
    }
    print(json.dumps(out, indent=2))


@app.command("arb-backtest")
def arb_backtest(
    snapshots_csv: str = typer.Option(..., help="CSV with ts,event_id,model_prob_team1,market_prob_team1"),
    config: str = "configs/default.yaml",
    stake_usd: float = typer.Option(100.0, help="Per-position notional in USD"),
):
    cfg = load_config(config)
    art = ensure_artifacts_dir(cfg)
    snaps = pd.read_csv(snapshots_csv)
    arb_cfg = ArbConfig(
        entry_edge_bps=cfg.live_arb.entry_edge_bps,
        exit_edge_bps=cfg.live_arb.exit_edge_bps,
        take_profit_bps=cfg.live_arb.take_profit_bps,
        stop_loss_bps=cfg.live_arb.stop_loss_bps,
        max_holding_minutes=cfg.live_arb.max_holding_minutes,
    )
    trades, metrics = backtest_from_snapshots(snaps, arb_cfg, stake_usd=stake_usd)
    trades.to_csv(art / "arb_backtest_trades.csv", index=False)
    (art / "arb_backtest_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(metrics)


@app.command("btc15m-exec")
def btc15m_exec(
    snapshot_json: str = typer.Option(..., help="Path to a BTC 15m market snapshot JSON file"),
    risk_json: str | None = typer.Option(None, help="Optional path to risk state JSON"),
    config: str = "configs/default.yaml",
):
    cfg = load_config(config)
    art = ensure_artifacts_dir(cfg)
    snapshot = load_snapshot(snapshot_json)
    risk = load_risk_state(risk_json)
    agent = BTC15mExecutionAgent(cfg.btc15m)
    decision = agent.evaluate(snapshot, risk)

    validate_trading_mode(cfg.trading)
    client = KalshiRestClient.from_env(cfg.trading) if cfg.trading.mode == "live" else MockKalshiPaperClient()
    agent.execute_candidate(decision, client=client, log_dir=art, live_enabled=cfg.trading.mode == "live")
    print(decision.render())


@app.command()
def dashboard(config: str = "configs/default.yaml"):
    cfg = load_config(config)
    art = Path(cfg.runtime.artifact_dir)
    cmd = f"streamlit run scripts/dashboard.py -- --config {config}"
    print(f"Run manually: {cmd}")


if __name__ == "__main__":
    app()
