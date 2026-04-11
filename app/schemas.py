from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny


Decision = Literal["APPROVE", "REVIEW", "REJECT"]
EvaluationStatus = Literal["success", "degraded", "failed"]
TargetExecutionStatus = Literal["skipped", "success", "failed"]
SubmissionSource = Literal["github_url", "local_path", "manual"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionInfo(StrictModel):
    schema_version: str = "v3"
    orchestrator_version: str = "0.3.0"
    decision_rule_version: str = "matrix-v2"
    target_adapter_version: str = "repo-intake-v1"
    target_model_version: str = ""
    expert_model_backend: str = ""
    judge_versions: dict[str, str] = Field(default_factory=dict)


class SubmissionTarget(StrictModel):
    source_type: SubmissionSource = "manual"
    github_url: str = ""
    local_path: str = ""
    target_name: str = ""
    description: str = ""


class RepositoryEvidence(StrictModel):
    path: str
    signal: str
    why_it_matters: str


class RepositorySummary(StrictModel):
    target_name: str
    source_type: SubmissionSource = "manual"
    resolved_path: str = ""
    description: str = ""
    framework: str = "Unknown"
    entrypoints: list[str] = Field(default_factory=list)
    llm_backends: list[str] = Field(default_factory=list)
    media_modalities: list[str] = Field(default_factory=list)
    upload_surfaces: list[str] = Field(default_factory=list)
    auth_signals: list[str] = Field(default_factory=list)
    secret_signals: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    notable_files: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    detected_signals: list[str] = Field(default_factory=list)
    evidence_items: list[RepositoryEvidence] = Field(default_factory=list)
    file_count: int = 0
    summary: str = ""


class AgentContext(StrictModel):
    agent_name: str
    description: str = ""
    domain: str = "Other"
    capabilities: list[str] = Field(default_factory=list)
    high_autonomy: bool = False


class ConversationTurn(StrictModel):
    role: Literal["user", "assistant", "system"]
    content: str


class TargetExecutionRecord(StrictModel):
    prompt_index: int
    prompt: str
    response: str
    error: str | None = None


class TargetExecutionPackage(StrictModel):
    version: VersionInfo = Field(default_factory=VersionInfo)
    status: TargetExecutionStatus = "skipped"
    endpoint: str = ""
    model: str = ""
    prompt_source: str = "conversation"
    source_conversation: list[ConversationTurn] = Field(default_factory=list)
    prompts: list[str] = Field(default_factory=list)
    records: list[TargetExecutionRecord] = Field(default_factory=list)
    prompt_count: int = 0
    adapter_metadata: dict[str, Any] = Field(default_factory=dict)


class ExpertMetadata(StrictModel):
    expert_name: str
    team: str = ""
    execution_mode: str = ""
    runner_mode: str = ""
    judge_version: str = "v1"


class CouncilMetadata(StrictModel):
    council_name: str = "safety_council"
    decision_rule_version: str = "matrix-v2"
    members: list[ExpertMetadata] = Field(default_factory=list)


class ExpertInputPackage(StrictModel):
    version: VersionInfo = Field(default_factory=VersionInfo)
    context: AgentContext
    selected_policies: list[str] = Field(default_factory=list)
    source_conversation: list[ConversationTurn] = Field(default_factory=list)
    enriched_conversation: list[ConversationTurn] = Field(default_factory=list)
    attack_turns: list[ConversationTurn] = Field(default_factory=list)
    target_output_turns: list[ConversationTurn] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    target_execution: TargetExecutionPackage | None = None
    submission: SubmissionTarget | None = None
    repository_summary: RepositorySummary | None = None


class Team1PolicyInput(ExpertInputPackage):
    policy_term_index: dict[str, list[str]] = Field(default_factory=dict)


class Team2RedTeamInput(ExpertInputPackage):
    tier: int = 2
    dimensions: list[str] = Field(default_factory=list)
    protocol_bundle: dict[str, Any] = Field(default_factory=dict)


class Team3RiskInput(ExpertInputPackage):
    protocol_plan: dict[str, Any] = Field(default_factory=dict)
    rule_baseline: dict[str, Any] = Field(default_factory=dict)


class ExpertDetailPayload(StrictModel):
    detail_type: str = "generic"
    source: str = "rules"
    evaluation_status: EvaluationStatus = "success"
    notes: list[str] = Field(default_factory=list)
    structured_input: dict[str, Any] = Field(default_factory=dict)


class PolicyRiskMapping(StrictModel):
    policy: str
    score: float = Field(ge=0.0)
    status: Literal["pass", "needs_attention", "fail"]
    reason: str


class RedTeamDimensionScore(StrictModel):
    dimension: str
    score_1_to_5: float = Field(ge=1.0, le=5.0)
    weight: float = Field(ge=0.0)


class RedTeamProtocolResult(StrictModel):
    protocol_id: str
    status: Literal["PASS", "FAIL"]
    score: float = Field(ge=0.0, le=100.0)


class Team1PolicyDetail(ExpertDetailPayload):
    detail_type: Literal["team1_policy"] = "team1_policy"
    selected_policies: list[str] = Field(default_factory=list)
    policy_alerts: list[PolicyRiskMapping] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)
    policy_scopes: dict[str, list[str]] = Field(default_factory=dict)


