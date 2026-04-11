# Unified Implementation Plan (proj-1 + proj-2 + proj-3)

## Goal
Build **one integrated AI Safety Lab product** for evaluation.

- `proj-1` becomes the **backend and infrastructure base**.
- `proj-2` becomes the **fine-tuning / evaluation assets layer**, not a separate app.
- `proj-3` becomes the **frontend and user-facing submission/reporting layer**.

The final deliverable should let an evaluator:
1. start the system from the README,
2. submit a real target project such as **VeriMedia**,
3. run three distinct expert evaluations,
4. receive a clear final verdict with synthesis,
5. understand the results without reading raw JSON.

---

## Product Direction

### Final product statement
This repository should no longer present three parallel prototypes as equal deliverables.
It should present **one product** composed of three integrated parts:

- **Backend**: proj-1
- **Model / evaluation assets**: proj-2
- **Frontend**: proj-3

### Non-goals
- Do not maintain three separate apps for grading.
- Do not require graders to manually edit config files to test VeriMedia.
- Do not rely on live API keys for the default demo path.
- Do not expose raw internal JSON as the primary user output.

---

## Current State Summary

### proj-1 currently provides
- FastAPI API skeleton
- orchestrator
- three expert modules
- council decision layer
- audit persistence
- mock/local SLM abstraction

### proj-2 currently provides
- separate council/evaluation logic and possibly fine-tuning assets
- useful scoring ideas, prompts, rubrics, labels, and evaluation structure
- a standalone app shape that should **not** remain a separate product path

### proj-3 currently provides
- a frontend prototype / Streamlit experience
- UI patterns that can become the final evaluator-facing interface
- demo-oriented presentation that still needs backend integration

---

## Target Architecture

```text
integrated-ai-safety-lab/
├── backend/                      # derived from proj-1
│   ├── app/
│   │   ├── main.py
│   │   ├── orchestrator.py
│   │   ├── council.py
│   │   ├── schemas.py
│   │   ├── config.py
│   │   ├── audit.py
│   │   ├── intake/              # new
│   │   ├── analyzers/           # new
│   │   ├── experts/
│   │   ├── reporting/           # new
│   │   ├── slm/
│   │   └── targets/
│   ├── tests/
│   └── data/
├── frontend/                     # derived from proj-3
│   ├── streamlit_app.py or app/
│   ├── components/
│   └── api_client/
├── model_assets/                 # extracted from proj-2
│   ├── prompts/
│   ├── scoring_rules/
│   ├── fine_tune_assets/
│   ├── eval_templates/
│   └── benchmark_cases/
├── examples/
│   └── verimedia/
├── scripts/
└── README.md
```

If directory renaming is too expensive right now, keep the physical directories temporarily but implement the same logical ownership:

- `proj-1` = backend
- `proj-3` = frontend
- `proj-2` = assets source

---

## Ownership by Project

## 1. proj-1 -> Backend / Infrastructure

### Keep from proj-1
- `app/main.py`
- `app/orchestrator.py`
- `app/council.py`
- `app/schemas.py`
- `app/config.py`
- `app/audit.py`
- `app/experts/*`
- `app/slm/*`
- `app/targets/*`
- tests and report persistence

### proj-1 responsibilities after integration
- provide stable API endpoints
- accept target project submissions
- convert repo/project input into internal evaluation context
- run three expert evaluations
- run council critique/synthesis
- persist results
- serve frontend-ready structured responses
- generate human-readable reports

### New modules to add in proj-1

#### `app/intake/`
Purpose: normalize real-world inputs into internal requests.

Planned files:
- `github_loader.py`
- `local_repo_loader.py`
- `request_builder.py`
- `submission_service.py`

Responsibilities:
- accept GitHub URL or local project path
- clone/read target project
- collect basic metadata
- create internal request object for evaluation

#### `app/analyzers/`
Purpose: extract repo-specific signals for expert analysis.

Planned files:
- `repo_summary.py`
- `framework_detector.py`
- `dependency_analyzer.py`
- `security_surface_extractor.py`
- `llm_usage_detector.py`
- `auth_detector.py`
- `media_pipeline_detector.py`

Responsibilities:
- detect Flask / FastAPI / other frameworks
- detect routes and upload surfaces
- detect auth/session patterns
- detect OpenAI / Claude / Whisper / external AI usage
- detect file parsing and media handling chains
- detect secret/config handling issues
- produce a structured project summary for experts

#### `app/reporting/`
Purpose: produce outputs readable by graders and stakeholders.

