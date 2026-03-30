# BTC15 Node Execution Service Spec — Work Order

Source: user-provided deployment design PDF.

## Intent
After paper testing is validated, prepare a lightweight Node.js execution service for BTC15 momentum scalping on Kalshi.

## Important gate
Do NOT deploy live execution agents yet.
Deployment prep should happen only after paper testing is satisfactory.
Current phase: convert the PDF into an implementable engineering work order and keep deployment gated.

## Strategy summary from spec
- no LLM in loop
- Node.js execution service
- market: Kalshi BTC 15-minute candle markets
- entry: buy YES when contract price is 58-65c, BTC slope positive, acceleration non-negative
- exits:
  - take profit at +$10 unrealized PnL
  - stop loss at -$15 unrealized PnL
  - time stop with 3 minutes remaining
- never hold through candle close

## Proposed architecture
- BTC feed
  - Binance WebSocket primary
  - CoinGecko fallback only for dev/testing
- Kalshi market feed
  - active market discovery
  - orderbook polling / websocket if available
  - authenticated trading via RSA signing
- derivatives engine
  - rolling price buffer
  - slope / acceleration / volatility
- signal engine
  - pure logic, no model
  - exits first, then entries
- order manager
  - track position
  - limit entry
  - guaranteed exit path
- trade logger
  - SQLite or JSON
- notifications
  - Telegram/OpenClaw status hooks optional

## Required implementation slices
1. Node service skeleton
   - TypeScript/Node project
   - env/config loader
   - runtime loop
   - structured logging

2. BTC feed
   - Binance trade stream adapter
   - rolling in-memory buffer
   - reconnect handling
   - fallback stub for replay/dev

3. Derivatives engine
   - slope
   - acceleration
   - volatility
   - deterministic tests

4. Kalshi adapter
   - active BTC15 market resolution
   - orderbook fetch
   - authenticated order placement scaffold
   - RSA-PSS request signing
   - paper-mode adapter first

5. Signal engine
   - implement exact rule ordering:
     - FORCE_EXIT
     - TAKE_PROFIT
     - STOP_LOSS
     - WAIT
     - CAUTION
     - ENTER
   - exits first, entries second

6. Order manager
   - one active position at a time
   - entry with limit order semantics
   - exit path for immediate flattening
   - unrealized PnL calc

7. Paper-mode harness
   - run the service in simulation/paper mode first
   - support 15-minute full-window paper tests
   - write trade/event logs for auditability

8. Deployment prep only after paper validation
   - Zeabur-friendly packaging
   - healthcheck endpoint
   - env var contract
   - start command
   - but no live promotion until explicitly approved later

## Safety controls added in the current Node pass
- explicit `MODE=paper|live` selector, with `paper` as the default and `SERVICE_MODE` kept as a backwards-compatible alias
- secondary live arming gate via `LIVE_TRADING_ENABLED=true`
- explicit live-risk acknowledgement via `LIVE_CONFIRMATION_PHRASE=I_UNDERSTAND_AND_ACCEPT_LIVE_TRADING_RISK`
- live boot refusal when `EMERGENCY_STOP=true`
- required non-empty `KALSHI_MARKET_ALLOWLIST` before live boot
- runtime entry guards for:
  - market allowlist
  - max per-order notional
  - max daily realized loss
  - max open positions
- live Kalshi adapter/client interface scaffold exists, but real orderbook/auth/order placement remain intentionally unimplemented

## Constraints
- paper-first
- safe-by-default
- no live deployment yet
- no guaranteed profit claims
- keep OpenClaw loop updated via kalshi channel

## Recommended next step
Build the next live path slice behind the new safety gates:
- real Kalshi market discovery for active BTC15 tickers
- authenticated REST/WebSocket client with RSA-PSS signing
- order placement + cancel/flatten semantics
- persistent trade/risk ledger so daily loss and emergency-stop state survive restarts
