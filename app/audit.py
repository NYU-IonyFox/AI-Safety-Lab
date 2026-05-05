import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from app.config import AUDIT_LOG, DATA_DIR, REPORT_DIR
from app.schemas import CouncilResult, EvaluationRequest, ExpertVerdict


REDACTED = "[REDACTED]"


def ensure_storage_ready() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_paths() -> None:
    ensure_storage_ready()


def _mask_endpoint(endpoint: str) -> str:
    if not endpoint:
        return ""
    parts = urlsplit(endpoint)
    safe_netloc = parts.hostname or ""
    if parts.port:
        safe_netloc = f"{safe_netloc}:{parts.port}"
    return urlunsplit((parts.scheme, safe_netloc, parts.path, "", ""))


def _truncate_text(text: str, limit: int = 280) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


def _redact_request(request: EvaluationRequest) -> tuple[dict, dict]:
    redacted_fields: list[str] = []
    metadata = dict(request.metadata)

    if metadata.pop("target_api_key", None) is not None:
        redacted_fields.append("metadata.target_api_key")
    if "target_body" in metadata and isinstance(metadata["target_body"], dict):
        body = dict(metadata["target_body"])
        removed = []
        for key in list(body.keys()):
            lower = key.lower()
            if any(token in lower for token in ("key", "token", "secret", "password", "authorization")):
                body[key] = REDACTED
                removed.append(f"metadata.target_body.{key}")
        metadata["target_body"] = body
        redacted_fields.extend(removed)
    if "target_endpoint" in metadata:
        metadata["target_endpoint"] = _mask_endpoint(str(metadata.get("target_endpoint", "")))
        redacted_fields.append("metadata.target_endpoint")

    conversation = [{"role": turn.role, "content": _truncate_text(turn.content)} for turn in request.conversation]

    expert_input = request.expert_input.model_dump() if request.expert_input else None
    if isinstance(expert_input, dict):
        for key in ("source_conversation", "enriched_conversation", "attack_turns", "target_output_turns"):
            if isinstance(expert_input.get(key), list):
                expert_input[key] = [
                    {**turn, "content": _truncate_text(str(turn.get("content", "")))}
                    for turn in expert_input[key]
                    if isinstance(turn, dict)
                ]

    target_execution = request.target_execution.model_dump() if request.target_execution else None
    if isinstance(target_execution, dict):
        target_execution["endpoint"] = _mask_endpoint(str(target_execution.get("endpoint", "")))
        redacted_fields.append("target_execution.endpoint")
        if isinstance(target_execution.get("records"), list):
            target_execution["records"] = [
                {
                    **record,
                    "prompt": _truncate_text(str(record.get("prompt", ""))),
                    "response": _truncate_text(str(record.get("response", ""))),
                }
                for record in target_execution["records"]
                if isinstance(record, dict)
            ]

    payload = {
        "version": request.version.model_dump(),
        "context": request.context.model_dump(),
        "selected_policies": list(request.selected_policies),
        "conversation": conversation,
        "metadata": metadata,
        "submission": request.submission.model_dump() if request.submission else None,
        "repository_summary": request.repository_summary.model_dump() if request.repository_summary else None,
        "calibration_case_id": request.calibration_case_id,
        "target_execution": target_execution,
        "expert_input": expert_input,
    }
    summary = {
        "strategy": "redaction-before-archive",
        "redacted_fields": sorted(set(redacted_fields)),
        "conversation_turn_count": len(request.conversation),
        "target_record_count": len(request.target_execution.records) if request.target_execution else 0,
    }
    return payload, summary


def persist_evaluation(
    request: EvaluationRequest,
    experts: list[ExpertVerdict],
    council: CouncilResult,
    markdown_report: str,
) -> tuple[str, Path, Path]:
    _ensure_paths()
    evaluation_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    redacted_request, redaction_summary = _redact_request(request)

    archive = {
        "evaluation_id": evaluation_id,
        "timestamp": timestamp,
        "version": request.version.model_dump(),
        "request": redacted_request,
        "experts": [e.model_dump() for e in experts],
        "council": council.model_dump(),
        "redaction_summary": redaction_summary,
    }
    archive_path = REPORT_DIR / f"{evaluation_id}.json"
    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = REPORT_DIR / f"{evaluation_id}.md"
    report_path.write_text(markdown_report, encoding="utf-8")

    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "evaluation_id": evaluation_id,
                    "timestamp": timestamp,
                    "decision": council.decision,
                    "score": council.council_score,
                    "decision_rule_version": council.decision_rule_version,
                    "version": request.version.model_dump(),
                    "redaction_summary": redaction_summary,
                    "report_path": str(report_path),
                    "archive_path": str(archive_path),
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    return evaluation_id, report_path, archive_path