class Team2RedTeamDetail(ExpertDetailPayload):
    detail_type: Literal["team2_redteam"] = "team2_redteam"
    tier: int = 1
    dimensions: list[str] = Field(default_factory=list)
    category_questions: dict[str, list[str]] = Field(default_factory=dict)
    scenario_stack: list[str] = Field(default_factory=list)
    dimension_scores: list[RedTeamDimensionScore] = Field(default_factory=list)
    protocol_results: list[RedTeamProtocolResult] = Field(default_factory=list)
    protocol_bundle: dict[str, Any] = Field(default_factory=dict)
    weighted_score_1_5: float = 0.0


class Team3RiskProtocolResult(StrictModel):
    protocol_id: str
    status: Literal["PASS", "FAIL"]
    score: float = Field(ge=0.0, le=100.0)


class Team3RiskDetail(ExpertDetailPayload):
    detail_type: Literal["team3_risk"] = "team3_risk"
    domain: str = "Other"
    capabilities: list[str] = Field(default_factory=list)
    high_autonomy: bool = False
    protocol_plan: dict[str, Any] = Field(default_factory=dict)
    protocol_results: list[Team3RiskProtocolResult] = Field(default_factory=list)
    rule_baseline: dict[str, Any] = Field(default_factory=dict)


class ExpertVerdict(StrictModel):
    expert_name: str
    evaluation_status: EvaluationStatus = "success"
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    critical: bool = False
    risk_tier: str = "UNKNOWN"
    summary: str
    findings: list[str] = Field(default_factory=list)
    detail_payload: SerializeAsAny[ExpertDetailPayload] = Field(default_factory=ExpertDetailPayload)
    evidence: dict[str, Any] = Field(default_factory=dict)
    metadata: ExpertMetadata | None = None


class DeliberationExchange(StrictModel):
    phase: Literal["initial", "critique", "defense", "revision"]
    author_expert: str
    target_expert: str = ""
    summary: str
    risk_delta: float = 0.0
    evidence_refs: list[str] = Field(default_factory=list)


class CouncilResult(StrictModel):
    decision: Decision
    council_score: float = Field(ge=0.0, le=1.0)
    needs_human_review: bool
    rationale: str
    decision_rule_triggered: str = ""
    initial_decision: Decision | None = None
    initial_decision_rule_triggered: str = ""
    deliberation_enabled: bool = False
    consensus_summary: str = ""
    cross_expert_critique: list[str] = Field(default_factory=list)
    deliberation_trace: list[DeliberationExchange] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    disagreement_index: float = Field(ge=0.0, le=1.0)
    triggered_by: list[str] = Field(default_factory=list)
    key_evidence: list[str] = Field(default_factory=list)
    ignored_signals: list[str] = Field(default_factory=list)
    decision_rule_version: str = "matrix-v2"
    metadata: CouncilMetadata | None = None


class EvaluationRequest(StrictModel):
    version: VersionInfo = Field(default_factory=VersionInfo)
    status: EvaluationStatus = "success"
    context: AgentContext
    selected_policies: list[str] = Field(default_factory=list)
    conversation: list[ConversationTurn] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    target_execution: TargetExecutionPackage | None = None
    expert_input: ExpertInputPackage | None = None
    submission: SubmissionTarget | None = None
    repository_summary: RepositorySummary | None = None
    calibration_case_id: str = ""


class EvaluationResponse(StrictModel):
    evaluation_id: str
    status: EvaluationStatus = "success"
    version: VersionInfo = Field(default_factory=VersionInfo)
    decision: Decision
    council_result: CouncilResult
    experts: list[ExpertVerdict]
    target_execution: TargetExecutionPackage | None = None
    expert_input: ExpertInputPackage | None = None
    submission: SubmissionTarget | None = None
    repository_summary: RepositorySummary | None = None
    report_path: str
    archive_path: str = ""
