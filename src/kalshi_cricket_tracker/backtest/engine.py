from __future__ import annotations

import numpy as np
import pandas as pd


def run_backtest(labeled_matches: pd.DataFrame, fee_bps: float = 10.0) -> tuple[pd.DataFrame, dict]:
    df = labeled_matches.copy().sort_values("date")
    df = df[df["stake_usd"] > 0].copy()
    if df.empty:
        return df, {"trades": 0, "pnl": 0.0, "hit_rate": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}

    fee_rate = fee_bps / 10000

    def pnl_row(r):
        win = (r["action"] == "BUY_YES" and r["winner"] == r["team1"]) or (r["action"] == "BUY_NO" and r["winner"] != r["team1"])
        gross = r["stake_usd"] if win else -r["stake_usd"]
        return gross - abs(r["stake_usd"]) * fee_rate

    df["trade_pnl"] = df.apply(pnl_row, axis=1)
    df["cum_pnl"] = df["trade_pnl"].cumsum()
    df["equity_peak"] = df["cum_pnl"].cummax()
    df["drawdown"] = df["cum_pnl"] - df["equity_peak"]

    returns = df["trade_pnl"] / df["stake_usd"].replace(0, np.nan)
    sharpe = np.sqrt(252) * returns.mean() / (returns.std() + 1e-9)

    metrics = {
        "trades": int(len(df)),
        "pnl": float(df["trade_pnl"].sum()),
        "hit_rate": float((df["trade_pnl"] > 0).mean()),
        "sharpe": float(sharpe),
        "max_drawdown": float(df["drawdown"].min()),
    }
    return df, metrics