Planned files:
- `report_builder.py`
- `markdown_report.py`
- `html_report.py`
- `frontend_view_model.py`

Responsibilities:
- transform expert outputs into concise summaries
- generate final report sections
- support downloadable markdown/html report
- shape API output for frontend cards/tables

---

## 2. proj-2 -> Fine-Tuning / Evaluation Assets Layer

### Important principle
`proj-2` should **not** survive as a separate app in the final submission path.
Its value is in the assets and logic it contributes.

### What to extract from proj-2

#### Prompts and evaluation templates
Move reusable expert prompts and council templates into:
- `model_assets/prompts/`
- `model_assets/eval_templates/`

#### Scoring rules / taxonomy
Move reusable:
- risk dimensions
- severity levels
- score mapping
- critique templates
- decision criteria

into:
- `model_assets/scoring_rules/`

#### Fine-tuning assets
Move reusable:
- labeled examples
- prompt/completion pairs
- classifier labels
- benchmark I/O cases
- validation sets

into:
- `model_assets/fine_tune_assets/`
- `model_assets/benchmark_cases/`

### How proj-2 should be used at runtime

#### Default runtime path
- system runs without requiring fine-tuning
- backend uses rules, templates, and optional SLM/API inference
- graders can run the product in a clean environment

#### Enhanced path
- proj-2 assets can improve expert prompts, scoring, and optional fine-tuned models
- these should be optional, not required for the base demo

### What not to do with proj-2
- do not require the grader to run proj-2 separately
- do not keep separate endpoints/UI for proj-2 in the final demo flow
- do not make core correctness depend on a fine-tuned checkpoint that may be unavailable

---

## 3. proj-3 -> Frontend / Submission + Reporting Experience

### Keep from proj-3
- layout patterns
- card-based display of findings
- summary/trace visualization concepts
- Streamlit or web app scaffolding

### proj-3 responsibilities after integration
- provide the grader-facing interface
- allow target submission
- display extracted target summary
- display distinct expert outputs
- display final verdict and synthesis
- support report download

### Required frontend views

#### Submission page
Inputs:
- GitHub repo URL
- local target path
- optional target description
- optional runtime mode

Action:
- submit evaluation request to backend

#### Target overview page
Show:
- target name
- framework
- languages
- detected routes
- detected model/API integrations
- upload/media surfaces
- auth posture

#### Expert results page
Show three clearly separated expert cards:
- Team1 Governance / Policy
- Team2 Red-Team / Attack Surface
- Team3 Architecture / Deployment Risk

Each card should include:
- verdict / risk tier
- key findings
- evidence basis
- must-fix items

#### Council page
Show:
- final verdict: `APPROVE`, `REVIEW`, or `REJECT`
- consensus findings
- disagreements
- synthesis rationale
- must-fix before deployment
- recommended next actions

#### Report page/download
Support:
- readable markdown/html report
- optional PDF export if time permits

### What proj-3 must stop doing
- relying on static scenario-only demo flows
- presenting fabricated results as the primary experience
- acting like a disconnected prototype

---

## End-to-End Flow

### Intended evaluator flow
1. evaluator opens frontend
2. evaluator submits VeriMedia by GitHub URL or local path
3. backend intake loads repo metadata
4. analyzers extract project features
5. orchestrator builds expert input package
6. Team1, Team2, Team3 run independently
7. council performs critique + synthesis
8. backend stores audit artifacts and final report
9. frontend displays structured results

### Internal data flow

```text
submission
  -> intake layer
  -> repo analyzers
  -> normalized target project context
  -> expert input packages
  -> three expert verdicts
  -> council synthesis
  -> persisted report + frontend view model
```

---

## VeriMedia-Specific Requirements

The integrated product must be able to accept VeriMedia as a real target and produce findings specific to that codebase.

### Minimum extracted facts for VeriMedia
The system should detect and surface at least:
- Flask application structure
- file upload route / upload handling
- text/audio/video processing workflow
- OpenAI / GPT-4o / Whisper usage
- session and secret key handling
- lack of obvious authentication layer
- media conversion dependency chain (e.g. ffmpeg/moviepy/pydub)
- large file handling / operational constraints

### Expert-specific expectations for VeriMedia

#### Team1 should emphasize
- privacy and governance implications of uploaded media
- third-party AI data handling concerns
- policy/compliance gaps
- transparency and oversight gaps

#### Team2 should emphasize
- upload abuse surface
- malicious media input risks
- prompt and model misuse risk
- unprotected access patterns
- attack scenarios around external API-backed processing

#### Team3 should emphasize
- Flask architecture and deployment readiness
- configuration posture and default secret handling
- operational dependency risk
- resource pressure from media processing
- system readiness for production review

