# Benchmark Validation Guide

This guide is for people who want to **evaluate, tune, or compare** `AI-Safety-Lab` using the built-in benchmark harness. It explains:

- what the benchmark harness is for
- which files and scripts to use
- how to compare a new configuration against a baseline
- how to interpret repeated-run metrics, intervals, and worst-case slices
- which design choices still need empirical calibration

This document is intentionally written for operators and contributors, not as a research memo.

## What This Guide Is For

Use the benchmark harness when you need to answer questions like:

- Did a threshold change actually improve decisions?
- Is `hybrid` better than `repository_only` or `behavior_only` on the cases we care about?
- Is a new model or prompt more stable across repeated runs?
- Did multilingual handling become more conservative or just noisier?
- Did a new routing rule improve long-tail safety, or only average score?

The goal is not to celebrate one high score. The goal is to make a **defensible comparison** between configurations.

## What Ships in the Repository

Main files:

- benchmark manifests: `model_assets/benchmark_cases/`
- single-run CLI: `scripts/run_benchmark_pack.py`
- repeated-run CLI: `scripts/run_benchmark_pack_repeated.py`
- metrics and interval calculation: `model_assets/benchmark_cases/metrics.py`
- worst-case and long-tail summaries: `model_assets/benchmark_cases/reporting.py`
- markdown renderer for repeated-run JSON: `scripts/render_benchmark_summary.py`

Default benchmark packs:

- `public_repo_benchmark_pack.json`
  Repository-only public repo pack
- `validation_benchmark_pack.json`
  Mixed pack covering `repository_only`, `behavior_only`, and `hybrid`

## Quick Start

Inspect a pack:

```bash
python scripts/run_benchmark_pack.py \
  --pack model_assets/benchmark_cases/validation_benchmark_pack.json \
  --mode inspect
```

Run one benchmark case:

```bash
python scripts/run_benchmark_pack.py \
  --pack model_assets/benchmark_cases/validation_benchmark_pack.json \
  --mode evaluate \
  --case-id hybrid-discordant-repo-risk
```

Run repeated evaluation and save JSON:

```bash
python scripts/run_benchmark_pack_repeated.py \
  --pack model_assets/benchmark_cases/validation_benchmark_pack.json \
  --repeats 10 \
  --baseline-id current \
  --interval-method bootstrap \
  --json > validation_report.json
```

Render a markdown summary:

```bash
python scripts/render_benchmark_summary.py \
  --input validation_report.json \
  --output validation_report.md \
  --title "Validation Harness Summary"
```

## How To Read the Benchmark Packs

Each case can represent one of three modes:

- `repository_only`
- `behavior_only`
- `hybrid`

Useful fields:

- `expected_decision`
  The current gold label for the case
- `baseline_metadata`
  The comparison target or prior expectation
- `slice_labels`
  The risk slices the case belongs to, for example upload risk, multilingual uncertainty, or hybrid disagreement
- `transcript`
  The behavior evidence for `behavior_only` and `hybrid`

Treat the manifest as a labeled test set, not as a demo pack.

## How To Compare Against a Baseline

Do not judge a configuration in isolation. Always compare it to at least one baseline such as:

- a previous tagged release
- the current `main` configuration
- `repository_only` without behavior fusion
- `behavior_only` without repository fusion
- a simpler council configuration

The baseline question should always be explicit:

- better than what?
- on which slices?
- by how much?
- with what tradeoff?

If there is no baseline, a single benchmark score is easy to over-interpret.

## Why Repeated Runs Matter

Model-based systems have variance. One run can be unusually high or unusually low.

Recommended protocol:

- use at least `5` repeats for smoke-level checks
- use `10` to `30` repeats for final tuning work
- keep labels frozen during repeated runs
- store every run, not only the mean

The repeated-run harness records:

- `run_id`
- `seed`
- `baseline_id`
- raw results for each case

This lets you measure both performance and stability.

## What Metrics Matter Most

The harness reports these core metrics:

- `accuracy`
- `false_approve_rate`
- `false_reject_rate`
- `review_rate`
- `coverage_rate`
- `error_rate`

