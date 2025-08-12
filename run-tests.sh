#!/usr/bin/env bash
set -euo pipefail

echo "==> starting run-tests.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Echo every command for visibility
set -x

# Pick python
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

# Create/activate venv
VENV="$ROOT/.venv"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
# shellcheck disable=SC1090
source "$VENV/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT/requirements.txt"

# Base test deps (no -q so you see progress)
python -m pip install pytest pytest-asyncio httpx

TARGET="${1:-quick}"
PYTEST_EXPR=""
PYTEST_EXTRA=""
SERVER_PID_FILE="$ROOT/.pytest-uvicorn.pid"

cleanup() {
  set +e
  if [ -f "$SERVER_PID_FILE" ]; then
    kill "$(cat "$SERVER_PID_FILE")" 2>/dev/null || true
    rm -f "$SERVER_PID_FILE"
  fi
}
trap cleanup EXIT

case "$TARGET" in
  unit) PYTEST_EXPR="unit" ;;
  integration) PYTEST_EXPR="integration" ;;
  quick|"") PYTEST_EXPR="unit or integration" ;;
  all) PYTEST_EXPR="" ;; # everything
  e2e)
    python -m pip install pytest-playwright playwright
    python -m playwright install
    # Start server in background and log visibly
    UVICORN="uvicorn --app-dir src soullink_tracker.main:app --host 127.0.0.1 --port 8000"
    bash -c "($UVICORN > .pytest-uvicorn.log 2>&1 & echo \$! > '$SERVER_PID_FILE')"
    # Wait until it’s up (max ~10s)
    for i in {1..50}; do
      if curl -sf http://127.0.0.1:8000/docs >/dev/null; then
        echo "Server is up."
        break
      fi
      sleep 0.2
    done
    PYTEST_EXTRA="--base-url http://127.0.0.1:8000"
    PYTEST_EXPR="e2e"
    ;;
  *)
    set +x
    echo "Unknown target: $TARGET"
    echo "Usage: $0 [quick|unit|integration|e2e|all]"
    exit 2
    ;;
esac

export PYTHONPATH=src

# Show pytest version and collected tests for visibility
pytest --version
pytest -k "" ${PYTEST_EXTRA:-} ${PYTEST_EXPR:+-m "$PYTEST_EXPR"} "$ROOT/tests"
