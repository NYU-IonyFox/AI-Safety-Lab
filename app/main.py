from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.audit import ensure_storage_ready
from app.council import synthesize_council
from app.intake.submission_service import SubmissionError
from app.orchestrator import SafetyLabOrchestrator
from app.schemas import AgentContext, EvaluationRequest, EvaluationResponse, SubmissionTarget


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage_ready()
    yield


app = FastAPI(title="UNICC AI Safety Lab", version="0.3.0", lifespan=lifespan)
orchestrator = SafetyLabOrchestrator()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "UNICC AI Safety Lab API",
        "status": "ok",
        "docs_url": "/docs",
        "health_url": "/health",
        "smoke_test_url": "/smoke-test",
        "evaluation_endpoint": "/v1/evaluations",
        "cli_hint": "Run `ai-safety-lab-eval --github-url https://github.com/owner/repository` for a no-schema CLI path.",
        "frontend_hint": "Run `streamlit run frontend/streamlit_app.py` for the stakeholder-facing UI.",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/smoke-test")
def smoke_test() -> dict[str, object]:
    request = EvaluationRequest(
        context=AgentContext(agent_name="smoke-test", domain="Other", capabilities=[], high_autonomy=False),
        selected_policies=["eu_ai_act", "us_nist", "iso", "unesco"],
        conversation=[],
        metadata={},
        submission=SubmissionTarget(source_type="manual", target_name="smoke-test", description="Internal readiness probe"),
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
        }

    council = synthesize_council(verdicts)
    return {
        "smoke_test": "pass",
        "llm_backend": orchestrator.version.expert_model_backend,
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
