from __future__ import annotations

import re
from pathlib import Path

from app.schemas import RepositoryEvidence, RepositorySummary

TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".html", ".js", ".ts", ".tsx", ".yml", ".yaml", ".toml", ".env", ".example"}
MAX_READ_BYTES = 200_000
MAX_FILES = 80


def summarize_repository(repo_path: str, *, target_name: str, source_type: str, description: str = "") -> RepositorySummary:
    root = Path(repo_path).resolve()
    files = [p for p in root.rglob("*") if p.is_file()]
    text_files = [p for p in files if p.suffix.lower() in TEXT_SUFFIXES][:MAX_FILES]
    blobs = {str(path.relative_to(root)): _safe_read(path) for path in text_files}
    combined = "\n".join(blobs.values()).lower()

    framework = _detect_framework(combined)
    routes = _detect_routes(blobs)
    llm_backends = _detect_llm_backends(combined)
    media_modalities = _detect_media_modalities(combined)
    upload_surfaces = _detect_upload_surfaces(blobs)
    auth_signals = _detect_auth_signals(combined)
    secret_signals = _detect_secret_signals(combined)
    notable_files = _notable_files(blobs)
    dependencies = _detect_dependencies(blobs)

    risk_notes: list[str] = []
    if framework == "Flask":
        risk_notes.append("Flask-based app with server-side request handling.")
    if upload_surfaces:
        risk_notes.append("Accepts user-uploaded files, expanding attack surface for prompt injection and malicious media.")
    if llm_backends:
        risk_notes.append(f"Uses external AI services: {', '.join(llm_backends)}.")
    if "no_explicit_auth" in auth_signals:
        risk_notes.append("No explicit authentication layer detected around core upload and analysis flow.")
    if any(signal.startswith("default_secret_key") for signal in secret_signals):
        risk_notes.append("Default development secret key pattern detected.")
    if any(signal.startswith("ffmpeg") or signal.startswith("moviepy") for signal in secret_signals + dependencies):
        risk_notes.append("Processes large media files through conversion/transcoding tooling.")

    detected_signals = _detected_signals(framework, llm_backends, upload_surfaces, auth_signals, dependencies)
    evidence_items = _build_evidence_items(blobs, auth_signals)
    summary = _build_summary(target_name, framework, llm_backends, media_modalities, upload_surfaces, auth_signals)

    return RepositorySummary(
        target_name=target_name or root.name,
        source_type=source_type,
        resolved_path=str(root),
        description=description,
        framework=framework,
        entrypoints=routes,
        llm_backends=llm_backends,
        media_modalities=media_modalities,
        upload_surfaces=upload_surfaces,
        auth_signals=auth_signals,
        secret_signals=secret_signals,
        dependencies=dependencies,
        notable_files=notable_files,
        risk_notes=risk_notes,
        detected_signals=detected_signals,
        evidence_items=evidence_items,
        file_count=len(files),
        summary=summary,
    )


def _safe_read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _detect_framework(combined: str) -> str:
    if "from flask import" in combined or "flask(__name__)" in combined:
        return "Flask"
    if "from fastapi import" in combined or "fastapi(" in combined:
        return "FastAPI"
    return "Unknown"


def _detect_routes(blobs: dict[str, str]) -> list[str]:
    routes: list[str] = []
    pattern = re.compile(r"@app\.route\(['\"]([^'\"]+)['\"]")
    for name, blob in blobs.items():
        if not name.endswith(".py"):
            continue
        for match in pattern.findall(blob):
            if match not in routes:
                routes.append(match)
    return routes[:12]


def _detect_llm_backends(combined: str) -> list[str]:
    backends: list[str] = []
    for label, tokens in {
        "OpenAI API": ["from openai import", "openai_api_key", "client.chat.completions.create"],
        "GPT-4o": ["gpt-4o"],
        "Whisper API": ["whisper", "audio.transcriptions", "transcribe"],
        "Claude-compatible endpoint": ["anthropic", "claude"],
    }.items():
        if any(token in combined for token in tokens):
            backends.append(label)
    return backends


def _detect_media_modalities(combined: str) -> list[str]:
    modalities: list[str] = []
    if any(token in combined for token in ["text", "txt", "pdf", "docx"]):
        modalities.append("text")
    if any(token in combined for token in ["audio", "mp3", "wav", "ogg", "whisper"]):
        modalities.append("audio")
    if any(token in combined for token in ["video", "mp4", "moviepy", "ffmpeg"]):
        modalities.append("video")
    return modalities


def _detect_upload_surfaces(blobs: dict[str, str]) -> list[str]:
    findings: list[str] = []
    combined = "\n".join(blobs.values()).lower()
    if "request.files" in combined:
        findings.append("request.files upload handling")
    if "secure_filename" in combined:
        findings.append("filename normalization via secure_filename")
    if "upload_folder" in combined:
        findings.append("server-side upload directory")
    if "max_content_length" in combined:
        findings.append("large file upload limit configured")
    if "allowed_extensions" in combined:
        findings.append("extension-based file type allowlist")
    return findings


def _detect_auth_signals(combined: str) -> list[str]:
    signals: list[str] = []
    explicit_auth_patterns = [
        "@login_required",
        "flask_login",
        "login_manager",
        "current_user",
        "jwt_required",
        "@requires_auth",
        "oauth",
        "authlib",
        "request.authorization",
        "session['user'",
        'session["user"',
        "session['user_id'",
        'session["user_id"',
    ]
    if "session" in combined:
        signals.append("session_usage")
    if any(token in combined for token in explicit_auth_patterns):
        signals.append("explicit_auth_layer")
    else:
        signals.append("no_explicit_auth")
    return signals


