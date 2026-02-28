import pandas as pd

from kalshi_cricket_tracker.strategy.contextual_bandit import RiskAwareLinUCBBandit, run_bandit_backtest


def test_bandit_budget_constraint():
    b = RiskAwareLinUCBBandit(n_features=3, stake_arms=[0, 25, 50], alpha=0.0)
    x = pd.Series([1.0, 0.2, -0.1]).to_numpy()
    d = b.choose(x=x, p_model=0.6, market_prob=0.5, remaining_budget=30)
    assert d.stake_usd in [0, 25]
    assert d.stake_usd <= 30


def test_bandit_update_changes_params():
    b = RiskAwareLinUCBBandit(n_features=2, stake_arms=[0, 50], alpha=0.0)
    x = pd.Series([1.0, 0.5]).to_numpy()
    pre = b.b[50].copy()
    b.update(x=x, arm=50, pnl=10.0)
    assert (b.b[50] != pre).any()


def test_run_bandit_backtest_outputs_metrics():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=8, freq="D"),
            "team1": ["A"] * 8,
            "team2": ["B"] * 8,
            "winner": ["A", "B", "A", "A", "B", "A", "B", "A"],
            "team1_win_prob_pre": [0.55, 0.52, 0.58, 0.57, 0.49, 0.6, 0.51, 0.56],
            "proxy_market_prob_team1": [0.51, 0.5, 0.53, 0.54, 0.5, 0.55, 0.5, 0.52],
            "team1_form": [0.5] * 8,
            "team2_form": [0.5] * 8,
            "team1_pre_elo": [1520] * 8,
            "team2_pre_elo": [1490] * 8,
        }
    )
    out, metrics = run_bandit_backtest(df, stake_arms=[0, 25, 50], alpha=0.5, risk_lambda=0.05, l2_reg=1.0, daily_budget=100)
    assert "cum_pnl" in out.columns
    assert "trades" in metrics
