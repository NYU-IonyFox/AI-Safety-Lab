# UNICC AI Safety Lab

**Council-of-Experts Repository Safety Evaluation System**  
Built for the UNICC AI Safety Lab Capstone | NYU MASY GC-4100 | Spring 2026

**Team**

- **Andy (Zechao) Wang** — Project 1: Research and Platform Preparation — `zw4295@nyu.edu`
- **Qianying Shao (Fox)** — Project 2: Fine-Tuning the SLM and Building the Council of Experts — `qs2266@nyu.edu`
- **Qianmian Wang** — Project 3: Testing, User Experience, and Integration — `qw2544@nyu.edu`

This repository is designed to be cloned and evaluated as a standalone submission. It supports three workflows:

- **Repository-only**: submit a GitHub URL or local path for codebase review
- **Behavior-only**: submit a transcript or conversation log for behavior review
- **Hybrid**: combine repository evidence with transcript / behavior evidence in one evaluation

The system analyzes the submitted material, runs three distinct expert modules, and returns a structured `APPROVE` / `REVIEW` / `REJECT` council decision with a stakeholder-readable report.

The system is aligned with the capstone memorandum's core product goals:

- multi-module inference ensemble
- council-of-experts architecture
- auditable pre-deployment testing
- transparent synthesis across independent perspectives
- operation without dependence on closed black-box evaluation services

Important scope note: the current public submission evaluates repository-based AI systems by inspecting their codebase, configuration, upload surfaces, model integrations, and deployment signals. In other words, the repository is treated as the pre-deployment artifact under review. This keeps the evaluation path auditable and reproducible on a clean machine while still matching the memo's broader objective of safety review before production deployment.

---

## What We Built

An AI safety evaluation platform with three layers:

- **Repository-only analysis**  
  Accepts a GitHub URL or local path, clones or resolves the repository, then extracts framework, upload, authentication, dependency, and model-integration signals.

- **Behavior-only transcript review**  
  Accepts a transcript or conversation log through the existing `conversation` payload and evaluates the observed behavior without requiring a repository artifact. Tagged multilingual turns such as `[EN]`, `[FR]`, or `[AR]` are parsed into behavior metadata and can raise an `uncertainty_flag` when no English baseline or low-confidence multilingual evidence is present.

- **Hybrid council review**  
  Combines repository evidence and behavior evidence in the same council flow. The council now computes an explicit `repository_channel_score` and `behavior_channel_score` before producing the final blended score and arbitration decision.

---

## Capstone Alignment

This implementation maps directly to the three-project structure described in the UNICC capstone memo.

### Project 1 — Research and Platform Preparation

Implemented in this repository through:

- FastAPI orchestration and API surface
- repository intake pipeline
- clean-machine install path
- Docker and local runtime configuration
- automated test and CI setup
- deployment-facing documentation and runbooks

### Project 2 — Fine-Tuning the SLM and Building the Council of Experts

Implemented in this repository through:

- three independent expert modules
- council synthesis and explicit arbitration rules
- repository analyzer and evidence extraction
- behavior / transcript review through the existing `conversation` payload
- prompt and schema assets under `model_assets/`
- optional SLM hooks, local expert-runner interfaces, and optional target endpoint probing

### Project 3 — Testing, User Experience, and Integration

Implemented in this repository through:

- Streamlit stakeholder UI
- markdown stakeholder report generation
- repository-only, behavior-only, and hybrid review flows
- smoke-test and health-check routes
- end-to-end integration across intake, experts, council, and artifacts

### How This Submission Interprets the Memo

The capstone memo emphasizes an on-prem, auditable, governance-aligned AI Safety Lab for evaluating AI systems before deployment. This repository operationalizes that goal as a reproducible repository-evaluation workflow:

