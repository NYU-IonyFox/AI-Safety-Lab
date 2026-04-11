#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_PROFILE="${INSTALL_PROFILE:-local-hf}"

if [[ "$INSTALL_PROFILE" == "local-hf" ]]; then
  if ! "$PYTHON_BIN" -m pip install -e ".[local-hf]"; then
    echo "Local HF dependencies were not installed; falling back to base install and rules_fallback execution."
    "$PYTHON_BIN" -m pip install -e .
  fi
else
  "$PYTHON_BIN" -m pip install -e .
fi

"$PYTHON_BIN" -m uvicorn app.main:app --port 8080 &
BACKEND_PID=$!

for _ in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS http://127.0.0.1:8080/health >/dev/null

"$PYTHON_BIN" -m streamlit run frontend/streamlit_app.py --server.headless true &
FRONTEND_PID=$!

for _ in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:8501/ >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Backend:  http://127.0.0.1:8080/health"
echo "Frontend: http://127.0.0.1:8501"
echo "Press Ctrl+C to stop both services."

wait -n "$BACKEND_PID" "$FRONTEND_PID"
