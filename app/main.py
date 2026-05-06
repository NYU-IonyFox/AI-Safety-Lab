import glob
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit import ensure_storage_ready
from app.orchestrator import run_evaluation
from app.safe_schemas import EvidenceBundle, SAFEEvaluationResponse, TranslationReport
from app.schemas import EvaluationRequest

logger = logging.getLogger(__name__)

REPORTS_DIR: str = os.getenv("SAFE_REPORTS_DIR", "reports")


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage_ready()
    yield


app = FastAPI(title="UNICC AI Safety Lab", version="0.3.0", lifespan=lifespan)

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
_STATIC_DIR = _FRONTEND_DIR / "static"
_TEMPLATES_DIR = _FRONTEND_DIR / "templates"

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR)) if _TEMPLATES_DIR.exists() else None


def root() -> dict:
    """Returns API metadata dict. Kept callable for test_api.py compatibility."""
    return {
        "name": "UNICC AI Safety Lab API",
        "status": "ok",
        "docs_url": "/docs",
        "health_url": "/health",
        "smoke_test_url": "/smoke-test",
        "evaluation_endpoint": "/v1/evaluations",
        "runtime_preflight_status": "ok",
        "configured_execution_mode": os.getenv("EXECUTION_MODE", "llm_api"),
        "startup_warning": "",
    }


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    if _templates:
        return _templates.TemplateResponse(request, "index.html")
    info = root()
    return HTMLResponse(content=f"<h1>SAFE</h1><pre>{json.dumps(info, indent=2)}</pre>")


@app.get("/result", response_class=HTMLResponse, include_in_schema=False)
def result_page(request: Request):
    if _templates:
        return _templates.TemplateResponse(request, "result.html")
    return HTMLResponse(content="<h1>SAFE — Result</h1>")


@app.get("/health", summary="Health check", description="Simple liveness probe for the API process.")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _detect_provider(api_key: str) -> str | None:
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    if api_key.startswith("AIza"):
        return "gemini"
    if api_key.startswith("sk-"):
        return "openai"
    return None


@app.post(
    "/v1/evaluations",
    response_model=SAFEEvaluationResponse,
    summary="Run a SAFE council evaluation",
    description=(
        "Accepts an EvaluationRequest (GitHub URL, conversation, or document). "
        "Runs L1 translation → L3 Expert Council → L4 Arbitration → L5 Output."
    ),
)
def evaluate(request: EvaluationRequest = Body(...)) -> SAFEEvaluationResponse:
    api_key = request.metadata.get("api_key", "") or os.getenv("ANTHROPIC_API_KEY", "")
    provider = _detect_provider(api_key) if api_key else None

    _mode_to_input_type = {
        "behavior_only": "conversation",
        "repository_only": "github",
        "hybrid": "github",
    }
    input_type = _mode_to_input_type.get(request.evaluation_mode, "conversation")

    # L1 — Translation (fail-safe: fall back to no-translation report on any error)
    conversation_text = " ".join(t.content for t in request.conversation)
    try:
        from app.translation.translation_service import translate
        translation_report = translate(conversation_text, api_key=api_key or None, provider=provider)
    except Exception:
        translation_report = TranslationReport(translation_applied=False, primary_language="en")

    # Build EvidenceBundle for L3–L5
    content: dict = {
        "api_key": api_key,
        "target_name": request.context.agent_name,
        "conversation": [t.model_dump() for t in request.conversation],
        "evaluation_mode": request.evaluation_mode,
        "metadata": {k: v for k, v in request.metadata.items() if k != "api_key"},
    }
    if request.submission:
        content["submission"] = request.submission.model_dump()

    bundle = EvidenceBundle(
        input_type=input_type,
        translation_report=translation_report,
        content=content,
    )
    print(f"[/v1/evaluations] input_type={bundle.input_type}, translation_applied={bundle.translation_report.translation_applied}")
    safe_response = run_evaluation(bundle)
    print(f"[/v1/evaluations] verdict={safe_response.verdict}, experts={len(safe_response.experts)}")
    return safe_response


@app.post(
    "/evaluate",
    response_model=SAFEEvaluationResponse,
    summary="SAFE evaluation (direct EvidenceBundle)",
    include_in_schema=False,
)
def evaluate_safe(bundle: EvidenceBundle) -> SAFEEvaluationResponse:
    return run_evaluation(bundle)


@app.get(
    "/report/{evaluation_id}",
    summary="Download evaluation PDF report",
    description="Returns the PDF report for the given evaluation_id, or 404 if not found.",
)
def get_report(evaluation_id: str) -> FileResponse:
    pattern = str(Path(REPORTS_DIR) / f"{evaluation_id}_*.pdf")
    matches = glob.glob(pattern)
    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No PDF report found for evaluation_id: {evaluation_id}",
        )
    return FileResponse(matches[0], media_type="application/pdf", filename=Path(matches[0]).name)


def _find_archive(evaluation_id: str) -> Path | None:
    """Search known report directories for a JSON archive matching evaluation_id."""
    from app.config import REPORT_DIR
    search_dirs = [
        Path(REPORTS_DIR),
        REPORT_DIR,
        Path("data") / "reports",
    ]
    for d in search_dirs:
        for pattern in [f"*{evaluation_id}*.json", f"{evaluation_id}*.json"]:
            matches = glob.glob(str(d / pattern))
            if matches:
                return Path(matches[0])
    return None


@app.get(
    "/v1/evaluations/{evaluation_id}/pdf",
    summary="Download evaluation PDF (v1 path)",
    include_in_schema=False,
)
def get_evaluation_pdf(evaluation_id: str) -> FileResponse:
    return get_report(evaluation_id)


@app.get(
    "/v1/evaluations/{evaluation_id}/json",
    summary="Download evaluation JSON archive (v1 path)",
    include_in_schema=False,
)
def get_evaluation_json(evaluation_id: str):
    archive = _find_archive(evaluation_id)
    if not archive:
        raise HTTPException(
            status_code=404,
            detail=f"No JSON archive found for evaluation_id: {evaluation_id}",
        )
    return FileResponse(
        str(archive),
        media_type="application/json",
        filename=archive.name,
    )


@app.get(
    "/v1/evaluations/{evaluation_id}",
    summary="Get evaluation result by ID (v1 path)",
    include_in_schema=False,
)
def get_evaluation(evaluation_id: str):
    archive = _find_archive(evaluation_id)
    if not archive:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation not found: {evaluation_id}",
        )
    with open(str(archive), encoding="utf-8") as f:
        return JSONResponse(json.load(f))