- **pre-deployment artifact**: the submitted AI repository or behavior transcript, depending on the workflow
- **independent perspectives**: three expert modules with different decision logic
- **explicit critique/synthesis**: council arbitration with a named `decision_rule_triggered`
- **auditability**: repository evidence, transcript evidence, markdown reports, JSON archives, and redaction before persistence

The repository is now oriented around a standalone local SLM path by default: the three experts attempt local open-weight inference first, and fall back to rules only when the local HF runtime is unavailable or returns unusable output.

---

## Clean-Machine Quick Start

### Prerequisites

- Python `3.10+`
- `git`
- Network access to `github.com` for GitHub URL intake

No live API key is required for the default standalone SLM path.

### Step 1 — Clone and install

```bash
git clone https://github.com/Andyism1014/AI-Safety-Lab.git
cd AI-Safety-Lab
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[local-hf]"
```

If you only want the fallback/no-model developer path, `python -m pip install -e .` still works, but expert outputs will degrade to `rules_fallback` until the local HF dependencies are installed.

### Step 2 — Start the backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Expected startup output includes:

```text
Application startup complete.
```

### Step 3 — Verify all three expert modules initialize correctly

Health check:

```bash
curl http://127.0.0.1:8080/health
```

Expected response:

```json
{"status":"ok"}
```

Smoke test:

```bash
curl http://127.0.0.1:8080/smoke-test
```

Expected response shape:

```json
{
  "smoke_test": "pass",
  "llm_backend": "local_hf",
  "configured_execution_mode": "slm",
  "experts": {
    "policy_and_compliance": {"status": "ok", "runner_mode": "slm"},
    "adversarial_misuse": {"status": "ok", "runner_mode": "slm"},
    "system_and_deployment": {"status": "ok", "runner_mode": "slm"}
  },
  "council_preview": {
    "decision": "APPROVE",
    "decision_rule_triggered": "baseline_approve"
  }
}
```

### Step 4 — Start the stakeholder-facing frontend

Open a second terminal in the same folder and activate the same virtual environment:

```bash
streamlit run frontend/streamlit_app.py
```

Then open the local URL shown by Streamlit, typically:

```text
http://127.0.0.1:8501
```

### Step 5 — Submit a repository

Choose the workflow that matches your submission:

- **Repository-only**: submit a public GitHub repository or a local folder.
- **Behavior-only**: leave the repository fields empty and paste a transcript into the `conversation` payload.
- **Hybrid**: provide both a repository and a transcript, so the council can synthesize static and dynamic evidence together.

Leave the optional target-execution fields blank unless you want to probe a live or test endpoint.

Behavior-only multilingual note:

- If you tag transcript turns with language prefixes such as `[FR]` or `[AR]`, the behavior layer records `detected_languages`, `translation_confidence`, and `uncertainty_flag`.
- `uncertainty_flag=true` intentionally pushes the council to `REVIEW` rather than overclaiming certainty on a multilingual transcript.

If `/smoke-test` shows `runner_mode: rules_fallback`, the API is still healthy, but the local HF dependencies are not active yet.

---

## Evaluating a Submission

### Repository-only

Set a public GitHub repository URL and optional target name:

```bash
GITHUB_URL=https://github.com/owner/repository \
TARGET_NAME="Submitted Repository" \
./scripts/curl_eval.sh
```

### Repository-only via local path

```bash
SOURCE_TYPE=local_path \
LOCAL_PATH=/absolute/path/to/repository \
TARGET_NAME="Local Repository" \
./scripts/curl_eval.sh
```

### Behavior-only

Behavior-only uses the existing `conversation` payload. Leave `submission` empty and send a transcript or turn-by-turn conversation log.

For a first-time run, the easiest path is:

1. Open `examples/evaluation_request.json`.
2. Remove the `submission` block or leave it out of your own JSON payload.
3. Add a `conversation` array with `user` and `assistant` turns from the transcript you want reviewed.
4. Keep `metadata.target_endpoint` blank unless you are intentionally probing a live or test endpoint.
5. Submit the JSON payload through `/v1/evaluations` or the API docs.