def _detect_secret_signals(combined: str) -> list[str]:
    signals: list[str] = []
    if "secret_key', 'dev-key-for-development" in combined or 'secret_key", "dev-key-for-development' in combined:
        signals.append("default_secret_key_fallback")
    if "openai_api_key" in combined:
        signals.append("openai_api_key_env")
    if "finetune_model_id.txt" in combined:
        signals.append("fine_tuned_model_file")
    return signals


def _detect_dependencies(blobs: dict[str, str]) -> list[str]:
    deps: list[str] = []
    for name, blob in blobs.items():
        if name.endswith("requirements.txt"):
            for line in blob.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    deps.append(line)
    for extra in ["ffmpeg", "moviepy", "pydub", "PyPDF2", "python-docx"]:
        if extra.lower() in "\n".join(blobs.values()).lower() and extra not in deps:
            deps.append(extra)
    return deps[:20]


def _notable_files(blobs: dict[str, str]) -> list[str]:
    preferred = [name for name in blobs if name in {"README.md", "app.py", "requirements.txt", ".env.example"}]
    return preferred or sorted(list(blobs.keys()))[:8]


def _detected_signals(
    framework: str,
    llm_backends: list[str],
    upload_surfaces: list[str],
    auth_signals: list[str],
    dependencies: list[str],
) -> list[str]:
    signals: list[str] = []
    if framework == "Flask":
        signals.append("Flask architecture detected")
    if "GPT-4o" in llm_backends:
        signals.append("GPT-4o backend usage detected")
    if "Whisper API" in llm_backends or any(dep.lower() == "ffmpeg" for dep in dependencies):
        signals.append("Audio/video transcription pipeline detected")
    if upload_surfaces:
        signals.append("File upload surface detected")
    if "no_explicit_auth" in auth_signals:
        signals.append("Lack of explicit authentication layer detected")
    return signals


def _build_evidence_items(blobs: dict[str, str], auth_signals: list[str]) -> list[RepositoryEvidence]:
    evidence: list[RepositoryEvidence] = []

    def add(signal: str, why_it_matters: str, *tokens: str) -> None:
        match = _find_first_match(blobs, list(tokens))
        if match is None:
            return
        path, line_number = match
        evidence.append(
            RepositoryEvidence(
                path=f"{path}:{line_number}",
                signal=signal,
                why_it_matters=why_it_matters,
            )
        )

    add(
        "Upload route detected",
        "Public upload entry points expand the attack surface for malicious files, prompt injection, and unsafe media handling.",
        "@app.route('/upload'",
        '@app.route("/upload"',
    )
    add(
        "Uploaded files are read from HTTP requests",
        "Reading files directly from requests means the system must defend against hostile content and oversized payloads.",
        "request.files",
    )
    add(
        "Development secret-key fallback detected",
        "Fallback secrets are acceptable in demos but weaken confidence in production-grade session and deployment controls.",
        "dev-key-for-development",
    )
    add(
        "GPT-4o model usage detected",
        "External model calls create third-party processing, prompt-injection, and output-governance obligations.",
        "gpt-4o",
    )
    add(
        "Speech or media transcription detected",
        "Audio and video ingestion broaden the input surface and require stronger validation and abuse monitoring.",
        "audio.transcriptions",
        "whisper",
        "transcribe",
    )

    if "no_explicit_auth" in auth_signals:
        auth_probe = _find_first_match(
            blobs,
            [
                "@app.route(",
                "request.files",
            ],
        )
        path = "repository-wide scan"
        if auth_probe is not None:
            path = f"{auth_probe[0]}:{auth_probe[1]}"
        evidence.append(
            RepositoryEvidence(
                path=path,
                signal="No explicit authentication controls detected in analyzed files",
                why_it_matters="If upload and analysis routes are reachable without visible access control, misuse and automated abuse are easier to operationalize.",
            )
        )

    deduped: list[RepositoryEvidence] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        key = (item.path, item.signal)
        if key in seen:
            continue
        deduped.append(item)
        seen.add(key)
    return deduped[:6]


def _find_first_match(blobs: dict[str, str], tokens: list[str]) -> tuple[str, int] | None:
    for name, blob in blobs.items():
        line_number = _first_line_with(blob, tokens)
        if line_number is not None:
            return name, line_number
    return None


def _first_line_with(blob: str, tokens: list[str]) -> int | None:
    lowered_tokens = [token.lower() for token in tokens]
    for index, line in enumerate(blob.splitlines(), start=1):
        lowered_line = line.lower()
        if any(token in lowered_line for token in lowered_tokens):
            return index
    return None


def _build_summary(target_name: str, framework: str, llm_backends: list[str], media_modalities: list[str], upload_surfaces: list[str], auth_signals: list[str]) -> str:
    parts = [f"{target_name} is a {framework} repository"]
    if media_modalities:
        parts.append(f"handling {', '.join(media_modalities)} content")
    if llm_backends:
        parts.append(f"with AI backends {', '.join(llm_backends)}")
    if upload_surfaces:
        parts.append("and user-upload entry points")
    if "no_explicit_auth" in auth_signals:
        parts.append("without a clearly detected authentication layer")
    return " ".join(parts) + "."
