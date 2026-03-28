# BTC15 Dashboard

Static Vercel-friendly dashboard for the Kalshi BTC15 workflow.

## Architecture
- **Static frontend**: `index.html` + `styles.css` + `app.js`
- **Static data payload**: `data/dashboard-data.json`
- **Exporter**: `scripts/build_dashboard_data.py` reads repo artifacts and regenerates the JSON payload

This keeps deployment simple: Vercel serves the dashboard as plain static files, with no runtime filesystem dependency.

## Local run
From the repo root:

```bash
cd dashboard
python3 -m http.server 4173
```

Open <http://localhost:4173>.

## Refresh dashboard data from artifacts
From the repo root:

```bash
.venv/bin/python scripts/build_dashboard_data.py
```

This reads from:
- `artifacts/btc15m_executed_trades.jsonl`
- `artifacts/btc15m_candidate_decisions.jsonl`
- `artifacts/paper_fills.csv`

and writes:
- `dashboard/data/dashboard-data.json`

## Data model assumptions
- **PnL** is the sum of numeric `pnl` values on executed trades. Missing/null values are treated as unrealized/unknown and excluded from realized PnL.
- **Transaction volume** is `stake_usd` when available in `raw_response`; otherwise it falls back to `filled_size * limit_price / 100`.
- **Trade status** is `OPEN` when `pnl` is missing and no `exit_price` is present, otherwise `CLOSED`.
- **Decision log** is derived from `btc15m_candidate_decisions.jsonl` and shown as context for recent non-trade / trade decisions.
- If no live artifact rows exist, the dashboard still renders an empty-safe state using the bundled JSON payload.

## Auto-refresh behavior
- The browser polls `data/dashboard-data.json` every 60 seconds with `cache: 'no-store'` plus a timestamp query param, so an already-open dashboard tab picks up newly deployed static snapshots without a manual reload.
- The page only re-renders when the fetched payload signature changes, which avoids unnecessary churn.
- This does **not** generate new data on Vercel. Fresh dashboard content still requires regenerating `dashboard/data/dashboard-data.json` from repo artifacts and then redeploying the static site.

## Vercel
Deploy this `dashboard/` directory as the Vercel project root. No build command is required.

Redeploy implications:
1. Run `.venv/bin/python scripts/build_dashboard_data.py` after artifact changes.
2. Commit/push the updated `dashboard/data/dashboard-data.json` (or otherwise trigger a deployment containing it).
3. Vercel serves the new static snapshot, and open tabs pick it up on the next 60-second refresh cycle.
