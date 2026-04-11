from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.schemas import RepositoryEvidence, RepositorySummary


TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".html", ".js", ".ts", ".tsx", ".yml", ".yaml", ".toml", ".env", ".example"}
MAX_READ_BYTES = 200_000
MAX_FILES = 120


@dataclass(slots=True)
class SystemScopeAnalysis:
    exposure_findings: list[str] = field(default_factory=list)
    control_findings: list[str] = field(default_factory=list)
    evidence_items: list[RepositoryEvidence] = field(default_factory=list)


def analyze_system_scope(repo_path: str, repository_summary: RepositorySummary | None) -> SystemScopeAnalysis:
    root = Path(repo_path).resolve()
    if not root.exists():
        return SystemScopeAnalysis()

    files = [p for p in root.rglob("*") if p.is_file()]
    text_files = [p for p in files if p.suffix.lower() in TEXT_SUFFIXES][:MAX_FILES]
    blobs = {str(path.relative_to(root)): _safe_read(path) for path in text_files}
    combined = "\n".join(blobs.values()).lower()

    exposures: list[str] = []
    controls: list[str] = []
    evidence: list[RepositoryEvidence] = []

    if any(token in combined for token in ["subprocess.run", "os.system", "ffmpeg", "moviepy"]):
        exposures.append("Repository invokes local conversion or subprocess tooling that expands the runtime boundary.")
        evidence.extend(_collect_evidence(blobs, "Local conversion or subprocess tooling detected", "Media conversion and shell/process execution increase operational risk and hardening requirements.", ["subprocess.run", "os.system", "ffmpeg", "moviepy"]))
    if any(token in combined for token in ["openai", "anthropic", "httpx.post", "requests.post", "client.chat.completions.create"]):
        exposures.append("Repository makes external model or HTTP calls as part of the analysis pipeline.")
        evidence.extend(_collect_evidence(blobs, "External model or HTTP dependency detected", "External AI or HTTP calls widen the trust boundary and require stricter deployment controls.", ["from openai import", "anthropic", "httpx.post", "requests.post", "client.chat.completions.create"]))
    if any(token in combined for token in ["tmp", "tempfile", "upload_folder", "uploads/"]):
        exposures.append("Repository stages uploaded or derived artifacts on disk, which increases containment and cleanup requirements.")
        evidence.extend(_collect_evidence(blobs, "Upload or temp-file staging detected", "Persistent handling of untrusted files increases cleanup, scanning, and isolation requirements.", ["upload_folder", "tempfile", "uploads/", "tmp"]))

    if any(token in combined for token in ["secure_filename", "max_content_length", "allowed_extensions", "content-length"]):
        controls.append("Repository includes some intake hardening controls such as filename normalization or upload limits.")
    if any(token in combined for token in ["timeout", "retry", "try:", "except", "graceful"]):
        controls.append("Repository contains basic resilience or error-handling patterns.")
    if any(token in combined for token in ["dotenv", "os.getenv", "environ.get"]):
        controls.append("Repository reads configuration from environment variables rather than hardcoding every operational value.")

    repo = repository_summary
    if repo is not None:
        if repo.upload_surfaces and repo.llm_backends:
            exposures.append("User-controlled media flows into external AI services, creating a multi-stage trust boundary.")
        if "no_explicit_auth" in repo.auth_signals:
            exposures.append("Visible access-control boundaries are weak relative to the repository's public intake surface.")
        if any(signal.startswith("default_secret_key") for signal in repo.secret_signals):
            exposures.append("Default secret fallback indicates deployment hardening is incomplete.")

    return SystemScopeAnalysis(
        exposure_findings=_dedupe(exposures)[:6],
        control_findings=_dedupe(controls)[:4],
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


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


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
