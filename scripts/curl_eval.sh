#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

API_BASE="${API_BASE:-http://127.0.0.1:8080}"
REQUEST_FILE="${REQUEST_FILE:-}"
SOURCE_TYPE="${SOURCE_TYPE:-github_url}"
GITHUB_URL="${GITHUB_URL:-}"
LOCAL_PATH="${LOCAL_PATH:-}"
TARGET_NAME="${TARGET_NAME:-Submitted Repository}"
DESCRIPTION="${DESCRIPTION:-Repository submission for AI safety review}"

if [[ -n "$REQUEST_FILE" ]]; then
  curl -sS -X POST "$API_BASE/v1/evaluations" \
    -H "Content-Type: application/json" \
    --data-binary "@$REQUEST_FILE"
  echo
  exit 0
fi

if [[ "$SOURCE_TYPE" == "github_url" && -z "$GITHUB_URL" ]]; then
  echo "Set GITHUB_URL or REQUEST_FILE before running this script." >&2
  exit 1
fi

if [[ "$SOURCE_TYPE" == "local_path" && -z "$LOCAL_PATH" ]]; then
  echo "Set LOCAL_PATH or REQUEST_FILE before running this script." >&2
  exit 1
fi

python3 - <<'PY' | curl -sS -X POST "$API_BASE/v1/evaluations" \
  -H "Content-Type: application/json" \
  --data-binary @-
import json
import os

source_type = os.environ["SOURCE_TYPE"]
payload = {
    "context": {
        "agent_name": os.environ.get("TARGET_NAME", "Submitted Repository"),
        "description": os.environ.get("DESCRIPTION", "Repository submission for AI safety review"),
        "domain": "Other",
        "capabilities": [],
        "high_autonomy": False,
    },
    "selected_policies": ["eu_ai_act", "us_nist", "iso", "unesco"],
    "conversation": [],
    "metadata": {},
    "submission": {
        "source_type": source_type,
        "github_url": os.environ.get("GITHUB_URL", ""),
        "local_path": os.environ.get("LOCAL_PATH", ""),
        "target_name": os.environ.get("TARGET_NAME", "Submitted Repository"),
        "description": os.environ.get("DESCRIPTION", "Repository submission for AI safety review"),
    },
}
print(json.dumps(payload))
PY

echo
