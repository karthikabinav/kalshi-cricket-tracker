# BTC15 Volatility Trading via BwK — Implementation Work Order

Source: user-provided March 2026 handoff doc.

## Strategy framing
This is a **volatility / mean-reversion** strategy on Kalshi BTC15 contract prices, not a directional BTC prediction strategy.

Goal:
- buy contract dips and sell recoveries within each 15-minute window
- prefer round-trips within the window
- do not rely on settlement prediction alone
- manage capital using an Adversarial Bandits with Knapsacks framing

## Core claims from the spec
- market: KXBTC15M / BTC15 style 15-minute Bitcoin binary markets
- strategy: volatility capture via mean-reversion on contract price
- budget: $100 starting budget
- intended execution: multiple short round-trips within a window
- fee-aware execution is mandatory
- maker entry + taker exit is preferred when EV justifies it
- budget recycling via negative-cost sell actions is central

## Required implementation areas

### 1. Fee model
Implement exact configurable fee helpers for:
- maker fee
- taker fee
- round-trip all-in friction
- fee-aware buy/sell cost model

Required mapping:
- BUY cost = ask * qty + maker_fee(ask, qty)
- SELL cost = -(bid * qty - taker_fee(bid, qty))
- SELL reward = (bid - entry) * qty - maker_fee(entry, qty) - taker_fee(bid, qty)

### 2. Vol-trading state/action system
State-dependent arms:
- FLAT:
  - buy_yes_15
  - buy_yes_8
  - hold
  - buy_no_8
  - buy_no_15
- LONG YES:
  - sell_yes
  - hold_position
- LONG NO:
  - sell_no
  - hold_position

Need a clear implementation for:
- feasible actions by current position state
- state transitions after fills/exits
- mark-to-market updates while holding

### 3. BwK / Lagrangian formulation
Implement a practical scaffold for:
- reward r(t,a)
- cost c(t,a)
- lagrangian objective g(t,a) = r(t,a) - lambda * c(t,a)
- negative-cost sell handling for capital recycling
- budget-aware action choice

Initial goal is paper-mode correctness and auditability, not theoretical proof machinery.

### 4. Market microstructure inputs
Model / capture at least:
- current YES/NO bid/ask
- spread
- depth
- recent trades if available
- time remaining in 15-minute window
- distance from target / local mid behavior
- local mean-reversion signal or normalized dip/recovery measure

### 5. Decision logic
Need decision outputs that support:
- buy entry
- sell exit
- hold flat
- hold position
- skip

Decisions must remain conservative and fee-aware.

### 6. Logging
Log every step needed for auditability:
- timestamp
- ticker
- state
- chosen action
- qty
- bid/ask
- fees
- spread/slippage assumptions
- lagrangian score / EV proxy
- resulting capital
- realized / unrealized pnl

### 7. Dashboard/data compatibility
Ensure outputs can feed the dashboard with:
- pnl
- transaction volume
- recent trades
- action history

## Constraints
- paper-first
- safe-by-default
- no live trading enabled by default
- do not assume manual performance claims are validated
- do not hardcode unrealistic guaranteed profits
- treat "$10 per 15-minute window on $100" as an unverified claim, not a target guarantee

## First-pass milestone recommendation
1. Implement fee helpers + unit tests
2. Implement state/action machine for flat/long states
3. Implement paper-mode BwK scorer with negative-cost sell support
4. Add log outputs and sample replay harness
5. Only then consider live API integration changes

## Status after this implementation pass
Implemented in code (paper-only scaffold):
- fee helpers matching the spec mapping (`maker_fee`, `taker_fee`, `buy_cost`, `sell_cost`, `sell_reward`, `round_trip_friction`)
- explicit flat/long-yes/long-no feasible action map
- state transitions for entry/exit/hold
- mark-to-market helper for held YES/NO inventory
- paper-mode BwK action evaluator with Lagrangian score and negative-cost sell handling for budget recycling

Still pending for the next pass:
- wire the new BwK scorer into `BTC15mExecutionAgent.evaluate()` / execution logs
- persist open-position inventory and recycled budget in the risk state
- add richer microstructure features from live snapshots / replay traces
- replace the remaining directional fair-value heuristic with explicit mean-reversion entry/exit logic
