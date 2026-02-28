# kalshi-cricket-tracker

MVP research assistant for cricket-driven Kalshi market exploration (paper-only).

## Scope
- Public data ingest (Cricsheet historical + ESPN fixtures best-effort)
- Feature engineering (Elo, recent form, edge features)
- Rule-based daily signal generation + risk limits
- Contextual bandit strategy (budget-constrained, risk-adjusted)
- Backtesting metrics: PnL, Sharpe, max drawdown, hit-rate
- Mock Kalshi integration (paper fills)
- CLI + minimal Streamlit dashboard
- Tests + reproducible scripts

## Install
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

## Quickstart
```bash
kct run-daily --config configs/default.yaml
kct backtest --config configs/default.yaml
kct bandit-backtest --config configs/default.yaml
streamlit run scripts/dashboard.py -- --config configs/default.yaml
```

Or run end-to-end:
```bash
./scripts/run_all.sh
```

## CLI
- `kct run-daily`: ingest + features + daily signals + paper fills
- `kct backtest`: rule-based backtest
- `kct bandit-backtest`: contextual bandit backtest
- `kct dashboard`: prints launch command

## Files
- `src/kalshi_cricket_tracker/strategy/contextual_bandit.py` reusable bandit strategy module
- `docs/BANDIT.md` equations and assumptions
- `artifacts/` outputs (`daily_signals.csv`, `backtest_metrics.json`, `bandit_metrics.json`, ...)

## Notes
- No live trades are executed.
- Kalshi integration is mocked via `MockKalshiPaperClient`.
- Replace proxy odds with licensed/official odds APIs before any production use.
