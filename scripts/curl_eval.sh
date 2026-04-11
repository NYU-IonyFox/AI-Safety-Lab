#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

API_BASE="${API_BASE:-http://127.0.0.1:8080}"

curl -sS -X POST "$API_BASE/v1/evaluations" \
  -H "Content-Type: application/json" \
  --data-binary @examples/evaluation_request.json

echo