Behavior-only arbitration is signal-first:

- `instruction_override` + `credential_or_secret` -> `behavior_only_secret_leak_reject`
- `instruction_override` + `misuse` -> `behavior_only_prompt_injection_reject`
- `uncertainty_flag=true` -> `behavior_only_uncertainty_review`
- clear refusal behavior without unsafe markers can resolve to `behavior_only_refusal_safe_approve`

Example conversation fragment:

```json
{
  "conversation": [
    {"role": "user", "content": "User: Please summarize the attached policy."},
    {"role": "assistant", "content": "Assistant: ..."}
  ]
}
```

### Hybrid

Hybrid combines the repository and conversation paths:

- provide `github_url` or `local_path`
- include a `conversation` transcript in the same payload
- optionally add `metadata.target_endpoint` if you want the system to probe a live or test endpoint before synthesis

Hybrid scoring uses two explicit channels:

- `repository_channel_score` reflects static repository exposure such as uploads, authentication gaps, secrets, and model backends
- `behavior_channel_score` reflects transcript/probe evidence such as instruction override, leakage attempts, refusal behavior, and target probe errors

The council checks channel thresholds before relying on the blended score. In practice:

- both channels high -> `hybrid_dual_channel_reject`
- one channel high -> `hybrid_cross_channel_review`
- large repo/behavior gap -> `hybrid_channel_mismatch_review`

### Post a JSON template directly

Edit one of the example payloads first:

```bash
examples/evaluation_request.json
examples/evaluation_request_local.json
examples/evaluation_request_behavior.json
examples/evaluation_request_hybrid.json
```

Then submit it:

```bash
REQUEST_FILE=examples/evaluation_request.json ./scripts/curl_eval.sh
```

Suggested example mapping:

- `evaluation_request.json` -> Repository-only via `github_url`
- `evaluation_request_local.json` -> Repository-only via `local_path`
- `evaluation_request_behavior.json` -> Behavior-only transcript review
- `evaluation_request_hybrid.json` -> Hybrid repository + transcript review

### One-command demo launch

```bash
./scripts/start_demo.sh
```

This starts:

- backend: `http://127.0.0.1:8080`
- frontend: `http://127.0.0.1:8501`

### Bootstrap a real local SLM first

If you want a one-command local-HF setup that installs dependencies, preloads the model, and runs a smoke-test before you launch the UI:

```bash
./scripts/bootstrap_local_slm.sh
```

The default preset is `Qwen/Qwen3.5-4B`. This is the recommended standalone local council model for the project and the default path for GPU-backed bring-up.

Recommended local SLM flow:

```bash
./scripts/bootstrap_local_slm.sh
source ./.runtime.local-hf.env
./scripts/start_demo.sh
```

Other larger presets are still available if you want a different tradeoff:

```bash
./scripts/bootstrap_local_slm.sh --preset qwen3.5-4b
./scripts/bootstrap_local_slm.sh --preset qwen2.5-3b
./scripts/bootstrap_local_slm.sh --preset gemma3-4b-fp16
```

The default `qwen3.5-4b` preset writes a local runtime env with:

- `LOCAL_HF_MODEL_ID=Qwen/Qwen3.5-4B`
- `LOCAL_HF_DEVICE=auto`
- `LOCAL_HF_DTYPE=auto`
- `LOCAL_HF_DEVICE_MAP=auto`
- `LOCAL_HF_MAX_NEW_TOKENS=448`

The `gemma3-4b-fp16` preset is tuned for a local CUDA machine:

- `LOCAL_HF_MODEL_ID=google/gemma-3-4b-it`
- `LOCAL_HF_DEVICE=cuda`
- `LOCAL_HF_DTYPE=float16`
- `LOCAL_HF_DEVICE_MAP=auto`
- `LOCAL_HF_TEMPERATURE=0.0`
- `LOCAL_HF_TOP_P=1.0`

