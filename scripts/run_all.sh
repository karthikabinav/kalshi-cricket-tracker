#!/usr/bin/env bash
set -euo pipefail

CONFIG=${1:-configs/default.yaml}

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "No python interpreter found (python3/python)."
  exit 1
fi

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "pip unavailable for ${PYTHON_BIN}. Create/activate a venv with pip or install python3-pip."
  exit 1
fi

"$PYTHON_BIN" -m pip install -e '.[dev]'
"$PYTHON_BIN" -m pytest -q
"$PYTHON_BIN" -m kalshi_cricket_tracker.cli run-daily --config "$CONFIG"
"$PYTHON_BIN" -m kalshi_cricket_tracker.cli backtest --config "$CONFIG"
"$PYTHON_BIN" -m kalshi_cricket_tracker.cli bandit-backtest --config "$CONFIG"

echo "Done. Artifacts in $($PYTHON_BIN - <<PY
from kalshi_cricket_tracker.config import load_config
print(load_config("$CONFIG").runtime.artifact_dir)
PY
)"