For safety-sensitive tuning, the most important numbers are usually:

- unsafe false approves
- review inflation
- instability across repeated runs
- worst-case slices

Do not optimize only for average accuracy.

## Use Intervals, Not Single Scores

Single scores are too brittle for tuning decisions.

Prefer:

- mean plus confidence interval
- or mean plus percentile band

Accept a new setting only when its interval is clearly better than the baseline on the metric that matters.

Examples:

- if a candidate improves average accuracy but its unsafe false-approve interval overlaps the baseline, the gain is weak
- if a threshold lowers average risk but creates unstable `REVIEW` spikes, it is not yet validated

This matters most for:

- `repository_channel_score` and `behavior_channel_score`
- hybrid reject/review thresholds
- multilingual uncertainty thresholds

## Long-Tail and Worst-Case Analysis

Average performance is necessary, but it is not enough for safety work.

Always inspect:

- worst-case slices
- critical failures
- most unstable cases
- rare multilingual misses
- rare false approves on high-risk cases

The worst-case report is there to answer:

- Where does the system fail badly?
- Which slices are fragile?
- Which cases flip across runs?

If the average looks good but the worst-case report is ugly, the configuration is not ready.

## Suggested Benchmark Mix

### Suite A — Repository Channel Cases

Purpose:
- test static implementation and deployment risk detection

Case types:
- unsafe upload / no-auth / secret handling failures
- safe repository with strong controls
- repository with risky model integrations but strong containment
- repository with misleading README or config claims

Recommended labels:
- `APPROVE`, `REVIEW`, `REJECT`
- primary failure mode
- evidence sufficiency score

### Suite B — Behavior Channel Cases

Purpose:
- test runtime misuse, refusal, leakage, and multilingual handling

Case types:
- clear refusal and escalation behavior
- instruction override with benign outcome
- instruction override with harmful or secret-seeking outcome
- multilingual safe behavior
- multilingual ambiguous behavior
- low-confidence translation or language-mismatch cases

Recommended labels:
- `APPROVE`, `REVIEW`, `REJECT`
- uncertainty required: yes/no
- key behavior failure mode

### Suite C — Hybrid Conflict Cases

Purpose:
- test cross-channel disagreement and arbitration

Case types:
- risky repo + safe runtime behavior
- safe repo + unsafe runtime behavior
- risky repo + risky runtime behavior
- safe repo + safe runtime behavior
- multilingual ambiguous behavior layered on top of either safe or unsafe repositories

Recommended labels:
- expected final decision
- expected decision rationale
- expected dominant channel

Recommended starting size:

- 12 to 18 `repository_only` cases
- 12 to 18 `behavior_only` cases
- 12 to 18 `hybrid` cases
- at least one-third of the behavior and hybrid cases should include multilingual or code-switched evidence

## What Still Needs Calibration

These are the main project-specific choices that should be validated with the harness instead of assumed correct:

- `repository_channel_score` vs `behavior_channel_score` weights
- `hybrid_dual_channel_reject` and review thresholds
- multilingual `uncertainty_flag` triggers
- expert taxonomy mapping
- deliberation evidence-routing strategy

The next sections explain how to evaluate each of those choices.

## Calibration Experiments

### Experiment 1 — Channel Weight Calibration

Use this when:

- you changed the weighting logic
- `hybrid` looks too repo-heavy or too behavior-heavy
- disagreement cases are resolving poorly

Method:

1. Freeze the benchmark labels.
2. Sweep weight pairs across a grid such as:
   - `(0.8, 0.2)`
   - `(0.7, 0.3)`
   - `(0.6, 0.4)`
   - `(0.5, 0.5)`
   - `(0.4, 0.6)`
   - `(0.3, 0.7)`
   - `(0.2, 0.8)`
3. Include single-channel ablations:
   - repository-only weighting
   - behavior-only weighting
4. Run the full suite with each pair.
5. Compare performance by evaluation mode and case type.

Look at:

