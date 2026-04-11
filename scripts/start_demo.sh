#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m pip install -e .

"$PYTHON_BIN" -m uvicorn app.main:app --port 8080 &
BACKEND_PID=$!

"$PYTHON_BIN" -m streamlit run frontend/streamlit_app.py --server.headless true &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Backend:  http://127.0.0.1:8080/health"
echo "Frontend: http://127.0.0.1:8501"
echo "Press Ctrl+C to stop both services."

wait -n "$BACKEND_PID" "$FRONTEND_PID"
