# BTC15 Exec Service (Node/TypeScript skeleton)

Paper-first execution-service scaffold for the Kalshi BTC 15-minute strategy described in `docs/BTC15_NODE_EXEC_SERVICE_SPEC.md`.

## What is included in this pass
- TypeScript service scaffold under `services/btc15-exec-service`
- env/config loader via `dotenv` + `zod`
- rolling derivatives engine for slope / acceleration / volatility
- signal engine implementing the ordered PDF logic:
  - `FORCE_EXIT`
  - `TAKE_PROFIT`
  - `STOP_LOSS`
  - `WAIT`
  - `CAUTION`
  - `ENTER`
- paper-mode order manager stub with explicit bid-side exit / unrealized PnL handling for take-profit, stop-loss, and time-stop exits
- live Binance BTC trade stream adapter for paper mode with reconnect/backoff + stale-stream reset
- Kalshi adapter split into paper adapter + live adapter scaffold interface
- runtime risk guard for emergency stop, market allowlist, max order notional, daily loss cap, and max open positions
- runtime loop that ingests Binance ticks, waits for enough samples, then evaluates paper decisions on an interval
- Vitest suite covering config safety gates, feed parsing/reconnect behavior, derivatives, runtime flow, signals, and paper order flow

## Layout
- `src/config/env.ts` - env schema, typed config, and live-mode readiness assertions
- `src/core/derivatives.ts` - rolling price-buffer derivatives
- `src/core/risk.ts` - pre-trade safety/risk controls
- `src/core/signals.ts` - pure signal logic
- `src/order/paperOrderManager.ts` - paper execution state machine
- `src/adapters/binanceFeed.ts` - live Binance trade stream adapter
- `src/adapters/kalshi.ts` - Kalshi paper adapter + live-client scaffold
- `src/runtime.ts` - paper runtime orchestration with risk gating
- `src/index.ts` - bootstrap/runtime entrypoint
- `test/*.test.ts` - unit tests

## Run locally
```bash
cd services/btc15-exec-service
cp .env.example .env
npm install
npm test
npm run build
npm run dev
```

## Important constraints
- `MODE=paper` / `SERVICE_MODE=paper` is still the default and safest setting.
- Live mode now has explicit gates, but real authenticated Kalshi market discovery/order placement remains scaffold-only.
- `LIVE_TRADING_ENABLED=true` is required in addition to `MODE=live` before the service will even boot into live mode.
- `LIVE_CONFIRMATION_PHRASE=I_UNDERSTAND_AND_ACCEPT_LIVE_TRADING_RISK` is also required to mirror the Python-side explicit risk acknowledgement gate.
- `EMERGENCY_STOP=true` hard-blocks new live boot and all new entries.
- Runtime output is structured JSON so paper runs can be tailed and audited.

## Key runtime env vars
- `MODE` - preferred explicit execution mode selector (`paper` or `live`)
- `KALSHI_MARKET_ALLOWLIST` - comma-separated tickers allowed for entry; empty means unrestricted in paper mode
- `MAX_ORDER_NOTIONAL_DOLLARS` - per-entry notional cap
- `MAX_DAILY_LOSS_DOLLARS` - blocks new entries once realized losses breach the cap
- `MAX_OPEN_POSITIONS` - currently should stay `1`; runtime enforces this ceiling
- `LIVE_TRADING_ENABLED` - secondary live-trading arming switch
- `LIVE_CONFIRMATION_PHRASE` - must equal `I_UNDERSTAND_AND_ACCEPT_LIVE_TRADING_RISK` before live boot is allowed
- `EMERGENCY_STOP` - kill switch for live boot and all new entries
- `MIN_PRICE_SAMPLES` - minimum Binance ticks before the first evaluation cycle
- `EVAL_INTERVAL_MS` - paper decision loop interval
- `BINANCE_RECONNECT_BASE_MS` / `BINANCE_RECONNECT_MAX_MS` - reconnect backoff window
- `BINANCE_STALE_THRESHOLD_MS` - force reconnect if the stream goes quiet too long
