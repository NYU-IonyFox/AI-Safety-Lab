# UNICC AI Safety Lab

**Council-of-Experts Repository Safety Evaluation System**  
Built for the UNICC AI Safety Lab Capstone | NYU MASY GC-4100 | Spring 2026

**Team**

- **Andy (Zechao) Wang** — Project 1: Research and Platform Preparation — `zw4295@nyu.edu`
- **Qianying Shao (Fox)** — Project 2: Fine-Tuning the SLM and Building the Council of Experts — `qs2266@nyu.edu`
- **Qianmian Wang** — Project 3: Testing, User Experience, and Integration — `qw2544@nyu.edu`

This repository is designed to be cloned and evaluated as a standalone submission. It accepts a target repository by GitHub URL or local path, analyzes the codebase, runs three distinct expert modules, and returns a structured `APPROVE` / `REVIEW` / `REJECT` council decision with a stakeholder-readable report.

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

- **Repository Intake and Analysis**  
  Accepts a GitHub URL or local path, clones or resolves the repository, then extracts framework, upload, authentication, dependency, and model-integration signals.

- **Council of Experts**  
  Runs three independent expert modules:
  - **Policy & Compliance**: governance controls, accountability, access control, and policy exposure
  - **Adversarial Misuse**: abuse paths, prompt-injection surface, hostile uploads, and misuse likelihood
  - **System & Deployment**: architecture, external-model coupling, deployment exposure, and operational safeguards

- **Stakeholder-Facing UI and Reports**  
  Produces a structured JSON response, a markdown stakeholder report, a JSON archive, and a local Streamlit interface for non-technical review.

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
- prompt and schema assets under `model_assets/`
- optional SLM hooks and local expert-runner interfaces

### Project 3 — Testing, User Experience, and Integration

Implemented in this repository through:

- Streamlit stakeholder UI
- markdown stakeholder report generation
- repository evaluation flow
- smoke-test and health-check routes
- end-to-end integration across intake, experts, council, and artifacts

### How This Submission Interprets the Memo

The capstone memo emphasizes an on-prem, auditable, governance-aligned AI Safety Lab for evaluating AI systems before deployment. This repository operationalizes that goal as a reproducible repository-evaluation workflow:

- **pre-deployment artifact**: the submitted AI repository
- **independent perspectives**: three expert modules with different decision logic
- **explicit critique/synthesis**: council arbitration with a named `decision_rule_triggered`
- **auditability**: repository evidence, markdown reports, JSON archives, and redaction before persistence

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

Use either of the supported input modes:

- `github_url` for a public repository
- `local_path` for a repository already on disk

Leave advanced target-execution fields blank for the default no-key path.

If `/smoke-test` shows `runner_mode: rules_fallback`, the API is still healthy, but the local HF dependencies are not active yet.

---

## Evaluating a Repository

### Option 1 — Submit via GitHub URL

Set a public GitHub repository URL and optional target name:

```bash
GITHUB_URL=https://github.com/owner/repository \
TARGET_NAME="Submitted Repository" \
./scripts/curl_eval.sh
```

### Option 2 — Submit via local path

```bash
SOURCE_TYPE=local_path \
LOCAL_PATH=/absolute/path/to/repository \
TARGET_NAME="Local Repository" \
./scripts/curl_eval.sh
```

### Option 3 — Post a JSON template directly

Edit one of the example payloads first:

```bash
examples/evaluation_request.json
examples/evaluation_request_local.json
```

Then submit it:

```bash
REQUEST_FILE=examples/evaluation_request.json ./scripts/curl_eval.sh
```

### Option 4 — One-command demo launch

```bash
./scripts/start_demo.sh
```

This starts:

- backend: `http://127.0.0.1:8080`
- frontend: `http://127.0.0.1:8501`

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
  "experts": [
    {
      "expert_name": "team3_risk_expert",
      "summary": "Submitted Repository: system-risk review found an externally exposed upload pipeline connected to model processing, so deployment review is required."
    }
  ],
  "council_result": {
    "decision": "REJECT",
    "decision_rule_triggered": "multi_expert_high_risk"
  },
  "report_path": "data/reports/<evaluation-id>.md",
  "archive_path": "data/reports/<evaluation-id>.json"
}
```

---

## What a Strong Evaluation Should Surface

For a repository with public upload routes, model integrations, and weak access controls, the output should reference repository-specific evidence such as:

- Flask route architecture
- file-upload entry points
- GPT-4o usage
- speech or media transcription flow
- lack of an explicit authentication layer
- development secret-key fallback if present

In the current implementation, these are surfaced as:

- `repository_summary.detected_signals`
- `repository_summary.evidence_items`
- expert-specific findings
- `council_result.decision_rule_triggered`

---

## System Architecture

```text
GitHub URL / Local Path Submission
                ↓
        Repository Intake
     (clone / resolve / analyze)
                ↓
    Repository Summary + Evidence
                ↓
┌───────────────────────────────────────┐
│         Council of Experts            │
│                                       │
│  Policy & Compliance                  │
│  Adversarial Misuse                   │
│  System & Deployment                  │
└───────────────────────────────────────┘
                ↓
      Rule-Based Council Synthesis
   (explicit decision_rule_triggered)
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
