# kalshi-cricket-tracker

MVP research assistant for cricket-driven Kalshi market exploration (**paper mode by default**).

## Scope
- Public data ingest (Cricsheet historical + ESPN fixtures best-effort)
- Feature engineering (Elo, recent form, edge features)
- Rule-based daily signal generation + risk limits
- Pluggable odds adapters (proxy, local CSV, provider stub)
- Contextual bandit strategy (budget-constrained, risk-adjusted)
- Backtesting metrics: PnL, Sharpe, max drawdown, hit-rate
- Mock Kalshi integration (paper fills)
- Optional Kalshi REST scaffold (disabled unless explicitly enabled)
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
- `kct run-daily`: ingest + features + daily signals + paper fills (or live if explicitly enabled)
- `kct backtest`: rule-based backtest
- `kct bandit-backtest`: contextual bandit backtest
- `kct dashboard`: prints launch command

## Odds adapters
Configured under `odds:` in YAML:
- `provider: proxy` (default) uses model-probability shrinkage
- `provider: csv` reads `event_id,market_prob_team1` from a local CSV
- `provider: provider_stub` placeholder for a future real API provider

## Live trading safety defaults
Default config is **safe/paper**:
- `trading.mode: paper`
- `trading.enable_live_trading: false`
- `trading.live_confirmation_phrase: ""`

Live mode is blocked unless all of these are set:
1. `trading.mode: live`
2. `trading.enable_live_trading: true`
3. `trading.live_confirmation_phrase: I_UNDERSTAND_AND_ACCEPT_LIVE_TRADING_RISK`
4. Environment variables with credentials:
   - `KALSHI_API_KEY`
   - `KALSHI_API_SECRET`

If any guard fails, `run-daily` aborts before placing orders.

## Files
- `src/kalshi_cricket_tracker/strategy/contextual_bandit.py` reusable bandit strategy module
- `src/kalshi_cricket_tracker/odds.py` odds adapter interface + implementations
- `src/kalshi_cricket_tracker/execution/kalshi.py` mock executor + optional REST scaffold
- `src/kalshi_cricket_tracker/execution/guards.py` live-trading safety checks
- `docs/BANDIT.md` equations and assumptions
- `artifacts/` outputs (`daily_signals.csv`, `backtest_metrics.json`, `bandit_metrics.json`, ...)

## Notes
- Live trading is disabled by default.
- Kalshi live client is scaffold-level and should be validated against official API docs before production.