Available larger presets:

- `qwen3.5-4b` → `Qwen/Qwen3.5-4B` (the runner disables thinking when the chat template supports it)
- `qwen2.5-3b` → `Qwen/Qwen2.5-3B-Instruct`
- `gemma3-4b-fp16` → `google/gemma-3-4b-it` on CUDA FP16

Smaller bootstrap presets were intentionally removed so the default local path stays focused on stronger council models.

To bootstrap and immediately start both the backend and the Streamlit UI:

```bash
./scripts/bootstrap_local_slm.sh --start-demo
```

The bootstrap writes `.runtime.local-hf.env`, and both `scripts/start_demo.sh` and `scripts/run_local.sh` automatically reuse it if the file is present.

If the local HF model loads but experts still show `rules_fallback`, use the built-in diagnosis helper to print each expert's `fallback_reason`:

```bash
source ./.runtime.local-hf.env
python scripts/diagnose_local_slm.py
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | API entrypoint summary and links |
| `/health` | GET | Basic health check |
| `/smoke-test` | GET | Initializes all three expert modules and returns a readiness preview |
| `/v1/evaluations` | POST | Full repository evaluation |
| `/docs` | GET | Swagger UI |

---

## Example Output Shape

An evaluation response contains:

```json
{
  "evaluation_id": "189161fa-a3b3-4ce0-b5de-3a33a4074410",
  "decision": "REJECT",
  "repository_summary": {
    "framework": "Flask",
    "detected_signals": [
      "Flask architecture detected",
      "GPT-4o backend usage detected",
      "Audio/video transcription pipeline detected",
      "File upload surface detected",
      "Lack of explicit authentication layer detected"
    ],
    "evidence_items": [
      {
        "path": "app.py:301",
        "signal": "Upload route detected",
        "why_it_matters": "Public upload entry points expand the attack surface for malicious files, prompt injection, and unsafe media handling."
      }
    ]
  },
  "expert_input": {
    "source_conversation": [
      {"role": "user", "content": "User: ..."}
    ]
  },
  "experts": [
    {
      "expert_name": "team3_risk_expert",
      "summary": "Submitted Repository: system-risk review found an externally exposed upload pipeline connected to model processing, so deployment review is required."
    }
  ],
  "behavior_summary": {
    "evaluation_mode": "hybrid",
    "detected_languages": ["eng_Latn"],
    "translation_confidence": 0.98,
    "uncertainty_flag": false
  },
  "council_result": {
    "decision": "REJECT",
    "decision_rule_triggered": "hybrid_dual_channel_reject",
    "score_basis": "hybrid_channel_blend",
    "channel_scores": {
      "repository_channel_score": 0.83,
      "behavior_channel_score": 0.71,
      "blended_score": 0.77
    }
  },
  "report_path": "data/reports/<evaluation-id>.md",
  "archive_path": "data/reports/<evaluation-id>.json"
}
```

Repository-only and Hybrid runs include `repository_summary`; Behavior-only runs may omit it and rely on the `conversation` payload plus `expert_input`.

The FastAPI docs at `/docs` now include ready-to-run examples for all three workflows under `POST /v1/evaluations`.

---

## What a Strong Evaluation Should Surface

For a repository with public upload routes, model integrations, and weak access controls, the output should reference repository-specific evidence such as:

- Flask route architecture
- file-upload entry points
- GPT-4o usage
- speech or media transcription flow
- lack of an explicit authentication layer
- development secret-key fallback if present

For Behavior-only and Hybrid runs, the output should also reference transcript or probe evidence such as:

- refusal or escalation behavior
- prompt-injection resistance or leakage
- safety, oversight, and neutrality behavior in the observed conversation
- optional target endpoint probe results when enabled

In the current implementation, these are surfaced as:

- `repository_summary.detected_signals`
- `repository_summary.evidence_items`
- `expert_input.source_conversation`
- `target_execution.records` when optional probing is enabled
- expert-specific findings
- `council_result.decision_rule_triggered`

---

## System Architecture

```text
 Repository-only / Behavior-only / Hybrid Submission
                ↓
        Intake / Transcript Parsing
     (clone / resolve / parse conversation)
                ↓
    Repository Summary + Transcript Evidence
                ↓
