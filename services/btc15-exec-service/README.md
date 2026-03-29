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
- paper-mode order manager stub with unrealized PnL calculation
- stub adapters for Binance BTC feed and Kalshi market access
- Vitest suite covering config, derivatives, signals, and paper order flow

## Layout
- `src/config/env.ts` - env schema and typed config
- `src/core/derivatives.ts` - rolling price-buffer derivatives
- `src/core/signals.ts` - pure signal logic
- `src/order/paperOrderManager.ts` - paper execution state machine
- `src/adapters/binanceFeed.ts` - Binance adapter stub
- `src/adapters/kalshi.ts` - Kalshi adapter interface + paper stub
- `src/index.ts` - bootstrap/runtime skeleton
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

## Notes
- `SERVICE_MODE=paper` is the intended default for this phase.
- No live Kalshi submission is implemented or enabled in this pass.
- Zeabur-friendly deployment hooks (health endpoint, Docker/package wiring, live runtime loop) are intentionally deferred until paper validation is satisfactory.
