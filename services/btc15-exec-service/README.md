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
- paper Kalshi adapter stub for market resolution / snapshots while auth and live orderbook work remain gated
- runtime loop that ingests Binance ticks, waits for enough samples, then evaluates paper decisions on an interval
- Vitest suite covering config, feed parsing/reconnect behavior, derivatives, runtime flow, signals, and paper order flow

## Layout
- `src/config/env.ts` - env schema and typed config
- `src/core/derivatives.ts` - rolling price-buffer derivatives
- `src/core/signals.ts` - pure signal logic
- `src/order/paperOrderManager.ts` - paper execution state machine
- `src/adapters/binanceFeed.ts` - live Binance trade stream adapter
- `src/adapters/kalshi.ts` - Kalshi adapter interface + paper stub
- `src/runtime.ts` - paper runtime orchestration
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
- `SERVICE_MODE=paper` is the only allowed mode in this phase.
- No live Kalshi submission is implemented or enabled.
- Kalshi market access remains stubbed/paper until auth/orderbook work is explicitly completed.
- Runtime output is structured JSON so paper runs can be tailed and audited.

## Key runtime env vars
- `MIN_PRICE_SAMPLES` - minimum Binance ticks before the first evaluation cycle
- `EVAL_INTERVAL_MS` - paper decision loop interval
- `BINANCE_RECONNECT_BASE_MS` / `BINANCE_RECONNECT_MAX_MS` - reconnect backoff window
- `BINANCE_STALE_THRESHOLD_MS` - force reconnect if the stream goes quiet too long