### Final synthesis expectations
The council output should explicitly mention repository-specific signals rather than generic AI safety boilerplate.

---

## Detailed Implementation Phases

## Phase 0 - Align the repository around one product

### Objective
Define one integrated product path and stop treating the three project folders as separate end-user deliverables.

### Tasks
- designate proj-1 as backend base
- designate proj-3 as frontend base
- designate proj-2 as source of prompts/rubrics/fine-tune assets
- update top-level README language accordingly
- remove ambiguity in docs about what graders should run

### Deliverables
- updated architecture statement
- updated integration plan
- updated top-level README direction

---

## Phase 1 - Make proj-1 the real backend

### Objective
Upgrade proj-1 from evaluation skeleton to full project-ingestion backend.

### Tasks

#### 1. Extend schemas
Add project-aware schema types, such as:
- `TargetProjectContext`
- `RepoRouteSummary`
- `LLMIntegrationSummary`
- `SecuritySurfaceSummary`
- `DeploymentReadinessSummary`

Update `EvaluationRequest` so it can carry:
- repo path or repo URL
- analyzed project summary
- target metadata derived from code

#### 2. Add intake endpoints
Recommended endpoints:
- `POST /v1/intake/evaluate`
- `POST /v1/evaluations/from-repo`
- `GET /v1/evaluations/{id}`
- `GET /v1/evaluations/{id}/report`

#### 3. Add repo analyzers
Implement static repo inspection sufficient for VeriMedia.

#### 4. Update orchestrator
Change orchestrator so expert input comes from analyzed project context, not only transcript/conversation.

#### 5. Update audit/report persistence
Persist both:
- raw structured expert/council result
- human-readable report artifacts

### Deliverables
- running backend that accepts repo input
- project-aware evaluation request pipeline
- persisted structured and readable outputs

---

## Phase 2 - Convert proj-2 into reusable assets

### Objective
Extract the useful intelligence from proj-2 without keeping it as a separate runtime dependency.

### Tasks

#### 1. Inventory proj-2
Create a mapping of:
- prompts worth reusing
- score rubrics worth reusing
- benchmark or label assets worth reusing
- logic worth porting into experts or council

#### 2. Create `model_assets/`
Organize extracted content into stable directories.

#### 3. Wire selected assets into backend experts
Examples:
- Team1 prompt templates
- Team2 attack/evaluation rubrics
- Team3 risk tier templates
- council critique templates

#### 4. Preserve optional fine-tuning path
If proj-2 includes true fine-tuning assets, document them as an optional enhancement path.

### Deliverables
- extracted asset library
- expert prompts/rules informed by proj-2
- optional fine-tuning documentation without runtime hard dependency

---

## Phase 3 - Rebuild expert modules around project analysis

### Objective
Ensure the three modules are truly distinct in logic, evidence, and output.

### Team1: Governance / Policy / Compliance
Focus:
- privacy
- governance controls
- auditability
- transparency
- human oversight
- external model/data handling

Expected inputs:
- data flow summary
- auth/session findings
- external API usage
- project configuration signals

Expected outputs:
- governance posture
- compliance concerns
- required controls
- policy-linked findings

### Team2: Red-Team / Attack Surface
Focus:
- abuse cases
- unsafe input handling
- adversarial risk
- upload and parsing attack surface
- endpoint misuse scenarios

Expected inputs:
- routes
- upload surfaces
- prompt/model call sites
- media pipeline
- external request surfaces

Expected outputs:
- attack scenarios
- exploitability assessment
- severity
- remediation priorities

### Team3: Architecture / Deployment / Operational Risk
Focus:
- system design
- deployment readiness
- dependency and config posture
- operational resilience
- resource bottlenecks

Expected inputs:
- stack/framework summary
- dependencies
- config and env handling
- file processing assumptions
- runtime constraints

Expected outputs:
- architecture findings
- deployment concerns
- readiness verdict
- production blockers

### Deliverables
- three clearly differentiated expert modules
- target-specific findings from each expert
- non-overlapping output structure across experts

---

## Phase 4 - Upgrade council into critique + synthesis

### Objective
Meet the rubric expectation that the final layer does more than threshold aggregation.

### Required changes
- standardize final decisions to:
  - `APPROVE`
  - `REVIEW`
  - `REJECT`
- add explicit consensus analysis
- add explicit disagreement analysis
- add final synthesis rationale
- add must-fix actions before deployment

