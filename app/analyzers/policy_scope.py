from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.schemas import RepositoryEvidence, RepositorySummary


TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".html", ".js", ".ts", ".tsx", ".yml", ".yaml", ".toml", ".env", ".example"}
MAX_READ_BYTES = 200_000
MAX_FILES = 120


@dataclass(slots=True)
class PolicyScopeAnalysis:
    scan_mode: str = "none"
    scanned_file_count: int = 0
    governance_controls: list[str] = field(default_factory=list)
    policy_gaps: list[str] = field(default_factory=list)
    processor_mentions: list[str] = field(default_factory=list)
    evidence_items: list[RepositoryEvidence] = field(default_factory=list)


def analyze_policy_scope(repo_path: str, repository_summary: RepositorySummary | None) -> PolicyScopeAnalysis:
    root = Path(repo_path).resolve()
    if not root.exists():
        return PolicyScopeAnalysis()

    files = [p for p in root.rglob("*") if p.is_file()]
    text_files = [p for p in files if p.suffix.lower() in TEXT_SUFFIXES][:MAX_FILES]
    blobs = {str(path.relative_to(root)): _safe_read(path) for path in text_files}
    combined = "\n".join(blobs.values()).lower()

    controls: list[str] = []
    if any(token in combined for token in ["privacy policy", "data retention", "retention policy", "delete after processing"]):
        controls.append("Repository contains privacy or retention language.")
    if any(token in combined for token in ["audit", "audit_log", "logging", "structured logging", "access log"]):
        controls.append("Repository mentions audit or logging controls.")
    if any(token in combined for token in ["rate limit", "limiter", "throttle"]):
        controls.append("Repository mentions rate-limiting or abuse throttling.")
    if any(token in combined for token in ["human review", "manual review", "escalate", "moderation queue"]):
        controls.append("Repository mentions human review or escalation.")
    if any(token in combined for token in ["terms of service", "acceptable use", "content policy"]):
        controls.append("Repository documents acceptable-use or moderation expectations.")

    processor_mentions = [
        label
        for label, tokens in {
            "OpenAI API": ["from openai import", "openai_api_key", "client.chat.completions.create"],
            "Whisper API": ["audio.transcriptions", "whisper"],
            "Anthropic": ["anthropic", "claude"],
        }.items()
        if any(token in combined for token in tokens)
    ]

    gaps: list[str] = []
    repo = repository_summary
    if repo is not None:
        if repo.upload_surfaces and "no_explicit_auth" in repo.auth_signals:
            gaps.append("Upload and analysis flow appears reachable without visible access-control enforcement.")
        if repo.llm_backends and not any("privacy" in control.lower() or "retention" in control.lower() for control in controls):
            gaps.append("External AI processors are in scope, but privacy and retention controls are not clearly documented.")
        if repo.upload_surfaces and not any("acceptable-use" in control.lower() or "moderation" in control.lower() for control in controls):
            gaps.append("User-generated media intake is present, but moderation or acceptable-use controls are not clearly documented.")
        if repo.llm_backends and not any("audit" in control.lower() or "logging" in control.lower() for control in controls):
            gaps.append("Third-party AI processing is present, but audit/logging controls are not clearly surfaced.")
        if not any("human review" in control.lower() or "escalation" in control.lower() for control in controls):
            gaps.append("Human-review or escalation language is not clearly surfaced for high-risk outputs.")

    evidence: list[RepositoryEvidence] = []
    evidence.extend(_collect_evidence(blobs, "Privacy or retention language detected", "Evidence of privacy-aware data handling or retention controls.", ["privacy policy", "data retention", "delete after processing"]))
    evidence.extend(_collect_evidence(blobs, "Audit or logging language detected", "Auditability claims are stronger when logging controls are explicitly documented.", ["audit_log", "structured logging", "access log", "logging"]))
    evidence.extend(_collect_evidence(blobs, "Human-review or escalation language detected", "Human oversight language supports accountable governance and escalation posture.", ["human review", "manual review", "escalate", "moderation queue"]))
    evidence.extend(_collect_evidence(blobs, "Acceptable-use or moderation policy language detected", "Content intake controls are more credible when moderation expectations are documented.", ["acceptable use", "terms of service", "content policy", "moderation"]))

    if repo is not None and "no_explicit_auth" in repo.auth_signals:
        match = _find_first_match(blobs, ["@app.route(", "router.", "request.files"])
        path = "repository-wide scan"
        if match is not None:
            path = f"{match[0]}:{match[1]}"
        evidence.append(
            RepositoryEvidence(
                path=path,
                signal="No explicit policy-facing access-control documentation detected",
                why_it_matters="Governance posture is weaker when public intake exists without clear authentication or authorization evidence.",
            )
        )

    return PolicyScopeAnalysis(
        scan_mode="local_scan",
        scanned_file_count=len(text_files),
        governance_controls=controls[:5],
        policy_gaps=gaps[:5],
        processor_mentions=processor_mentions[:3],
        evidence_items=_dedupe_evidence(evidence)[:6],
    )


def _safe_read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _collect_evidence(blobs: dict[str, str], signal: str, why_it_matters: str, tokens: list[str]) -> list[RepositoryEvidence]:
    match = _find_first_match(blobs, tokens)
    if match is None:
        return []
    path, line_number = match
    return [RepositoryEvidence(path=f"{path}:{line_number}", signal=signal, why_it_matters=why_it_matters)]


def _find_first_match(blobs: dict[str, str], tokens: list[str]) -> tuple[str, int] | None:
    lowered_tokens = [token.lower() for token in tokens]
    for name, blob in blobs.items():
        for index, line in enumerate(blob.splitlines(), start=1):
            lowered_line = line.lower()
            if any(token in lowered_line for token in lowered_tokens):
                return name, index
    return None


def _dedupe_evidence(items: list[RepositoryEvidence]) -> list[RepositoryEvidence]:
    deduped: list[RepositoryEvidence] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.path, item.signal)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
