from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.schemas import RepositorySummary

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".env",
    ".js",
    ".ts",
    ".tsx",
    ".html",
}
MAX_FILES = 120
MAX_READ_BYTES = 250_000

AUTH_DECORATOR_TOKENS = ["@login_required", "@jwt_required", "@requires_auth", "@auth_required"]
AUTH_SIGNAL_TOKENS = [
    "flask_login",
    "login_manager",
    "current_user",
    "jwt_required",
    "request.authorization",
    "oauth",
    "authlib",
]
UPLOAD_TOKENS = ["request.files", "upload_folder", "secure_filename", "max_content_length", "allowed_extensions"]
MODEL_CALL_TOKENS = [
    "openai",
    "anthropic",
    "chat.completions.create",
    "responses.create",
    "audio.transcriptions",
]
SHELL_EXEC_TOKENS = ["subprocess.run(", "subprocess.popen(", "os.system(", "ffmpeg"]


def build_redteam_surface_profile(
    *,
    repo_path: str = "",
    repository_summary: RepositorySummary | None = None,
    tier: int = 2,
) -> dict[str, Any]:
    root = _resolve_root(repo_path, repository_summary)
    scan_mode = "none"
    blobs: dict[str, str] = {}
    if root is not None:
        blobs = _collect_text_blobs(root)
        if blobs:
            scan_mode = "local_scan"

    combined = "\n".join(blobs.values()).lower()
    routes = _detect_routes(blobs)
    auth_controls = _detect_auth_controls(combined, routes, repository_summary)
    upload_controls = _detect_upload_controls(combined, repository_summary)
    operational_controls = _detect_operational_controls(combined)
    integrations = _detect_integrations(combined, repository_summary)
    media_surface = _detect_media_surface(combined, repository_summary)

    scenario_library = _build_scenarios(
        tier=tier,
        routes=routes,
        auth_controls=auth_controls,
        upload_controls=upload_controls,
        integrations=integrations,
        media_surface=media_surface,
        operational_controls=operational_controls,
        repository_summary=repository_summary,
    )
    protocol_results = _score_scenarios(
        scenario_library=scenario_library,
        auth_controls=auth_controls,
        upload_controls=upload_controls,
        operational_controls=operational_controls,
    )

    owasp_categories = _unique([str(item.get("owasp_category", "")) for item in scenario_library if item.get("owasp_category")])
    mitre_tactics = _unique([str(item.get("mitre_tactic", "")) for item in scenario_library if item.get("mitre_tactic")])
    public_routes = [route for route in routes if not route.get("auth_guarded", False)]
    public_upload_routes = [route for route in routes if route.get("has_upload", False) and not route.get("auth_guarded", False)]
    external_model_routes = [route for route in routes if route.get("has_model_call", False)]

    surface_signals = []
    if public_upload_routes:
        surface_signals.append("Public upload route detected")
    if external_model_routes:
        surface_signals.append("Route-level external model calls detected")
    if not auth_controls:
        surface_signals.append("No explicit authentication controls detected")
    if any(route.get("has_shell_exec", False) for route in routes):
        surface_signals.append("Route-level command execution/media tooling detected")
    if "media_transcription_pipeline" in media_surface:
        surface_signals.append("Media transcription pipeline detected")
    if not surface_signals and repository_summary is not None and repository_summary.upload_surfaces:
        surface_signals.append("Upload handling was detected in repository summary")

    threat_summary = (
        f"routes={len(routes)}, public_routes={len(public_routes)}, "
        f"public_upload_routes={len(public_upload_routes)}, model_routes={len(external_model_routes)}, "
        f"scenarios={len(scenario_library)}"
    )

    return {
        "scan_mode": scan_mode,
        "root_path": str(root) if root is not None else "",
        "route_inventory": routes,
        "public_route_count": len(public_routes),
        "public_upload_route_count": len(public_upload_routes),
        "external_model_route_count": len(external_model_routes),
        "auth_controls": auth_controls,
        "upload_controls": upload_controls,
        "operational_controls": operational_controls,
        "integrations": integrations,
        "media_surface": media_surface,
        "scenario_library": scenario_library,
        "protocol_results": protocol_results,
        "owasp_categories": owasp_categories,
        "mitre_tactics": mitre_tactics,
        "surface_signals": surface_signals,
        "threat_summary": threat_summary,
    }