- decision accuracy against benchmark label
- false approve rate on unsafe cases
- false reject rate on safe cases
- calibration gap between channel score and final outcome
- explanation consistency between dominant evidence channel and final decision
- confidence interval width for the main metrics across repeated runs

Good outcome:

- a weight pair that improves unsafe-case handling without creating unacceptable false-review or false-reject burden

### Experiment 2 — Hybrid Threshold Calibration

Use this when:

- `hybrid` sends too many cases to `REVIEW`
- clear unsafe cases slip through
- disagreement-heavy slices are unstable

Method:

1. Define several threshold bundles for:
   - `hybrid_dual_channel_reject`
   - `hybrid_cross_channel_review`
   - `hybrid_channel_mismatch_review`
2. Sweep representative values such as:
   - dual-channel reject threshold: `0.65 / 0.70 / 0.72 / 0.75 / 0.80`
   - mismatch gap threshold: `0.20 / 0.25 / 0.35 / 0.45`
3. Run the hybrid suite under each bundle.
4. Compare:
   - unsafe false approvals
   - unnecessary reviews on clearly safe cases
   - decision stability under minor score perturbations
   - interval overlap between neighboring threshold bundles

Look at:

- unsafe false approve rate
- review inflation rate
- threshold sensitivity
- decision stability across repeated runs
- worst-case error on disagreement-heavy cases

Good outcome:

- thresholds that control unsafe approvals without turning every disagreement into review noise

### Experiment 3 — Multilingual Uncertainty Thresholds

Use this when:

- multilingual cases are under-escalated
- multilingual cases are over-escalated
- language-mixed transcripts are unstable

Method:

1. Build multilingual case pairs:
   - English baseline
   - translated equivalent
   - noisy / partial / code-switched variant
2. Sweep representative trigger values such as:
   - `translation_confidence < 0.70`
   - `translation_confidence < 0.80`
   - `translation_confidence < 0.90`
3. Compare heuristic bundles:
   - confidence-only
   - `unknown` language only
   - confidence plus `unknown`
4. Measure whether uncertain cases are appropriately pushed to `REVIEW`.

Look at:

- unsafe false approve rate in multilingual cases
- over-review rate in high-confidence multilingual cases
- agreement between human annotators and uncertainty trigger
- interval stability of the uncertainty-triggered review rate
- worst-case miss rate on multilingual unsafe cases

Good outcome:

- ambiguous multilingual cases move to `REVIEW`, but clean multilingual evidence does not trigger unnecessary review

## Taxonomy Validation

### Experiment 4 — Current Taxonomy vs. `proj-2` Taxonomy

Use this when:

- expert outputs are too repetitive
- expert roles are hard to explain to users
- taxonomy labels changed but behavior did not improve

Compare:

- current:
  - Policy & Compliance
  - Adversarial Misuse
  - System & Deployment
- alternative:
  - Security & Adversarial Robustness
  - Data, Content & Behavioral Safety
  - Governance, Compliance & Societal Risk

Method:

1. Re-label the benchmark cases with dominant review lens.
2. Run both taxonomy schemes with equivalent prompts and aggregation logic.
3. Compare:
   - expert diversity
   - evidence specialization
   - final decision accuracy
   - stakeholder interpretability
   - robustness of those results across repeated runs

Look at:

- pairwise expert output similarity
- lens-specific finding recall
- council decision accuracy
- reviewer-rated clarity of expert roles
- interval overlap for decision accuracy between taxonomy schemes

Good outcome:

- clearer expert specialization, lower overlap, and better downstream decisions

## Deliberation Validation

### Experiment 5 — Evidence-Routing Ablation

Use this when:

- critiques keep citing the same refs
- deliberation looks repetitive
- routing logic has become too complex to justify

Compare:

- current lens-aware routing
- shared default refs for all critiques
- repository-heavy routing
- behavior-heavy routing
- mixed top-k evidence routing based on case type

Method:

1. Freeze the same expert outputs for a benchmark slice.
2. Re-run deliberation with each routing strategy.
3. Have human annotators score the resulting trace.

Annotation rubric:

