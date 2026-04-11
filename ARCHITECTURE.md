# Architecture and Validation Rationale

This document explains why the major modules in `AI-Safety-Lab` are structured the way they are, what external research or standards support those choices, and where the current implementation still depends on project-specific empirical validation.

## System Overview

The repository supports three evaluation modes:

- `repository_only`: evaluate a submitted repository as a pre-deployment artifact
- `behavior_only`: evaluate a transcript or target-behavior trace
- `hybrid`: combine repository evidence and behavior evidence in one council decision

Across all three modes, the system follows the same high-level flow:

1. intake and normalization
2. evidence extraction
3. three expert assessments
4. critique / revision trace
5. explicit council arbitration
6. stakeholder-readable report and JSON artifacts

## Validation / Design Rationale

The system is not a clone of any single benchmark or paper. It is an assurance-oriented architecture assembled from multiple validated components.

### 1. Council of Experts and Critique

The council structure is informed by work on adversarial debate, critique-based refinement, and scalable oversight:

- `AI Safety via Debate` argues that adversarial argument between models can help surface truthful or safety-relevant distinctions that a judge would otherwise miss.  
  Source: https://arxiv.org/abs/1805.00899
- `Scalable AI Safety via Doubly-Efficient Debate` further supports structured multi-agent critique as an oversight mechanism rather than simple majority voting.  
  Source: https://arxiv.org/abs/2311.14125
- `Constitutional AI` validates critique-and-revision as a practical alignment pattern.  
  Source: https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback
- Anthropic's `Measuring Progress on Scalable Oversight for Large Language Models` supports treating model-assisted review as a structured oversight problem rather than a single-pass classification problem.  
  Source: https://www.anthropic.com/news/measuring-progress-on-scalable-oversight-for-large-language-models

Why this matters here:

- three experts are meant to expose different failure modes
- critique and revision create an auditable path from initial verdict to final verdict
- explicit arbitration rules make the final decision inspectable instead of opaque

### 2. Multilingual Uncertainty

The behavior layer records `detected_languages`, `translation_confidence`, and `uncertainty_flag` because multilingual safety is not reliably captured by English-only reasoning.

Relevant support:

- `All Languages Matter: On the Multilingual Safety of LLMs` shows that safety performance varies substantially across languages.  
  Source: https://aclanthology.org/2024.findings-acl.349/
- `Uncertainty-Aware Machine Translation Evaluation` supports treating translation quality as an uncertainty-sensitive measurement problem instead of a binary pass/fail assumption.  
  Source: https://aclanthology.org/2021.findings-emnlp.330/
- `Conformalizing Machine Translation Evaluation` supports calibration-aware treatment of translation quality and uncertainty.  
  Source: https://aclanthology.org/2024.tacl-1.80/
- `BenchMAX` treats multilingual coverage as a first-class evaluation dimension for LLMs.  
  Source: https://aclanthology.org/2025.findings-emnlp.909/

Why this matters here:

- `behavior_only` should not overclaim confidence when a transcript is low-confidence or non-English
- `hybrid` should be able to push ambiguous multilingual cases to review instead of forcing false precision

### 3. Repository Channel

The repository channel is justified as software assurance applied to an AI system's deployable artifact.

Primary support:

- `NIST SP 800-218 Secure Software Development Framework (SSDF)` supports review of software implementation, secure development practices, and deployment-facing controls.  
  Source: https://csrc.nist.gov/pubs/sp/800/218/final

Why this matters here:

- static evidence such as upload surfaces, authentication gaps, secret handling, and model integrations is audit-ready
- repository evidence is reproducible on a clean machine and easy to trace to `file:line`

### 4. Behavior Channel

The behavior channel is justified as runtime safety testing and red teaming.

Primary support:

- `OWASP AI Testing Guide` treats AI testing as broader than prompt-level evaluation alone and includes system, application, and model concerns.  
  Source: https://owasp.org/www-project-ai-testing-guide/
- `OWASP GenAI Red Teaming Guide` supports adversarial probing for misuse, prompt injection, safety boundary failures, and related runtime behaviors.  
  Source: https://genai.owasp.org/resource/genai-red-teaming-guide/
- `NIST AI 100-2e2025` provides a common taxonomy for adversarial machine-learning attacks and mitigations.  
  Source: https://csrc.nist.gov/pubs/ai/100/2/e2025/final
- `MITRE ATLAS` gives a structured attack taxonomy for AI-enabled systems.  
  Source: https://atlas.mitre.org/pdf-files/MITRE_ATLAS_Fact_Sheet.pdf

Why this matters here:

- behavior probes capture evidence that static repository review misses
- refusal behavior, secret leakage, instruction override, and misuse markers are observable from transcripts and live responses

### 5. Hybrid Assurance

The hybrid mode is the project's main systems-assurance claim: repository evidence and behavior evidence should be evaluated together because each channel captures failure modes the other can miss.

Primary support:

- `NIST AI RMF 1.0` supports the idea that AI risk management spans governance, measurement, and operational control rather than a single test.  
  Source: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10
- `NIST AI RMF Generative AI Profile` makes that idea concrete for GenAI systems, including testing and red teaming.  
  Source: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
- `MITRE AI Assurance: A Repeatable Process for Assuring AI-enabled Systems` supports repeatable system-level assurance rather than one-shot model scoring.  
  Source: https://www.mitre.org/news-insights/publication/ai-assurance-repeatable-process-assuring-ai-enabled-systems

Why this matters here:

- repository evidence is strong for implementation and deployment risk
- behavior evidence is strong for runtime misuse and safety-control effectiveness
- a pre-deployment council should be able to reconcile both

## What Is Strongly Supported vs. What Still Needs Validation

### Strongly Supported

- using multiple expert perspectives
- using critique / revision as an oversight mechanism
- treating multilingual uncertainty explicitly
- combining static and dynamic assurance activities at the standards level

### Project-Specific Choices That Still Need Empirical Validation

These choices are reasonable engineering decisions, but they are not directly validated by a single external paper:

- the weights behind `repository_channel_score` and `behavior_channel_score`
- the thresholds behind `hybrid_dual_channel_reject`, `hybrid_cross_channel_review`, and mismatch rules
- the trigger thresholds for `uncertainty_flag`
- whether the current expert taxonomy is better than the original `proj-2` taxonomy for this product
- which evidence-routing policy produces the most useful deliberation outcomes

Those questions require benchmark design and measurement inside this project. See [VALIDATION_PLAN.md](VALIDATION_PLAN.md).
