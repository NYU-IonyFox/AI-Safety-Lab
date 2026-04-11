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

- **Grader-Facing UI and Reports**  
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
- VeriMedia evaluation flow
- smoke-test and health-check routes
- end-to-end integration across intake, experts, council, and artifacts

### How This Submission Interprets the Memo

The capstone memo emphasizes an on-prem, auditable, governance-aligned AI Safety Lab for evaluating AI systems before deployment. This repository operationalizes that goal as a reproducible repository-evaluation workflow:

- **pre-deployment artifact**: the submitted AI repository
- **independent perspectives**: three expert modules with different decision logic
- **explicit critique/synthesis**: council arbitration with a named `decision_rule_triggered`
- **auditability**: repository evidence, markdown reports, JSON archives, and redaction before persistence

The repository also includes optional hooks for more advanced expert-model backends, but the default grading path intentionally runs in a deterministic rules/mock mode so evaluators can install and test it without extra credentials or cluster access.

---

## Clean-Machine Quick Start

### Prerequisites

- Python `3.10+`
- `git`
- Network access to `github.com` for GitHub URL intake

No live API key is required for the default grading path.

### Step 1 — Clone and install

```bash
git clone <YOUR_REPOSITORY_URL>
cd ai-safety-lab
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

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
  "llm_backend": "rules",
  "experts": {
    "policy_and_compliance": {"status": "ok"},
    "adversarial_misuse": {"status": "ok"},
    "system_and_deployment": {"status": "ok"}
  },
  "council_preview": {
    "decision": "APPROVE",
    "decision_rule_triggered": "baseline_approve"
  }
}
```

### Step 4 — Start the grader-facing frontend

Open a second terminal in the same folder and activate the same virtual environment:

```bash
streamlit run frontend/streamlit_app.py
```

Then open the local URL shown by Streamlit, typically:

```text
http://127.0.0.1:8501
```

### Step 5 — Submit VeriMedia

The frontend defaults to the standard test case:

- `Source type`: `github_url`
- `GitHub URL`: `https://github.com/FlashCarrot/VeriMedia`
- `Target name`: `VeriMedia`

Leave advanced target-execution fields blank for the default no-key grading path.

---

## Evaluating VeriMedia

### Option 1 — Submit via GitHub URL

```bash
curl -sS -X POST "http://127.0.0.1:8080/v1/evaluations" \
  -H "Content-Type: application/json" \
  --data-binary @examples/evaluation_request.json
```

### Option 2 — Submit via local path

```bash
curl -sS -X POST "http://127.0.0.1:8080/v1/evaluations" \
  -H "Content-Type: application/json" \
  --data-binary @examples/evaluation_request_local.json
```

### Option 3 — Use the helper script

```bash
./scripts/curl_eval.sh
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
      "summary": "VeriMedia: system-risk review found an unauthenticated upload pipeline connected to external AI services, so deployment review is required."
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

## What a Strong VeriMedia Evaluation Should Surface

When evaluating `https://github.com/FlashCarrot/VeriMedia`, the output should reference repository-specific evidence such as:

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
├── frontend/           # Streamlit grader-facing UI
├── examples/           # Example evaluation payloads
├── model_assets/       # Prompt and schema assets
├── scripts/            # Demo and evaluation helpers
├── services/           # Optional local service shims
├── tests/              # Automated tests
└── data/               # Generated reports and audit artifacts
```

---

## Configuration

The default grading path is intentionally safe:

- `SLM_BACKEND=mock`
- `EXPERT_EXECUTION_MODE=rules`
- `TEAM3_REQUIRE_LOCAL_SLM=false`

Optional environment variables are documented in `.env.example`.

These are only needed if you want to enable optional expert-model or target-model integrations:

- `LOCAL_SLM_ENDPOINT`
- `LOCAL_SLM_API_KEY`
- `TARGET_ENDPOINT`
- `TARGET_MODEL`
- `TARGET_API_KEY`

---

## Docker

Docker is supported, but the recommended evaluator path is the plain Python quick start above.

```bash
docker compose up --build
```

The Docker defaults are aligned with the same no-key grading mode used by the README:

- `SLM_BACKEND=mock`
- `EXPERT_EXECUTION_MODE=rules`

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

- No live API key is required for the default grading flow.
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
