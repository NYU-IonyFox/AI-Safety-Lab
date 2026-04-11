import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.analyzers import summarize_repository
from app.audit import ensure_storage_ready
from app.council import synthesize_council
from app.intake.submission_service import SubmissionError
from app.orchestrator import SafetyLabOrchestrator
from app.schemas import AgentContext, EvaluationRequest, EvaluationResponse, SubmissionTarget

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage_ready()
    preflight = orchestrator.runtime_preflight()
    if preflight.get("warning"):
        logger.warning("%s", preflight["warning"])
    yield


app = FastAPI(title="UNICC AI Safety Lab", version="0.3.0", lifespan=lifespan)
orchestrator = SafetyLabOrchestrator()


@app.get("/")
def root() -> dict[str, str]:
    preflight = orchestrator.runtime_preflight()
    return {
        "name": "UNICC AI Safety Lab API",
        "status": "ok",
        "docs_url": "/docs",
        "health_url": "/health",
        "smoke_test_url": "/smoke-test",
        "evaluation_endpoint": "/v1/evaluations",
        "default_backend": orchestrator.version.expert_model_backend,
        "cli_hint": "Run `ai-safety-lab-eval --github-url https://github.com/owner/repository` for a no-schema CLI path.",
        "frontend_hint": "Run `streamlit run frontend/streamlit_app.py` for the stakeholder-facing UI.",
        "fallback_hint": "If local HF execution fails, expert verdicts degrade to rules_fallback and record the reason in metadata.",
        "runtime_preflight_status": preflight["status"],
        "configured_execution_mode": preflight["configured_execution_mode"],
        "startup_warning": preflight["warning"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/smoke-test")
def smoke_test() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[1]
    request = EvaluationRequest(
        context=AgentContext(agent_name="smoke-test", domain="Other", capabilities=[], high_autonomy=False),
        selected_policies=["eu_ai_act", "us_nist", "iso", "unesco"],
        conversation=[],
        metadata={},
        submission=SubmissionTarget(
            source_type="local_path",
            local_path=str(repo_root),
            target_name="smoke-test",
            description="Internal readiness probe",
        ),
    )
    repository_summary = summarize_repository(
        str(repo_root),
        target_name="smoke-test",
        source_type="local_path",
        description="Internal readiness probe",
    )
    normalized_request = orchestrator._normalize_request(request, repository_summary)
    target_execution = orchestrator._build_target_execution(normalized_request)
    behavior_summary = orchestrator._build_behavior_summary(
        normalized_request,
        target_execution,
        repository_summary,
        source_conversation=request.conversation,
    )
    expert_input = orchestrator._build_expert_input(
        normalized_request,
        target_execution,
        repository_summary,
        behavior_summary,
        source_conversation=request.conversation,
    )
    request = normalized_request.model_copy(
        update={
            "version": orchestrator._request_version(normalized_request),
            "target_execution": target_execution,
            "behavior_summary": behavior_summary,
            "expert_input": expert_input,
            "repository_summary": repository_summary,
        }
    )

    verdicts = []
    expert_statuses: dict[str, dict[str, str]] = {}
    label_map = {
        "team1_policy_expert": "policy_and_compliance",
        "team2_redteam_expert": "adversarial_misuse",
        "team3_risk_expert": "system_and_deployment",
    }

    for expert in orchestrator.experts:
        try:
            verdict = expert.assess(request)
        except Exception as exc:  # noqa: BLE001
            return {
                "smoke_test": "fail",
                "llm_backend": orchestrator.version.expert_model_backend,
                "failed_module": expert.name,
                "error": str(exc),
            }
        verdicts.append(verdict)
        expert_statuses[label_map.get(expert.name, expert.name)] = {
            "module": expert.name,
            "status": "ok",
            "evaluation_status": verdict.evaluation_status,
            "risk_tier": verdict.risk_tier,
            "runner_mode": str(verdict.evidence.get("execution_path", "unknown")),
            "backend": str(verdict.evidence.get("configured_backend", orchestrator.version.expert_model_backend)),
            "fallback_reason": str(verdict.evidence.get("fallback_reason", "")),
        }

    council = synthesize_council(verdicts)
    return {
        "smoke_test": "pass",
        "llm_backend": orchestrator.version.expert_model_backend,
        "configured_execution_mode": orchestrator.experts[0].configured_execution_mode() if orchestrator.experts else "unknown",
        "evaluation_mode": request.evaluation_mode,
        "behavior_summary": behavior_summary.model_dump(),
        "experts": expert_statuses,
        "council_preview": {
            "decision": council.decision,
            "decision_rule_triggered": council.decision_rule_triggered,
        },
    }


@app.post("/v1/evaluations", response_model=EvaluationResponse)
def evaluate(request: EvaluationRequest) -> EvaluationResponse:
    try:
        return orchestrator.evaluate(request)
    except SubmissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
