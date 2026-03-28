# BTC15 EV Next Pass Work Order

Source of truth: uploaded BTC15 EV spec (conservative Kalshi BTC15 execution agent).

## Goal
Upgrade the current guarded BTC15 scaffold into an EV-driven paper-first execution engine.

## Requirements
1. Implement `estimate_trade_ev(state)` returning:
   - fair_prob
   - tp_hit_prob
   - stop_hit_prob
   - expected_settlement_value
   - gross_edge
   - fees
   - slippage
   - net_ev
   - recommended_size
   - recommended_action

2. Implement `decide_trade(state)` returning only:
   - ENTER_LONG_YES
   - ENTER_LONG_NO
   - HOLD
   - EXIT
   - SKIP

3. Add state features:
   - BTC spot
   - contract price
   - distance from target
   - time to cutoff
   - short-horizon realized vol
   - microprice / order-book imbalance
   - spread
   - depth
   - recent trades
   - settlement-rule-aware signals

4. Add exact cost modeling:
   - maker vs taker handling
   - round-trip fees
   - slippage estimates
   - net EV after all costs
   - configurable safety buffer

5. Add continuous re-evaluation for open positions:
   - recompute EV while in position
   - early exit if EV turns negative
   - account for near-cutoff settlement mechanics

6. Add rolling evaluation metrics:
   - win rate
   - average win/loss
   - expectancy per trade
   - realized vs expected slippage
   - maker fill rate
   - pnl by regime
   - pnl by time-to-expiry bucket
   - pnl by distance-to-target bucket

7. Keep strict safety:
   - paper mode first
   - no live trading by default
   - preserve hard risk caps
   - prefer SKIP on weak confidence or poor data quality

## Non-goal
Do NOT optimize to an unrealistic fixed profit target like "$50/hour on $100 principal".
Optimize for long-run positive expectancy net of fees/slippage.

## Deliverables
- code changes
- tests
- sample state/snapshot format
- README/docs update
- paper-mode run example
