# BTC 15m Mean-Reversion Execution Agent Spec

## Objective
Run a **paper-first BTC 15-minute Kalshi strategy** that trades only in the **middle 9 minutes** of each 15-minute contract and avoids both opening price discovery and end-of-market resolution chaos.

This is a **mean-reversion / microstructure** strategy, not a last-minute momentum strategy.

## Allowed trading window
For each 15-minute market:
- **No trades in the first 3 minutes** after market open
- **No trades in the last 3 minutes** before market close
- **Only trade in the middle 9 minutes**

In current implementation terms, with a 15-minute contract:
- allowed when **3 < time_remaining_min <= 12**
- blocked when **time_remaining_min <= 3**
- blocked when **time_remaining_min > 12**

## Core hypothesis
The market is most exploitable in the middle section of the contract, where:
- opening discovery noise has already passed
- final settlement chasing has not started yet
- temporary dislocations can revert toward local fair value / microprice / short-horizon equilibrium

## Strategy family
Two evaluation paths currently exist in code:

1. **Standard EV path**
   - estimates a short-horizon fair value from market state features
   - compares fair value vs current ask prices
   - enters only if net EV remains positive after fees, slippage, and safety buffer

2. **Vol/BwK paper path** (enabled in paper config)
   - treats the contract as a short-horizon mean-reversion / inventory-control problem
   - evaluates buy / hold / sell actions with reward-cost tradeoffs
   - uses a bandwidth/knapsack-style cost penalty and inventory-aware logic

## Hard pre-trade gates
A trade is immediately rejected if any of the following is true:
- agent disabled in config
- market is not BTC15-compatible
- rules are empty / ambiguous
- market status is not open/active/trading
- inside the first-3-minute no-trade region
- inside the final-3-minute no-trade region
- spread too wide
- depth too low
- order book instability too high
- max simultaneous positions hit
- daily loss limit hit
- consecutive loss stop triggered
- hourly trade cap hit
- recent bad-slippage stop triggered

## Market-quality requirements
The strategy assumes the market is only tradable when:
- spread is tight enough for controlled entry/exit
- top-of-book depth is sufficient
- repricing is not excessively unstable
- recent trade flow / imbalance are usable as short-horizon state inputs

## Standard EV description
The standard EV estimator computes an internal fair value using a weighted blend of:
- thesis price if supplied, otherwise contract mid
- microprice
- order book imbalance
- recent trade buy ratio
- settlement signal strength

Then it applies penalties for:
- realized volatility
- timing chaos near the forbidden boundary

For each side it estimates:
- gross edge vs current ask
- fee cost
- slippage cost
- net EV after safety buffer

It only recommends entry when:
- tradeability gates pass
- net EV exceeds configured minimum
- size recommendation is non-zero

## Vol/BwK paper path description
The paper config currently enables the Vol/BwK path. Conceptually:
- if local price deviation implies mean reversion opportunity, it may buy YES or buy NO
- if already in inventory and the move reverts / score turns negative, it exits
- if signal is weak, it holds or skips

This path is inventory-aware and capital-aware.

## Position/risk rules
- paper mode by default
- one BTC directional position at a time by default
- max dollars per trade enforced by config
- capital accounting updated after each paper action
- realized and unrealized round-trip PnL tracked in risk state
- no martingale / no doubling down / no averaging down

## Expected behavior by time region
- **13-15 min remaining**: NO TRADE (opening/no-trade region)
- **3-12 min remaining**: strategy may evaluate and trade if all filters pass
- **0-3 min remaining**: NO TRADE (closing/no-trade region)

## Logging requirements
Before every candidate decision log:
- ticker
- time remaining
- spread/depth/stability summary
- inventory/capital context
- chosen side/action
- confidence
- reason for trade or abstain

After every paper action log:
- entry time
- ticker / side / action
- limit price / size
- fee/cost/reward metrics
- resulting capital
- realized/unrealized round-trip PnL

## Implementation alignment checklist
The code is aligned if tests verify at least:
- disabled agent => NO TRADE
- first-3-minute block => NO TRADE
- final-3-minute block => NO TRADE
- mid-window eligible case => TRADE when signals are favorable
- spread/depth/risk gates block correctly
- open-position negative turn => EXIT
- paper execution writes candidate / trade / state logs
- inventory transitions FLAT -> LONG -> FLAT correctly in paper mode
- capital increases after a profitable round trip in paper mode

## Live progression rule
Do not enable live submission until:
1. algorithm description and code agree,
2. unit tests cover the intended policy strongly,
3. real Kalshi market-data polling is verified in paper mode,
4. logs and dashboard confirm correct state transitions.