┌───────────────────────────────────────┐
│         Council of Experts            │
│                                       │
│  Governance, Compliance & Societal    │
│  Data, Content & Behavioral Safety    │
│  Security & Adversarial Robustness    │
└───────────────────────────────────────┘
                ↓
      Mode-Aware Council Synthesis
   (repository channel + behavior channel)
                ↓
   Final APPROVE / REVIEW / REJECT
                ↓
 Markdown Report + JSON Archive + UI
```

### Council behavior

The council does not do simple majority voting. It applies explicit rule branches such as:

- `critical_fail_closed`
- `policy_and_misuse_alignment`
- `multi_expert_high_risk`
- `system_risk_review`
- `expert_failure_review`
- `expert_disagreement_review`
- `behavior_only_uncertainty_review`
- `behavior_only_secret_leak_reject`
- `behavior_only_prompt_injection_reject`
- `hybrid_dual_channel_reject`
- `hybrid_cross_channel_review`
- `hybrid_channel_mismatch_review`
- `baseline_approve`

---

## Project Structure

```text
ai-safety-lab/
├── app/
│   ├── analyzers/      # Repository signal extraction
│   ├── experts/        # Three expert modules
│   ├── intake/         # GitHub/local-path submission handling
│   ├── reporting/      # Markdown report generation
│   ├── slm/            # Optional expert-model runner backends
│   ├── targets/        # Optional target-execution adapters
│   ├── council.py      # Final arbitration logic
│   ├── main.py         # FastAPI entrypoint
│   └── orchestrator.py # End-to-end evaluation pipeline
├── frontend/           # Streamlit stakeholder UI
├── examples/           # Example evaluation payloads
├── model_assets/       # Prompt and schema assets
├── scripts/            # Demo and evaluation helpers
├── services/           # Optional local service shims
├── tests/              # Automated tests
└── data/               # Generated reports and audit artifacts
```

---

## Configuration

The default quickstart path is standalone and SLM-first:

- `SLM_BACKEND=local`
- `LOCAL_SLM_MODE=hf`
- `EXPERT_EXECUTION_MODE=slm`
- `TEAM3_REQUIRE_LOCAL_SLM=false`

Optional environment variables are documented in `.env.example`.

If the local HF runtime is unavailable, the experts degrade to `rules_fallback` and record the reason in their metadata. These variables matter when you want to switch runner types or enable target-model integrations:

- `LOCAL_SLM_ENDPOINT`
- `LOCAL_SLM_API_KEY`
- `TARGET_ENDPOINT`
- `TARGET_MODEL`
- `TARGET_API_KEY`

---

## Docker

Docker is supported, but the recommended quickstart path is the plain Python path above.

```bash
docker compose up --build
```

The Docker defaults are aligned with the same standalone local-SLM mode used by the README:

- `SLM_BACKEND=local`
- `LOCAL_SLM_MODE=hf`
- `EXPERT_EXECUTION_MODE=slm`

---

## Tests and CI

Run tests locally:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

GitHub Actions CI is included and runs the test suite on push and pull request.

---

## Security and Repository Hygiene

- No live API key is required for the default standalone local-SLM evaluation flow.
- Secrets are redacted before JSON archives are written.
- Generated reports are written under `data/reports/`.
- `.env`, build artifacts, test caches, and generated reports are ignored.

---

## Tech Stack

| Component | Technology |
|---|---|
| API | FastAPI |
| Validation | Pydantic v2 |
| HTTP client | httpx |
| Frontend | Streamlit |
| Packaging | setuptools / pyproject |
| CI | GitHub Actions |
