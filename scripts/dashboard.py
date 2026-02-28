from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from kalshi_cricket_tracker.config import load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    args, _ = parser.parse_known_args()

    cfg = load_config(args.config)
    art = Path(cfg.runtime.artifact_dir)

    st.title("Kalshi Cricket Tracker (Paper Research)")

    sig_fp = art / "daily_signals.csv"
    bt_fp = art / "backtest_trades.csv"
    bbt_fp = art / "bandit_backtest.csv"

    if sig_fp.exists():
        st.subheader("Daily Signals")
        st.dataframe(pd.read_csv(sig_fp).head(50))

    if bt_fp.exists():
        st.subheader("Rule-Based Backtest")
        bt = pd.read_csv(bt_fp)
        if not bt.empty and "cum_pnl" in bt.columns:
            fig = px.line(bt, y="cum_pnl", title="Rule-based Cumulative PnL")
            st.plotly_chart(fig, use_container_width=True)

    if bbt_fp.exists():
        st.subheader("Bandit Backtest")
        bbt = pd.read_csv(bbt_fp)
        st.dataframe(bbt.tail(30))
        if not bbt.empty and "cum_pnl" in bbt.columns:
            fig2 = px.line(bbt, y="cum_pnl", title="Bandit Cumulative PnL")
            st.plotly_chart(fig2, use_container_width=True)

    for name in ["backtest_metrics.json", "bandit_metrics.json"]:
        fp = art / name
        if fp.exists():
            st.subheader(name)
            st.json(json.loads(fp.read_text()))


if __name__ == "__main__":
    main()
