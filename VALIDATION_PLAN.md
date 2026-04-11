# Benchmark Validation Plan

This document defines how to empirically validate the major project-specific design choices in `AI-Safety-Lab` that are not settled by external standards alone.

## Objective

Validate whether the current `repository_only`, `behavior_only`, and `hybrid` decision logic is better calibrated, more useful, and more reproducible than plausible alternatives.

## Research Questions

1. Are the current `repository_channel_score` and `behavior_channel_score` weights appropriate?
2. Are the current hybrid arbitration thresholds correctly calibrated?
3. Are the multilingual `uncertainty_flag` thresholds appropriately conservative?
4. Is the current expert taxonomy better than a more direct `proj-2` taxonomy mapping?
5. Does the current deliberation evidence-routing improve decision quality over simpler routing strategies?

## Benchmark Design Principles

- Use paired cases whenever possible.
- Separate static-risk signals from runtime-risk signals so the council can be stress-tested under disagreement.
- Annotate ground truth at the case level before tuning thresholds.
- Measure both correctness and governance behavior, not just average score.
- Start with a tractable benchmark size, then expand once the harness is stable.
- Compare against at least one meaningful baseline instead of judging the current system in isolation.
- Prefer interval- and distribution-based decisions over single-run point estimates.
- Track long-tail failures separately from average performance.

Recommended starting size:

- 12 to 18 `repository_only` cases
- 12 to 18 `behavior_only` cases
- 12 to 18 `hybrid` cases
- ensure at least one-third of the behavior and hybrid cases include multilingual or code-switched evidence

## Baselines and Comparison Targets

Every benchmark study should compare the current configuration against at least one baseline:

- previous tagged release or prior commit
- repository-only council without behavior fusion
- behavior-only council without repository fusion
- simplified council baseline without critique or with shared evidence refs

The purpose is to answer a systems question:

- is the current design better than a simpler or earlier alternative?
- where does it improve?
- where does it regress?

Avoid interpreting a single benchmark score in isolation when no baseline is present.

## Repeated Testing and Statistical Reliability

Single-run scores are too fragile for model-based systems. The same benchmark should be re-run multiple times whenever the model path, prompt path, or stochastic generation path can vary.

Recommended protocol:

- run each benchmark configuration at least `5` times for smoke-level studies
- run each benchmark configuration `10` to `30` times for final calibration studies
- keep benchmark labels frozen while repeating runs
- store every run, not only the mean

Use repeated evaluation to estimate:

- mean decision accuracy
- run-to-run variance
- false approve variance
- false reject variance
- review-rate variance
- expert disagreement variance

Where appropriate, bootstrap the repeated results to estimate confidence intervals for the main metrics. The exact term matters less than the operational goal: do not treat one lucky run as evidence of a stable setting.

## Decision Criteria Based on Intervals, Not Single Scores

Production-facing decisions should be based on intervals or distributions rather than one point score.

Recommended rule:

- prefer mean plus confidence interval, or median plus percentile band
- accept a configuration only when its interval is comfortably above the alternative or comfortably below the target risk threshold
- send a configuration to further review when intervals overlap heavily or flip sign across runs

Examples:

- if a candidate configuration has higher average accuracy but its unsafe false-approve interval overlaps the baseline, the gain is not yet persuasive
- if a threshold reduces average risk but produces unstable `REVIEW` spikes across repeated runs, it should not be treated as validated

This matters especially for council thresholds and uncertainty handling, where brittle point estimates can hide unstable boundary behavior.

## Long-Tail and Worst-Case Analysis

Average performance is necessary but not sufficient for safety evaluation.

For high-risk metrics, explicitly track:

- worst-case behavior on benchmark slices
- failure rate on critical cases
- extreme outliers in unsafe false approvals
- long-tail multilingual failures
- rare but severe prompt-injection or secret-leakage misses

At minimum, report these alongside mean metrics:

- worst-case slice accuracy
- critical-case false approve count
- percentile bands for unsafe-case performance
- top-k most severe benchmark misses with rationale

The goal is to avoid approving a system that performs well on average but fails badly on rare high-consequence cases.

## Benchmark Suite

### Suite A — Repository Channel Cases

Purpose:
- test static implementation and deployment risk detection

Case types:
- unsafe upload / no-auth / secret handling failures
- safe repository with strong controls
- repository with risky model integrations but strong containment
- repository with misleading README or config claims

Ground-truth labels:
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

Ground-truth labels:
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

Ground-truth labels:
- expected final decision
- expected decision rationale
- expected dominant channel

## Experiments

### Experiment 1 — Channel Weight Calibration

Question:
- Are the current repository/behavior weights correct?

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

Primary metrics:

- decision accuracy against benchmark label
- false approve rate on unsafe cases
- false reject rate on safe cases
- calibration gap between channel score and final outcome
- explanation consistency between dominant evidence channel and final decision
- confidence interval width for the main metrics across repeated runs

Success criterion:

- choose the weight pair that minimizes unsafe false approvals while preserving acceptable false-review and false-reject rates

### Experiment 2 — Hybrid Threshold Calibration

Question:
- Are the current reject/review thresholds too strict or too weak?

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

Primary metrics:

- unsafe false approve rate
- review inflation rate
- threshold sensitivity
- decision stability across repeated runs
- worst-case error on disagreement-heavy cases

Success criterion:

- threshold bundle that strongly controls unsafe approvals without sending too many clear safe cases into `REVIEW`

### Experiment 3 — Multilingual Uncertainty Thresholds

Question:
- Are `translation_confidence` and `uncertainty_flag` thresholds calibrated?

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

Primary metrics:

- unsafe false approve rate in multilingual cases
- over-review rate in high-confidence multilingual cases
- agreement between human annotators and uncertainty trigger
- interval stability of the uncertainty-triggered review rate
- worst-case miss rate on multilingual unsafe cases

Success criterion:

- conservative handling of ambiguous multilingual cases without over-triggering uncertainty on clean multilingual evidence

## Taxonomy Validation

### Experiment 4 — Current Taxonomy vs. `proj-2` Taxonomy

Question:
- Is the current expert split better than a direct `proj-2`-style split?

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

Primary metrics:

- pairwise expert output similarity
- lens-specific finding recall
- council decision accuracy
- reviewer-rated clarity of expert roles
- interval overlap for decision accuracy between taxonomy schemes

Success criterion:

- prefer the taxonomy that yields clearer expert specialization and better final decisions without collapsing into repeated findings

## Deliberation Validation

### Experiment 5 — Evidence-Routing Ablation

Question:
- Which evidence-routing strategy improves deliberation quality the most?

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

Primary metrics:

- average critique quality score
- unique evidence reference rate
- change in final decision accuracy
- change in stakeholder readability
- stability of those gains across repeated runs

Success criterion:

- routing strategy that increases critique specificity and evidence relevance without degrading final decision accuracy

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

## Outputs and Artifacts

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

## Implementation Phases

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

Use a four-agent workflow so the benchmark and analysis do not collapse into one person's intuition:

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

## Deliverable Standard

These design choices should be treated as validated only after the project can show:

- benchmark cases with frozen labels
- reproducible experimental runs
- explicit comparison against at least one reasonable alternative
- repeated-run results rather than single-run anecdotes
- interval-based reporting for the main safety metrics
- dedicated long-tail / worst-case analysis for critical slices
- written rationale for any threshold or taxonomy that remains in production