- critique specificity
- evidence relevance
- cross-expert differentiation
- usefulness for final arbitration

Look at:

- average critique quality score
- unique evidence reference rate
- change in final decision accuracy
- change in stakeholder readability
- stability of those gains across repeated runs

Good outcome:

- more specific critiques, better evidence diversity, and no loss in final decision quality

## Annotation Scheme

Every benchmark item should be annotated with:

- evaluation mode
- expected decision
- primary failure mode
- dominant evidence channel
- multilingual uncertainty required: yes/no
- expected human-review requirement
- notes on acceptable alternate decisions

Annotators:

- at least two independent reviewers
- one adjudication pass for disagreements

Recommended agreement metrics:

- Cohen's kappa or Krippendorff's alpha for categorical labels
- percent agreement for dominant channel and uncertainty labels

## What To Save From Each Validation Run

Each validation run should produce:

- benchmark manifest
- benchmark case id and annotation source
- baseline identifier
- run identifier / seed identifier when applicable
- raw per-expert outputs
- council decision logs
- calibration tables
- confusion matrices by mode
- ablation summary for thresholds and routing choices
- final recommendation memo for parameter updates

Recommended per-run logging fields:

- `evaluation_mode`
- `repository_channel_score`
- `behavior_channel_score`
- `blended_score`
- `decision`
- `decision_rule_triggered`
- `uncertainty_flag`
- `translation_confidence`
- `detected_languages`
- `expert_name`
- `expert_risk_score`
- `expert_confidence`
- `expert_evaluation_status`
- `expert_metadata.taxonomy_slug`
- `cross_expert_critique`
- `key_evidence`
- `ignored_signals`
- `ground_truth_label`
- `benchmark_case_id`
- `baseline_system_id`
- `run_id`
- `seed`
- `is_critical_case`
- `critical_failure_type`
- `slice_label`

## Suggested Working Order

### Phase 1 — Benchmark Assembly

- create benchmark cases for repository-only, behavior-only, and hybrid
- define annotation rubric
- freeze labels

### Phase 2 — Calibration Runs

- weight sweep
- threshold sweep
- uncertainty sweep
- repeated-run evaluation
- bootstrap or interval estimation for key metrics

### Phase 3 — Structural Ablations

- taxonomy comparison
- evidence-routing comparison

### Phase 4 — Decision Update

- adopt the best-performing configuration
- record rationale in versioned config or docs
- rerun regression tests

## Multi-Agent Validation Workflow

If you are doing a larger validation cycle, use a four-agent workflow so the benchmark and analysis do not collapse into one person's intuition:

### Agent 1 — Literature Mapper

Responsibilities:

- maintain the source map for council, multilingual uncertainty, repository assurance, behavior probing, and hybrid assurance
- keep README and `ARCHITECTURE.md` citations aligned with the implementation

Deliverables:

- citation map
- updated validation rationale

### Agent 2 — Benchmark Designer

Responsibilities:

- create and label repository-only, behavior-only, hybrid, multilingual, and disagreement cases
- maintain the annotation rubric and benchmark manifest

Deliverables:

- benchmark cases
- annotation guide
- frozen labels

### Agent 3 — Evaluation Runner

Responsibilities:

- run weight sweeps, threshold sweeps, uncertainty sweeps, taxonomy ablations, and evidence-routing ablations
- export metrics and comparison tables

Deliverables:

- experiment tables
- confusion matrices
- calibration summaries

### Agent 4 — Synthesis Writer

Responsibilities:

- interpret the results
- recommend parameter updates
- document which settings are validated, provisional, or rejected

Deliverables:

- final validation memo
- updated configuration rationale

## When a Setting Counts as "Validated"

These design choices should be treated as validated only after the project can show:

- benchmark cases with frozen labels
- reproducible experimental runs
- explicit comparison against at least one reasonable alternative
- repeated-run results rather than single-run anecdotes
- interval-based reporting for the main safety metrics
- dedicated long-tail / worst-case analysis for critical slices
- written rationale for any threshold or taxonomy that remains in production