### Recommended council output structure
- `final_verdict`
- `overall_risk_level`
- `consensus_findings`
- `cross_expert_disagreements`
- `synthesis_rationale`
- `must_fix_before_deployment`
- `recommended_next_steps`

### Deliverables
- clearer council response schema
- critique-aware synthesis layer
- final verdict aligned with grader language

---

## Phase 5 - Turn proj-3 into the real frontend

### Objective
Provide a usable evaluation interface for non-authors.

### Tasks
- replace static/dummy scenarios with backend API integration
- build submission form for repo URL/local path
- build target overview section
- build three expert result cards
- build final synthesis view
- add report download button

### UX requirements
- a user should understand where to submit VeriMedia
- a user should be able to tell the three experts apart instantly
- the final verdict should be visible without opening raw JSON
- the findings should read like a report, not a dump

### Deliverables
- connected frontend
- backend-driven result rendering
- clear reviewer workflow

---

## Phase 6 - README, demo path, and clean-run validation

### Objective
Optimize for grading flow.

### Tasks
- rewrite README for first-time users
- remove machine-specific absolute paths
- document clean install path
- document no-key default mode
- document configurable backend mode
- document VeriMedia demo submission flow
- add helper scripts:
  - `run_backend.sh`
  - `run_frontend.sh`
  - `run_verimedia_demo.sh`

### Validation checklist
- fresh environment install works
- backend starts
- frontend starts
- VeriMedia can be submitted
- three expert outputs render
- final report renders
- no secret committed in repo

### Deliverables
- grader-friendly README
- one-command or few-command demo path
- validated end-to-end run

---

## API and Data Model Changes

## New/updated backend request shape
Minimum submission options should support:

```json
{
  "github_url": "https://github.com/.../VeriMedia",
  "submission_label": "VeriMedia"
}
```

and

```json
{
  "local_path": "/path/to/target",
  "submission_label": "VeriMedia"
}
```

### Internal normalized evaluation object should include
- project identity
- source type
- framework and language summary
- route summary
- upload/media summary
- auth/config summary
- external model integration summary
- extracted findings inventory
- expert-ready evidence blocks

---

## File-Level Change Plan

## proj-1 files to modify first
- `proj-1/app/main.py`
- `proj-1/app/orchestrator.py`
- `proj-1/app/council.py`
- `proj-1/app/schemas.py`
- `proj-1/app/audit.py`
- `proj-1/app/config.py`
- `proj-1/app/experts/team1_policy_expert.py`
- `proj-1/app/experts/team2_redteam_expert.py`
- `proj-1/app/experts/team3_risk_expert.py`
- `proj-1/README.md`

## proj-1 files/directories to add
- `proj-1/app/intake/`
- `proj-1/app/analyzers/`
- `proj-1/app/reporting/`
- `proj-1/tests/test_intake_*`
- `proj-1/tests/test_verimedia_*`

## proj-2 outputs to extract
- prompts
- rubrics
- labels
- evaluation cases
- useful expert/council logic patterns

## proj-3 files to modify
- frontend entry file
- API integration layer
- result rendering components
- submission form components
- report display components

---

## Priority Order

## P0 - Must do
1. one-product positioning
2. proj-1 as backend base
3. proj-3 as frontend base
4. proj-2 converted into assets source
5. README cleanup
6. no-key default run path

## P1 - High priority
7. repo intake
8. VeriMedia static feature extraction
9. project-aware expert inputs
10. critique-aware council synthesis
11. clear frontend rendering

## P2 - Nice to have
12. downloadable HTML/PDF report
13. richer benchmark library from proj-2
14. optional fine-tuned expert support
15. stronger UI polish

---

## Definition of Done

The integration is successful when all of the following are true:

- there is one clearly documented product path
- grader can install and start the system from README
- grader can submit VeriMedia without manual code edits
- backend accepts real project input
- three experts produce distinct, target-specific outputs
- council returns `APPROVE`, `REVIEW`, or `REJECT`
- final output contains synthesis, not only aggregation
- frontend presents understandable results
- reports are readable by non-authors
- default run path works without live API secrets

---

## Immediate Next Actions

1. Update `proj-1/app/schemas.py` for project-based input.
2. Add `proj-1/app/intake/` and `proj-1/app/analyzers/`.
3. Change `proj-1/app/orchestrator.py` to use analyzed project context.
4. Rewrite the three experts around repo-derived evidence.
5. Upgrade `proj-1/app/council.py` to critique + synthesis.
6. Connect proj-3 frontend to backend endpoints.
7. Rewrite `proj-1/README.md` for the evaluator flow.
8. Add a VeriMedia end-to-end demo path.
