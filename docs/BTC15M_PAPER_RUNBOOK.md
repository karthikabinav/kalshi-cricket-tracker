# BTC15m Paper Runbook

## Purpose
Run the BTC 15m execution agent safely in paper mode against live Kalshi market data before enabling live order submission.

## Preconditions
- Virtualenv exists and dependencies are installed.
- Config: `configs/btc15m_paper.yaml`
- Risk state file exists or defaults are acceptable.
- You have an internal thesis price in YES cents for the chosen market.

## Step 1: Fetch a live BTC15m snapshot
Auto-discover nearest open BTC15m market:

```bash
.venv/bin/python -m kalshi_cricket_tracker.cli btc15m-fetch-live-snapshot \
  --config configs/btc15m_paper.yaml \
  --thesis-price-cents 60
```

Or target a specific ticker:

```bash
.venv/bin/python -m kalshi_cricket_tracker.cli btc15m-fetch-live-snapshot \
  --config configs/btc15m_paper.yaml \
  --ticker <KALSHI_BTC15M_TICKER> \
  --thesis-price-cents 60
```

Expected outcomes:
- If no open BTC15m market exists, the command should fail cleanly.
- If a market exists, a snapshot JSON is written under `artifacts/`.

## Step 2: Run paper decisioning directly from live market data

```bash
.venv/bin/python -m kalshi_cricket_tracker.cli btc15m-paper-live \
  --config configs/btc15m_paper.yaml \
  --thesis-price-cents 60 \
  --risk-json artifacts/btc15m_risk_state.example.json
```

Optional explicit ticker:

```bash
.venv/bin/python -m kalshi_cricket_tracker.cli btc15m-paper-live \
  --config configs/btc15m_paper.yaml \
  --ticker <KALSHI_BTC15M_TICKER> \
  --thesis-price-cents 60 \
  --risk-json artifacts/btc15m_risk_state.example.json
```

## Logs to inspect
- `artifacts/btc15m_candidate_decisions.jsonl`
- `artifacts/btc15m_executed_trades.jsonl`
- `artifacts/btc15m_state_trace.jsonl`
- `artifacts/btc15m_risk_state.json`

State trace now includes:
- inventory state / qty / entry price
- reward / cost / lagrangian score / fees
- resulting capital
- realized and unrealized round-trip PnL
- state before each paper action

## Replay a snapshot sequence
Use JSON or JSONL snapshots to replay a whole 15-minute window in paper mode:

```bash
.venv/bin/python -m kalshi_cricket_tracker.cli btc15m-replay \
  --config configs/btc15m_paper.yaml \
  --snapshots-json path/to/btc15m_sequence.jsonl
```

This updates the same risk-state JSON and appends to the paper logs, so replay runs stay audit-friendly.

## Promotion checklist before live mode
- Market discovery consistently finds the correct BTC15m contract.
- Snapshot parser correctly maps bid/ask/depth/rules/close time.
- At least several paper sessions run without malformed data or ambiguous rule handling.
- Risk state updates are real, not static placeholders.
- Kalshi auth/signing and order lifecycle handling are fully validated.
- First live launch should stop before first order unless explicitly approved again.

## Known limitation
Paper mode still depends on an externally supplied thesis price (`--thesis-price-cents`). The current code does not yet infer a BTC directional thesis autonomously from a market data model.
