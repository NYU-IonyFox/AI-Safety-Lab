#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
MODEL_PRESET="${MODEL_PRESET:-gemma3-270m-it}"
START_DEMO=0
SKIP_SMOKE_TEST=0

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap_local_slm.sh [--preset <name>] [--start-demo] [--skip-smoke-test]

Presets:
  gemma3-270m-it      Lightweight default for first local SLM bring-up
  gemma3-4b-fp16      Stronger GPU preset for higher-quality council output
  qwen2.5-0.5b        Small fallback if Gemma access is unavailable

Examples:
  ./scripts/bootstrap_local_slm.sh
  ./scripts/bootstrap_local_slm.sh --preset gemma3-4b-fp16
  MODEL_PRESET=gemma3-4b-fp16 ./scripts/bootstrap_local_slm.sh --start-demo
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preset)
      MODEL_PRESET="${2:-}"
      shift 2
      ;;
    --start-demo)
      START_DEMO=1
      shift
      ;;
    --skip-smoke-test)
      SKIP_SMOKE_TEST=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

case "${MODEL_PRESET}" in
  gemma3-270m-it)
    MODEL_ID="google/gemma-3-270m-it"
    DEVICE="cuda"
    DTYPE="float16"
    DEVICE_MAP="auto"
    MAX_NEW_TOKENS="${LOCAL_HF_MAX_NEW_TOKENS:-256}"
    MAX_INPUT_CHARS="${LOCAL_HF_MAX_INPUT_CHARS:-8000}"
    ;;
  gemma3-4b-fp16)
    MODEL_ID="google/gemma-3-4b-it"
    DEVICE="cuda"
    DTYPE="float16"
    DEVICE_MAP="auto"
    MAX_NEW_TOKENS="${LOCAL_HF_MAX_NEW_TOKENS:-288}"
    MAX_INPUT_CHARS="${LOCAL_HF_MAX_INPUT_CHARS:-10000}"
    ;;
  qwen2.5-0.5b)
    MODEL_ID="Qwen/Qwen2.5-0.5B-Instruct"
    DEVICE="${LOCAL_HF_DEVICE:-auto}"
    DTYPE="${LOCAL_HF_DTYPE:-auto}"
    DEVICE_MAP="${LOCAL_HF_DEVICE_MAP:-none}"
    MAX_NEW_TOKENS="${LOCAL_HF_MAX_NEW_TOKENS:-256}"
    MAX_INPUT_CHARS="${LOCAL_HF_MAX_INPUT_CHARS:-8000}"
    ;;
  *)
    echo "Unsupported preset: ${MODEL_PRESET}" >&2
    usage >&2
    exit 1
    ;;
esac

cat > .runtime.local-hf.env <<EOF
export SLM_BACKEND=local
export LOCAL_SLM_MODE=hf
export EXPERT_EXECUTION_MODE=slm
export LOCAL_HF_MODEL_ID=${MODEL_ID}
export LOCAL_HF_DEVICE=${DEVICE}
export LOCAL_HF_DTYPE=${DTYPE}
export LOCAL_HF_DEVICE_MAP=${DEVICE_MAP}
export LOCAL_HF_MAX_NEW_TOKENS=${MAX_NEW_TOKENS}
export LOCAL_HF_MAX_INPUT_CHARS=${MAX_INPUT_CHARS}
export LOCAL_HF_TEMPERATURE=${LOCAL_HF_TEMPERATURE:-0.0}
export LOCAL_HF_TOP_P=${LOCAL_HF_TOP_P:-1.0}
EOF

set -a
source ./.runtime.local-hf.env
set +a

echo "Installing local HF dependencies..."
"$PYTHON_BIN" -m pip install -e ".[local-hf]"

echo "Preloading model ${LOCAL_HF_MODEL_ID} on ${LOCAL_HF_DEVICE} (${LOCAL_HF_DTYPE})..."
"$PYTHON_BIN" scripts/preload_local_hf_model.py

if [[ "${SKIP_SMOKE_TEST}" != "1" ]]; then
  echo "Running smoke-test in local SLM mode..."
  "$PYTHON_BIN" -c "from app.main import smoke_test; import json; print(json.dumps(smoke_test(), indent=2))"
fi

cat <<EOF

Local SLM runtime prepared.
Preset: ${MODEL_PRESET}
Model:  ${LOCAL_HF_MODEL_ID}
Env:    $(pwd)/.runtime.local-hf.env

To reuse this configuration in a shell:
  source ./.runtime.local-hf.env

To start the API + Streamlit with this model:
  source ./.runtime.local-hf.env && ./scripts/start_demo.sh
EOF

if [[ "${START_DEMO}" == "1" ]]; then
  echo "Starting demo services with ${MODEL_PRESET}..."
  exec ./scripts/start_demo.sh
fi
