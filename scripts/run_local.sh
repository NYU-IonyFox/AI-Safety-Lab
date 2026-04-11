#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m pip install -e .
"$PYTHON_BIN" -m uvicorn app.main:app --reload --port 8080
