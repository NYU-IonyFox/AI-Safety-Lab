from fastapi import FastAPI, HTTPException

from app.intake.submission_service import SubmissionError
from app.orchestrator import SafetyLabOrchestrator
from app.schemas import EvaluationRequest, EvaluationResponse

app = FastAPI(title="UNICC AI Safety Lab", version="0.3.0")
orchestrator = SafetyLabOrchestrator()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/evaluations", response_model=EvaluationResponse)
def evaluate(request: EvaluationRequest) -> EvaluationResponse:
    try:
        return orchestrator.evaluate(request)
    except SubmissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
