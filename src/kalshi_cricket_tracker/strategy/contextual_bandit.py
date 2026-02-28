from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BanditDecision:
    action: str
    side: str
    stake_usd: float
    score: float


class RiskAwareLinUCBBandit:
    """
    Risk-adjusted linear contextual bandit with stake arms.

    For each arm a, expected utility is estimated as:
      U_hat(x,a) = x_a^T theta_a + alpha * sqrt(x_a^T A_a^-1 x_a)

    Realized reward uses mean-variance proxy:
      r_t = pnl_t - lambda * pnl_t^2

    Online ridge-regression update:
      A_a <- A_a + x_a x_a^T
      b_a <- b_a + r_t x_a
      theta_a = A_a^-1 b_a
    """

    def __init__(self, n_features: int, stake_arms: list[float], alpha: float = 1.5, risk_lambda: float = 0.15, l2_reg: float = 1.0):
        self.n_features = n_features
        self.stake_arms = sorted(stake_arms)
        self.alpha = alpha
        self.risk_lambda = risk_lambda
        self.l2_reg = l2_reg
        self.A = {a: np.eye(n_features) * l2_reg for a in self.stake_arms}
        self.b = {a: np.zeros((n_features, 1)) for a in self.stake_arms}

    def _theta(self, arm: float) -> np.ndarray:
        return np.linalg.solve(self.A[arm], self.b[arm])

    def arm_score(self, arm: float, x: np.ndarray) -> float:
        x = x.reshape(-1, 1)
        A_inv_x = np.linalg.solve(self.A[arm], x)
        exploit = float((self._theta(arm).T @ x).item())
        explore = self.alpha * float(np.sqrt((x.T @ A_inv_x).item()))
        return exploit + explore

    def choose(
        self,
        x: np.ndarray,
        p_model: float,
        market_prob: float,
        remaining_budget: float,
        min_edge_bps: float = 0.0,
    ) -> BanditDecision:
        side = "BUY_YES" if p_model >= 0.5 else "BUY_NO"
        edge_bps = abs(float(p_model) - float(market_prob)) * 10000
        if edge_bps < max(0.0, min_edge_bps):
            return BanditDecision(action="HOLD", side=side, stake_usd=0.0, score=0.0)

        feasible = [a for a in self.stake_arms if a <= remaining_budget]
        if not feasible:
            return BanditDecision(action="HOLD", side=side, stake_usd=0.0, score=0.0)

        scored = [(a, self.arm_score(a, x)) for a in feasible]
        best_arm, best_score = max(scored, key=lambda t: (t[1], t[0]))
        if best_arm <= 0:
            return BanditDecision(action="HOLD", side=side, stake_usd=0.0, score=best_score)
        return BanditDecision(action="BET", side=side, stake_usd=best_arm, score=best_score)

    def update(self, x: np.ndarray, arm: float, pnl: float) -> float:
        x = x.reshape(-1, 1)
        reward = pnl - self.risk_lambda * (pnl**2)
        self.A[arm] += x @ x.T
        self.b[arm] += reward * x
        return reward


def _pnl_for_outcome(side: str, team1_won: bool, stake: float, fee_rate: float) -> float:
    correct = (side == "BUY_YES" and team1_won) or (side == "BUY_NO" and (not team1_won))
    gross = stake if correct else -stake
    return gross - abs(stake) * fee_rate


def run_bandit_backtest(
    df: pd.DataFrame,
    stake_arms: list[float],
    alpha: float,
    risk_lambda: float,
    l2_reg: float,
    daily_budget: float,
    fee_bps: float = 10.0,
    min_edge_bps: float = 0.0,
) -> tuple[pd.DataFrame, dict]:
    """
    Required columns:
      date, team1_win_prob_pre, proxy_market_prob_team1, team1_form, team2_form,
      team1_pre_elo, team2_pre_elo, winner, team1
    """
    data = df.copy().sort_values("date").reset_index(drop=True)
    if data.empty:
        return data, {"trades": 0, "pnl": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "hit_rate": 0.0}

    feat_cols = [
        "team1_win_prob_pre",
        "proxy_market_prob_team1",
        "edge",
        "team1_form",
        "team2_form",
        "elo_diff",
    ]
    data["edge"] = data["team1_win_prob_pre"] - data["proxy_market_prob_team1"]
    data["elo_diff"] = data["team1_pre_elo"] - data["team2_pre_elo"]
    for col in feat_cols:
        data[col] = data[col].fillna(0.0)

    fee_rate = fee_bps / 10000
    bandit = RiskAwareLinUCBBandit(n_features=len(feat_cols), stake_arms=stake_arms, alpha=alpha, risk_lambda=risk_lambda, l2_reg=l2_reg)

    logs = []
    current_day = None
    remaining_budget = daily_budget

    for _, row in data.iterrows():
        day = pd.Timestamp(row["date"]).date()
        if day != current_day:
            current_day = day
            remaining_budget = daily_budget

        x = row[feat_cols].to_numpy(dtype=float)
        decision = bandit.choose(
            x,
            p_model=float(row["team1_win_prob_pre"]),
            market_prob=float(row["proxy_market_prob_team1"]),
            remaining_budget=remaining_budget,
            min_edge_bps=min_edge_bps,
        )

        stake = decision.stake_usd
        action = decision.action
        side = decision.side
        team1_won = row["winner"] == row["team1"]
        pnl = 0.0
        reward = 0.0
        if action == "BET" and stake > 0:
            pnl = _pnl_for_outcome(side=side, team1_won=team1_won, stake=stake, fee_rate=fee_rate)
            reward = bandit.update(x, stake, pnl)
            remaining_budget -= stake

        logs.append(
            {
                "date": row["date"],
                "team1": row["team1"],
                "team2": row["team2"],
                "winner": row["winner"],
                "action": action,
                "side": side,
                "stake_usd": stake,
                "remaining_budget": remaining_budget,
                "pnl": pnl,
                "risk_adjusted_reward": reward,
                "score": decision.score,
            }
        )

    out = pd.DataFrame(logs)
    out["cum_pnl"] = out["pnl"].cumsum()
    out["equity_peak"] = out["cum_pnl"].cummax()
    out["drawdown"] = out["cum_pnl"] - out["equity_peak"]

    trades = out[out["stake_usd"] > 0]
    if trades.empty:
        metrics = {
            "trades": 0,
            "pnl": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "hit_rate": 0.0,
            "avg_stake": 0.0,
            "turnover": 0.0,
            "profit_factor": 0.0,
        }
    else:
        rets = trades["pnl"] / trades["stake_usd"].replace(0, np.nan)
        sharpe = np.sqrt(252) * rets.mean() / (rets.std() + 1e-9)
        gross_profit = trades.loc[trades["pnl"] > 0, "pnl"].sum()
        gross_loss = abs(trades.loc[trades["pnl"] < 0, "pnl"].sum())
        metrics = {
            "trades": int(len(trades)),
            "pnl": float(trades["pnl"].sum()),
            "sharpe": float(sharpe),
            "max_drawdown": float(out["drawdown"].min()),
            "hit_rate": float((trades["pnl"] > 0).mean()),
            "avg_stake": float(trades["stake_usd"].mean()),
            "turnover": float(trades["stake_usd"].sum()),
            "profit_factor": float(gross_profit / (gross_loss + 1e-9)),
        }
    return out, metrics
