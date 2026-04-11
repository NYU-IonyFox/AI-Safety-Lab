#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"

SLM_BACKEND="${SLM_BACKEND:-mock}"
LOCAL_SLM_MODE="${LOCAL_SLM_MODE:-http}"

if [[ "${SLM_BACKEND,,}" == "local" ]] && [[ "${LOCAL_SLM_MODE,,}" == "hf" ]]; then
  "$PYTHON_BIN" -m pip install -e ".[local-hf]"
else
  "$PYTHON_BIN" -m pip install -e .
fi

"$PYTHON_BIN" -m uvicorn app.main:app --reload --port 8080
