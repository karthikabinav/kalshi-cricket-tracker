# BTC15M Paper Tuning Notes

## Reason for tuning
Observed live BTC15m markets were repeatedly blocked by:
- spread too wide
- high orderbook instability proxy
- low top-of-book depth

The strict defaults were preventing any paper fills, which made it hard to validate end-to-end behavior on live markets.

## Paper-only tuning changes
`configs/btc15m_paper.yaml` now uses looser paper thresholds:
- `min_depth_contracts: 1`
- `max_spread_cents: 4`
- `max_orderbook_instability_bps: 9000.0`

## Intent
This is for **paper exploration only** so the workflow can actually observe entries/exits on live BTC15m markets.
These looser thresholds should **not** be treated as production-safe defaults.

## Guardrails still active
Even with looser paper filters, the following still apply:
- no trades in first 3 minutes
- no trades in last 3 minutes
- risk limits
- paper mode only
- logged candidate decisions / state trace / trades
