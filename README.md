# AI Safety Lab

Integrated UNICC submission for repository-based AI safety evaluation.

This repository is intended to be submitted and cloned as a standalone project. It accepts a repository by GitHub URL or local path, analyzes the codebase, runs three distinct expert modules, and returns an explicit `APPROVE` / `REVIEW` / `REJECT` council verdict with a readable report.

## What the evaluator should be able to do

1. Clone this repository on a clean machine.
2. Install it with standard Python tooling.
3. Launch the backend and frontend without adding API keys.
4. Submit VeriMedia dynamically from GitHub.
5. Review three independent expert outputs plus an explicit arbitration rule.

## Default grading path

The default path is intentionally safe for offline or no-key evaluation:

- `EXPERT_EXECUTION_MODE=rules`
- no target model endpoint required
- no Anthropic/OpenAI key required
- GitHub URL intake enabled out of the box

## Prerequisites

- Python `3.10+`
- `git`
- network access to `github.com` for GitHub URL intake

## Quickstart

```bash
git clone <YOUR_REPOSITORY_URL>
cd ai-safety-lab
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Start the backend

```bash
uvicorn app.main:app --port 8080
```

Health check:

```bash
curl http://127.0.0.1:8080/health
```

Expected response:

```json
{"status":"ok"}
```

## Start the frontend

Open a second terminal in the same folder, activate the same virtual environment, then run:

```bash
streamlit run frontend/streamlit_app.py
```

The UI defaults to GitHub URL intake for VeriMedia.

## Quickest end-to-end demo

If you want one command to start both backend and frontend:

```bash
./scripts/start_demo.sh
```

This prints:

- backend: `http://127.0.0.1:8080/health`
- frontend: `http://127.0.0.1:8501`

## Submit VeriMedia

### Option A: through the frontend

Use the default form values:

- `Source type`: `github_url`
- `GitHub URL`: `https://github.com/FlashCarrot/VeriMedia`
- `Target name`: `VeriMedia`

Leave the advanced target endpoint fields blank for the no-key grading path.

### Option B: through the API

The included example payload already points to VeriMedia on GitHub:

```bash
curl -sS -X POST "http://127.0.0.1:8080/v1/evaluations" \
  -H "Content-Type: application/json" \
  --data-binary @examples/evaluation_request.json
```

Equivalent helper script:

```bash
./scripts/curl_eval.sh
```

## Local-path intake

If you already have VeriMedia or another target repo on disk, use `examples/evaluation_request_local.json` or switch the Streamlit form to `local_path`.

Example:

```bash
curl -sS -X POST "http://127.0.0.1:8080/v1/evaluations" \
  -H "Content-Type: application/json" \
  --data-binary @examples/evaluation_request_local.json
```

## What the output contains

Each evaluation returns:

- `repository_summary`
- `experts[]`
- `council_result`
- `decision`
- `report_path`
- `archive_path`

### Three expert modules

1. `Policy & Compliance`
   reviews governance controls, accountability, and policy exposure.
2. `Adversarial Misuse`
   reviews abuse paths, misuse likelihood, and attack surface.
3. `System & Deployment`
   reviews architecture, deployment exposure, and operational safeguards.

### Council synthesis

The council does not do simple majority voting. It applies explicit arbitration rules such as:

- critical fail-closed rejection
- multi-expert high-risk rejection
- expert-failure review
- disagreement review
- system-risk review

The returned `council_result` includes `decision_rule_triggered` so the evaluator can see exactly why the verdict was reached.

## What a strong VeriMedia evaluation should surface

When evaluating VeriMedia, the report should reference repository evidence such as:

- Flask architecture and route handling
- file-upload entry points
- GPT-4o or other external model usage
- speech or media transcription flow
- lack of a visible authentication layer
- development secret-key fallback if present

These signals are derived from the submitted repository at runtime rather than a hardcoded demo path.

## Tests

Install dev dependencies if you want to run the test suite:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Docker

Docker assets are kept for development, but the recommended grading path is the plain Python quickstart above. The Python path is the simplest and most reliable path for clean-machine evaluation.

## Security and repository hygiene

- no live API key is required for the default grading flow
- secrets are redacted before the JSON archive is written
- generated reports are written under `data/reports/`
- `.env` is ignored and not required for the default run