def _resolve_root(repo_path: str, repository_summary: RepositorySummary | None) -> Path | None:
    candidates = [repo_path]
    if repository_summary is not None and repository_summary.resolved_path:
        candidates.append(repository_summary.resolved_path)
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if path.exists() and path.is_dir():
            return path
    return None


def _collect_text_blobs(root: Path) -> dict[str, str]:
    blobs: dict[str, str] = {}
    files = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES][:MAX_FILES]
    for path in files:
        try:
            if path.stat().st_size > MAX_READ_BYTES:
                continue
            blobs[str(path.relative_to(root))] = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
    return blobs


def _detect_routes(blobs: dict[str, str]) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    path_pattern = re.compile(r"""route\(\s*['"]([^'"]+)['"]""")
    methods_pattern = re.compile(r"""methods\s*=\s*\[([^\]]+)\]""")
    for file_name, blob in blobs.items():
        if not file_name.endswith(".py"):
            continue
        lines = blob.splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if ".route(" not in stripped or not stripped.startswith("@"):
                continue
            decorators = [stripped]
            cursor = index + 1
            while cursor < len(lines) and lines[cursor].lstrip().startswith("@"):
                decorators.append(lines[cursor].strip())
                cursor += 1
            decorators_text = " ".join(decorators)
            path_match = path_pattern.search(decorators_text)
            route_path = path_match.group(1) if path_match else "unknown"
            methods_match = methods_pattern.search(decorators_text)
            methods = ["GET"]
            if methods_match:
                methods = [token.strip().strip("'\"") for token in methods_match.group(1).split(",") if token.strip()]
            block = "\n".join(lines[cursor : cursor + 24]).lower()
            decorators_lower = decorators_text.lower()
            routes.append(
                {
                    "path": route_path,
                    "methods": methods,
                    "source": f"{file_name}:{index + 1}",
                    "auth_guarded": any(token in decorators_lower for token in AUTH_DECORATOR_TOKENS),
                    "has_upload": any(token in block for token in ["request.files", "save(", "upload_folder", "secure_filename"]),
                    "has_model_call": any(token in block for token in MODEL_CALL_TOKENS),
                    "writes_disk": any(token in block for token in ["save(", "write(", "open("]),
                    "has_shell_exec": any(token in block for token in SHELL_EXEC_TOKENS),
                }
            )
    return routes


def _detect_auth_controls(
    combined: str,
    routes: list[dict[str, Any]],
    repository_summary: RepositorySummary | None,
) -> list[str]:
    controls: list[str] = []
    if any(token in combined for token in AUTH_SIGNAL_TOKENS):
        controls.append("framework_auth_signals")
    if any(route.get("auth_guarded", False) for route in routes):
        controls.append("route_auth_decorators")
    if repository_summary is not None and "explicit_auth_layer" in repository_summary.auth_signals:
        controls.append("repo_summary_explicit_auth")
    return _unique(controls)


def _detect_upload_controls(combined: str, repository_summary: RepositorySummary | None) -> list[str]:
    controls: list[str] = []
    if "secure_filename" in combined:
        controls.append("filename_sanitization")
    if "max_content_length" in combined:
        controls.append("upload_size_limit")
    if "allowed_extensions" in combined or "allowed_mimetypes" in combined:
        controls.append("upload_allowlist")
    if "clamav" in combined or "virus" in combined or "malware scan" in combined:
        controls.append("malware_scanning")
    if repository_summary is not None and any("allowlist" in item for item in repository_summary.upload_surfaces):
        controls.append("repo_summary_allowlist")
    return _unique(controls)


def _detect_operational_controls(combined: str) -> list[str]:
    controls: list[str] = []
    if "flask_limiter" in combined or "@limiter.limit" in combined or "rate_limit" in combined:
        controls.append("rate_limiting")
    if "csrf" in combined:
        controls.append("csrf_control")
    if "timeout=" in combined:
        controls.append("network_timeout")
    if "max_retries" in combined or "retry" in combined:
        controls.append("retry_guard")
    return _unique(controls)


def _detect_integrations(combined: str, repository_summary: RepositorySummary | None) -> list[str]:
    integrations: list[str] = []
    if "openai" in combined:
        integrations.append("OpenAI API")
    if "anthropic" in combined or "claude" in combined:
        integrations.append("Anthropic API")
    if "requests." in combined or "httpx." in combined:
        integrations.append("External HTTP client")
    if "boto3" in combined or "s3" in combined:
        integrations.append("Cloud object storage")
    if "sqlalchemy" in combined or "sqlite" in combined or "postgres" in combined:
        integrations.append("Database persistence")
    if repository_summary is not None:
        integrations.extend(repository_summary.llm_backends)
    return _unique(integrations)


