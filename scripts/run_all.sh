#!/usr/bin/env bash
set -euo pipefail

CONFIG=${1:-configs/default.yaml}

python -m pip install -e '.[dev]'
kct run-daily --config "$CONFIG"
kct backtest --config "$CONFIG"
kct bandit-backtest --config "$CONFIG"

echo "Done. Artifacts in $(python - <<'PY'
from kalshi_cricket_tracker.config import load_config
print(load_config('$CONFIG').runtime.artifact_dir)
PY
)"
