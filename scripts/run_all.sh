#!/usr/bin/env bash
set -euo pipefail

CONFIG=${1:-configs/default.yaml}

if ! python -m pip --version >/dev/null 2>&1; then
  echo "python -m pip unavailable. Install python3-pip (and python3-venv recommended) first."
  exit 1
fi

python -m pip install -e '.[dev]'
python -m pytest -q
kct run-daily --config "$CONFIG"
kct backtest --config "$CONFIG"
kct bandit-backtest --config "$CONFIG"

echo "Done. Artifacts in $(python - <<'PY'
from kalshi_cricket_tracker.config import load_config
print(load_config('$CONFIG').runtime.artifact_dir)
PY
)"