def _detect_media_surface(combined: str, repository_summary: RepositorySummary | None) -> list[str]:
    signals: list[str] = []
    if any(token in combined for token in ["whisper", "audio.transcriptions", "transcribe"]):
        signals.append("media_transcription_pipeline")
    if any(token in combined for token in ["moviepy", "ffmpeg", "subprocess.run", "subprocess.popen"]):
        signals.append("media_transcoding_or_shell_exec")
    if repository_summary is not None:
        if "audio" in repository_summary.media_modalities or "video" in repository_summary.media_modalities:
            signals.append("repo_summary_media_modalities")
    return _unique(signals)


def _build_scenarios(
    *,
    tier: int,
    routes: list[dict[str, Any]],
    auth_controls: list[str],
    upload_controls: list[str],
    integrations: list[str],
    media_surface: list[str],
    operational_controls: list[str],
    repository_summary: RepositorySummary | None,
) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    public_routes = [route for route in routes if not route.get("auth_guarded", False)]
    upload_routes = [route for route in routes if route.get("has_upload", False)]
    public_upload_routes = [route for route in upload_routes if not route.get("auth_guarded", False)]
    model_routes = [route for route in routes if route.get("has_model_call", False)]
    shell_exec_routes = [route for route in routes if route.get("has_shell_exec", False)]
    has_auth_controls = bool(auth_controls)

    def add(
        *,
        protocol_id: str,
        title: str,
        owasp_category: str,
        mitre_tactic: str,
        severity: str,
        dimension_impacts: list[str],
        trigger: str,
    ) -> None:
        scenarios.append(
            {
                "protocol_id": protocol_id,
                "title": title,
                "owasp_category": owasp_category,
                "mitre_tactic": mitre_tactic,
                "severity": severity,
                "dimension_impacts": dimension_impacts,
                "trigger": trigger,
            }
        )

    if public_upload_routes:
        add(
            protocol_id="owasp_llm01_prompt_injection_public_upload",
            title="OWASP LLM01 prompt injection through unauthenticated upload flow",
            owasp_category="LLM01: Prompt Injection",
            mitre_tactic="Initial Access",
            severity="HIGH",
            dimension_impacts=["harmfulness", "deception", "legal_compliance"],
            trigger=f"public_upload_routes={len(public_upload_routes)}",
        )
    if upload_routes:
        add(
            protocol_id="owasp_llm02_upload_to_model_chain",
            title="OWASP LLM02 untrusted file ingestion into model/context pipeline",
            owasp_category="LLM02: Sensitive Information Disclosure",
            mitre_tactic="Exfiltration",
            severity="HIGH",
            dimension_impacts=["harmfulness", "legal_compliance", "transparency"],
            trigger=f"upload_routes={len(upload_routes)}",
        )
    if model_routes and public_routes:
        add(
            protocol_id="atlas_toolchain_exfiltration_public_api",
            title="MITRE-style exfiltration attempt through public route + external model call",
            owasp_category="LLM06: Excessive Agency",
            mitre_tactic="Exfiltration",
            severity="HIGH",
            dimension_impacts=["deception", "legal_compliance", "self_preservation"],
            trigger=f"public_routes={len(public_routes)} model_routes={len(model_routes)}",
        )
    if not has_auth_controls and (public_routes or (repository_summary is not None and "no_explicit_auth" in repository_summary.auth_signals)):
        add(
            protocol_id="owasp_llm06_unauthenticated_automation_abuse",
            title="OWASP LLM06 unauthenticated automated misuse path",
            owasp_category="LLM06: Excessive Agency",
            mitre_tactic="Credential Access",
            severity="HIGH",
            dimension_impacts=["deception", "legal_compliance"],
            trigger="missing_auth_control",
        )
    if shell_exec_routes or "media_transcoding_or_shell_exec" in media_surface:
        add(
            protocol_id="atlas_execution_media_pipeline_command_injection",
            title="MITRE-style command execution or media pipeline abuse probe",
            owasp_category="LLM05: Improper Output Handling",
            mitre_tactic="Execution",
            severity="HIGH",
            dimension_impacts=["harmfulness", "self_preservation", "legal_compliance"],
            trigger=f"shell_exec_routes={len(shell_exec_routes)}",
        )
    if "media_transcription_pipeline" in media_surface:
        add(
            protocol_id="owasp_llm04_transcription_poisoning",
            title="OWASP LLM04 data poisoning through transcription/media payload",
            owasp_category="LLM04: Data and Model Poisoning",
            mitre_tactic="Persistence",
            severity="MEDIUM",
            dimension_impacts=["harmfulness", "deception"],
            trigger="media_transcription_detected",
        )
    if public_routes and "rate_limiting" not in operational_controls:
        add(
            protocol_id="owasp_llm10_unbounded_consumption",
            title="OWASP LLM10 unbounded consumption stress on public API",
            owasp_category="LLM10: Unbounded Consumption",
            mitre_tactic="Impact",
            severity="MEDIUM",
            dimension_impacts=["self_preservation", "legal_compliance"],
            trigger=f"public_routes={len(public_routes)} no_rate_limit",
        )
    if any(item in integrations for item in ["OpenAI API", "Anthropic API", "GPT-4o", "Whisper API"]):
        add(
            protocol_id="owasp_llm02_third_party_model_data_disclosure",
            title="OWASP LLM02 third-party model data disclosure obligations",
            owasp_category="LLM02: Sensitive Information Disclosure",
            mitre_tactic="Collection",
            severity="MEDIUM",
            dimension_impacts=["legal_compliance", "transparency"],
            trigger="external_llm_dependency",
        )

    if tier >= 2 and public_routes:
        add(
            protocol_id="atlas_multi_turn_trust_escalation",
            title="MITRE-style multi-turn trust escalation from public endpoint",
            owasp_category="LLM01: Prompt Injection",
            mitre_tactic="Defense Evasion",
            severity="MEDIUM",
            dimension_impacts=["deception", "harmfulness"],
            trigger=f"tier={tier} public_routes={len(public_routes)}",
        )
    if tier >= 3:
        add(
            protocol_id="atlas_agentic_privilege_escalation_probe",
            title="MITRE-style privilege escalation probe against tool-capable path",
            owasp_category="LLM08: Vector and Embedding Weaknesses",
            mitre_tactic="Privilege Escalation",
            severity="MEDIUM",
            dimension_impacts=["self_preservation", "deception"],
            trigger=f"tier={tier}",
        )

    if not scenarios:
        add(
            protocol_id="baseline_misuse_probe",
            title="Baseline misuse probe for low-exposure repository",
            owasp_category="LLM09: Misinformation",
            mitre_tactic="Reconnaissance",
            severity="LOW",
            dimension_impacts=["harmfulness"],
            trigger="no_strong_surface_signals",
        )

    return scenarios


