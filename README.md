# kalshi-cricket-tracker

MVP research assistant for cricket-driven Kalshi market exploration (**paper mode by default**), plus a separate **BTC 15-minute execution agent** that is disabled by default and only trades when all configured safety checks pass.

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
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

If your host Python lacks `venv`/`pip` (common on minimal Debian images), install first:
```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
```

## Quickstart
```bash
kct run-daily --config configs/default.yaml
kct backtest --config configs/default.yaml
kct bandit-backtest --config configs/default.yaml
kct arb-backtest --snapshots-csv docs/sample_arb_snapshots.csv --config configs/default.yaml
kct btc15m-exec --snapshot-json docs/btc15m_snapshot.example.json --config configs/default.yaml
streamlit run scripts/dashboard.py -- --config configs/default.yaml
```

Preflight checks:
```bash
python -m py_compile $(find src -name '*.py')
python -m pytest -q
```

Or run end-to-end:
```bash
./scripts/run_all.sh
```

## CLI
- `kct run-daily`: ingest + features + daily signals + paper fills (or live if explicitly enabled)
- `kct backtest`: rule-based backtest
- `kct bandit-backtest`: contextual bandit backtest
- `kct arb-backtest`: snapshot-based under/over-calibration trading backtest with open/close logic
- `kct btc15m-exec`: evaluate a single BTC 15m market snapshot, log the candidate decision, and optionally send a live limit order only when global live-trading guards are explicitly enabled
- `kct dashboard`: prints launch command

## Odds adapters
Configured under `odds:` in YAML:
- `provider: proxy` (default) uses model-probability shrinkage
- `provider: csv` reads `event_id,market_prob_team1` from a local CSV
- `provider: provider_stub` placeholder for a future real API provider

## Reference win-prob adapters (model side)
Configured under `winprob:` in YAML:
- `provider: elo_only` (default) uses Elo-derived probability
- `provider: csv` reads `event_id,external_prob_team1` from a local CSV
- `provider: cricinfo` best-effort JSON parser using `cricinfo_endpoint_template` (format with `{event_id}`)

If `external_prob_team1` is available for a fixture, signals use it as `model_prob_team1` and set `model_prob_source=external`.

## Live trading safety defaults
Default config is **safe/paper**:
- `trading.mode: paper`
- `trading.enable_live_trading: false`
- `trading.live_confirmation_phrase: ""`
- `btc15m.enabled: false`

Live mode is blocked unless all of these are set:
1. `trading.mode: live`
2. `trading.enable_live_trading: true`
3. `trading.live_confirmation_phrase: I_UNDERSTAND_AND_ACCEPT_LIVE_TRADING_RISK`
4. Environment variables with credentials:
   - `KALSHI_API_KEY`
   - `KALSHI_API_SECRET`
5. Explicit BTC agent opt-in in config:
   - `btc15m.enabled: true`

If any guard fails, `run-daily` / `btc15m-exec` abort before placing live orders.

## BTC 15m execution agent
The BTC 15m agent is intentionally narrow:
- Only accepts tickers that look like BTC 15-minute markets
- Defaults to **NO TRADE** unless all required rule, timing, liquidity, spread, stability, edge, confidence, and risk checks pass
- Uses **limit orders only**
- Caps notional at `$100` per trade and one open directional BTC position by default
- Logs every candidate decision to `artifacts/btc15m_candidate_decisions.jsonl`
- Logs every submitted/paper trade to `artifacts/btc15m_executed_trades.jsonl`

### Snapshot input
`btc15m-exec` currently expects a JSON snapshot with the fields used by the decision engine. Example:

```json
{
  "ticker": "KXBTCD-15M-TEST",
  "rules": "Resolves to YES if BTC settles above threshold at close.",
  "status": "open",
  "close_time": "2026-03-01T00:08:00Z",
  "yes_ask_cents": 58,
  "yes_bid_cents": 57,
  "no_ask_cents": 43,
  "no_bid_cents": 42,
  "best_yes_ask_size": 50,
  "best_yes_bid_size": 60,
  "best_no_ask_size": 55,
  "best_no_bid_size": 65,
  "orderbook_stability_bps": 20,
  "thesis_price_cents": 63
}
```

The user should place Kalshi credentials in environment variables only. Recommended workflow:
```bash
cp .env.kalshi.example .env.kalshi
# edit the values, then source it into the shell
set -a && source .env.kalshi && set +a
```

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