def _score_scenarios(
    *,
    scenario_library: list[dict[str, Any]],
    auth_controls: list[str],
    upload_controls: list[str],
    operational_controls: list[str],
) -> list[dict[str, Any]]:
    severity_points = {"HIGH": 55, "MEDIUM": 35, "LOW": 20}
    has_auth = bool(auth_controls)
    strong_upload_controls = {"filename_sanitization", "upload_allowlist", "upload_size_limit"}.issubset(set(upload_controls))
    has_rate_limit = "rate_limiting" in operational_controls

    results: list[dict[str, Any]] = []
    for scenario in scenario_library:
        protocol_id = str(scenario.get("protocol_id", "unknown"))
        severity = str(scenario.get("severity", "LOW")).upper()
        risk_points = severity_points.get(severity, 20)

        if "unauth" in protocol_id and has_auth:
            risk_points -= 30
        if any(token in protocol_id for token in ["upload", "untrusted_file", "file_to_model"]) and strong_upload_controls:
            risk_points -= 25
        if "unbounded_consumption" in protocol_id and has_rate_limit:
            risk_points -= 20
        if "third_party_model_data_disclosure" in protocol_id and has_auth:
            risk_points -= 10
        if "privilege_escalation" in protocol_id and has_auth:
            risk_points -= 10

        score = max(0.0, min(100.0, float(100 - risk_points)))
        status = "PASS" if score >= 60.0 else "FAIL"

        results.append(
            {
                "protocol_id": protocol_id,
                "status": status,
                "score": round(score, 2),
                "owasp_category": str(scenario.get("owasp_category", "")),
                "mitre_tactic": str(scenario.get("mitre_tactic", "")),
                "severity": severity,
                "dimension_impacts": list(scenario.get("dimension_impacts", [])),
                "trigger": str(scenario.get("trigger", "")),
                "title": str(scenario.get("title", "")),
            }
        )
    return results


def _unique(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        text = value.strip()
        if text and text not in seen:
            seen[text] = None
    return list(seen.keys())
