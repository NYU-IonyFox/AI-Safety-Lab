# DEPRECATED: This file is scheduled for removal in Phase 5.
# Do not modify. Kept for reference only.
from __future__ import annotations

from dataclasses import dataclass

from app.schemas import DeliberationExchange, EvaluationRequest, ExpertVerdict, RepositorySummary


@dataclass(slots=True)
class DeliberationResult:
    revised_verdicts: list[ExpertVerdict]
    trace: list[DeliberationExchange]


def run_deliberation(request: EvaluationRequest, verdicts: list[ExpertVerdict]) -> DeliberationResult:
    """Run an initial -> critique -> defense/revision loop before final council synthesis."""
    repo = request.repository_summary
    trace = [
        DeliberationExchange(
            phase="initial",
            author_expert=verdict.expert_name,
            summary=f"Initial position: {verdict.summary}",
            evidence_refs=_initial_refs(verdict, repo),
        )
        for verdict in verdicts
    ]

    critiques_by_target: dict[str, list[DeliberationExchange]] = {verdict.expert_name: [] for verdict in verdicts}
    for author in verdicts:
        for target in verdicts:
            if author.expert_name == target.expert_name:
                continue
            critique = _build_critique(author, target, repo)
            if critique is None:
                continue
            critiques_by_target[target.expert_name].append(critique)
            trace.append(critique)

    revised_verdicts: list[ExpertVerdict] = []
    for verdict in verdicts:
        revised_verdicts.append(_revise_verdict(verdict, critiques_by_target[verdict.expert_name], trace))

    return DeliberationResult(revised_verdicts=revised_verdicts, trace=trace)


def _build_critique(
    author: ExpertVerdict,
    target: ExpertVerdict,
    repository_summary: RepositorySummary | None,
) -> DeliberationExchange | None:
    """Generate one targeted peer critique when the author's lens finds a missing concern."""
    if repository_summary is None:
        return None

    target_text = " ".join([target.summary, *target.findings]).lower()
    severity_gap = author.risk_score - target.risk_score
    upload_path = _upload_anchor(repository_summary)
    backend_label = _backend_anchor(repository_summary)
    secret_label = _secret_anchor(repository_summary)

    if author.expert_name == "team1_policy_expert":
        missing: list[str] = []
        if "no_explicit_auth" in repository_summary.auth_signals and _lacks(target_text, ["auth", "access control", "authorization"]):
            missing.append(f"visible access-control obligations around `{upload_path}`")
        if repository_summary.llm_backends and _lacks(target_text, ["third-party", "external model", "accountability", "processor"]):
            missing.append(f"third-party model governance for {backend_label}")
        if repository_summary.upload_surfaces and _lacks(target_text, ["upload", "intake", "retention", "moderation"]):
            missing.append(f"documented intake controls for `{upload_path}`")
        if missing:
            return DeliberationExchange(
                phase="critique",
                author_expert=author.expert_name,
                target_expert=target.expert_name,
                summary=f"Policy critique: {target.expert_name} underweighted {', '.join(missing)} in a repository with public intake and governance exposure.",
                evidence_refs=_refs_for_categories(repository_summary, ["auth", "backend", "upload"]),
            )
        if severity_gap >= 0.18:
            return DeliberationExchange(
                phase="critique",
                author_expert=author.expert_name,
                target_expert=target.expert_name,
                summary=f"Policy critique: {target.expert_name} is materially less severe than the governance evidence warrants.",
                evidence_refs=_refs_for_categories(repository_summary, ["auth", "backend", "upload"]),
            )
        return None

    if author.expert_name == "team2_redteam_expert":
        missing = []
        if repository_summary.upload_surfaces and _lacks(target_text, ["malicious file", "hostile file", "payload chain", "prompt-injection"]):
            missing.append(f"hostile file ingestion risk on `{upload_path}`")
        if repository_summary.llm_backends and _lacks(target_text, ["prompt", "jailbreak", "misuse", "abuse"]):
            missing.append(f"prompt-injection or misuse pathways into {backend_label}")
        if "no_explicit_auth" in repository_summary.auth_signals and _lacks(target_text, ["unauthenticated", "abuse", "misuse", "rate"]):
            missing.append(f"automated unauthenticated abuse risk on `{upload_path}`")
        if missing:
            return DeliberationExchange(
                phase="critique",
                author_expert=author.expert_name,
                target_expert=target.expert_name,
                summary=f"Red-team critique: {target.expert_name} did not fully account for {', '.join(missing)}.",
                evidence_refs=_refs_for_categories(repository_summary, ["upload", "request", "backend", "auth"]),
            )
        if severity_gap >= 0.18:
            return DeliberationExchange(
                phase="critique",
                author_expert=author.expert_name,
                target_expert=target.expert_name,
                summary=f"Red-team critique: exploitability indicators justify a higher severity than {target.expert_name} assigned.",
                evidence_refs=_refs_for_categories(repository_summary, ["upload", "request", "backend", "auth"]),
            )
        return None

    if author.expert_name == "team3_risk_expert":
        missing = []
        if repository_summary.upload_surfaces and repository_summary.llm_backends and _lacks(target_text, ["system", "deployment", "boundary", "pipeline"]):
            missing.append(f"system-boundary exposure from `{upload_path}` into {backend_label}")
        if any(signal.startswith("default_secret_key") for signal in repository_summary.secret_signals) and _lacks(target_text, ["secret", "session", "deployment hardening"]):
            missing.append(f"deployment hardening weakness tied to {secret_label}")
        if repository_summary.media_modalities and _lacks(target_text, ["media", "conversion", "transcription", "runtime", "pipeline"]):
            missing.append("runtime handling of multimedia conversion and transcription steps")
        if missing:
            return DeliberationExchange(
                phase="critique",
                author_expert=author.expert_name,
                target_expert=target.expert_name,
                summary=f"System-risk critique: {target.expert_name} should more clearly reflect {', '.join(missing)}.",
                evidence_refs=_refs_for_categories(repository_summary, ["upload", "secret", "media", "backend"]),
            )
        if severity_gap >= 0.18:
            return DeliberationExchange(
                phase="critique",
                author_expert=author.expert_name,
                target_expert=target.expert_name,
                summary=f"System-risk critique: the architecture and deployment boundary justify a higher severity than {target.expert_name} assigned.",
                evidence_refs=_refs_for_categories(repository_summary, ["upload", "secret", "media", "backend"]),
            )
        return None

    return None


def _revise_verdict(
    verdict: ExpertVerdict,
    critiques: list[DeliberationExchange],
    trace: list[DeliberationExchange],
) -> ExpertVerdict:
    """Revise a verdict only when critiques introduce a concern not already covered."""
    if not critiques:
        return verdict

    current_text = " ".join([verdict.summary, *verdict.findings]).lower()
    novel_critiques = [critique for critique in critiques if _introduces_new_concern(critique.summary, current_text)]
    if not novel_critiques:
        trace.append(
            DeliberationExchange(
                phase="defense",
                author_expert=verdict.expert_name,
                summary=f"{verdict.expert_name} stood by the original assessment because peer critiques were already covered in its findings.",
                evidence_refs=_flatten_refs(critiques),
            )
        )
        return verdict

    severity_gap = max(0.0, max((critique.risk_delta for critique in critiques), default=0.0))
    novelty_weight = 0.02 + 0.015 * len(novel_critiques)
    content_weight = 0.0
    joined = " ".join(critique.summary.lower() for critique in novel_critiques)
    if any(token in joined for token in ["system-boundary", "deployment", "hardening"]):
        content_weight += 0.01
    if any(token in joined for token in ["prompt-injection", "hostile file", "misuse", "payload"]):
        content_weight += 0.015
    if any(token in joined for token in ["access-control", "governance", "third-party model"]):
        content_weight += 0.008
    risk_delta = min(0.09, round(novelty_weight + content_weight + severity_gap, 3))
    revised_risk = min(0.98, verdict.risk_score + risk_delta)
    revised_confidence = min(0.95, verdict.confidence + 0.02 * len(critiques))
    new_findings = list(verdict.findings)
    for critique in novel_critiques:
        new_findings.append(f"Deliberation revision: {critique.summary}")

    trace.append(
        DeliberationExchange(
            phase="defense",
            author_expert=verdict.expert_name,
            summary=f"{verdict.expert_name} accepted {len(novel_critiques)} peer critique(s) and expanded the evidence base before final synthesis.",
            evidence_refs=_flatten_refs(novel_critiques),
        )
    )
    trace.append(
        DeliberationExchange(
            phase="revision",
            author_expert=verdict.expert_name,
            summary=f"{verdict.expert_name} revised risk from {verdict.risk_score:.2f} to {revised_risk:.2f} after deliberation.",
            risk_delta=round(revised_risk - verdict.risk_score, 3),
            evidence_refs=_flatten_refs(novel_critiques),
        )
    )

    detail_payload = verdict.detail_payload.model_copy(
        update={
            "notes": [*verdict.detail_payload.notes, f"Deliberation accepted {len(novel_critiques)} peer critique(s)."],
        }
    )
    evidence = dict(verdict.evidence)
    evidence["deliberation"] = {
        "received_from": [critique.author_expert for critique in critiques],
        "accepted_from": [critique.author_expert for critique in novel_critiques],
        "risk_delta": round(revised_risk - verdict.risk_score, 3),
    }
    summary = verdict.summary
    if "peer critique reinforced" not in summary.lower():
        summary = f"{summary.rstrip('.')}. Peer critique reinforced this assessment."
    return verdict.model_copy(
        update={
            "risk_score": revised_risk,
            "confidence": revised_confidence,
            "risk_tier": _coerce_risk_tier(verdict, revised_risk),
            "summary": summary,
            "findings": new_findings,
            "detail_payload": detail_payload,
            "evidence": evidence,
        }
    )


def _introduces_new_concern(summary: str, current_text: str) -> bool:
    tokens = [
        "access-control",
        "governance",
        "upload",
        "prompt",
        "misuse",
        "system-boundary",
        "deployment",
        "hardening",
        "media",
        "runtime",
        "hostile file",
        "payload",
        "unauthenticated",
        "third-party model",
    ]
    lowered = summary.lower()
    return any(token in lowered and token not in current_text for token in tokens)


def _lacks(text: str, keywords: list[str]) -> bool:
    return not any(keyword in text for keyword in keywords)


def _default_refs(repository_summary: RepositorySummary | None) -> list[str]:
    if repository_summary is None:
        return []
    return [item.path for item in repository_summary.evidence_items[:3]]


def _initial_refs(verdict: ExpertVerdict, repository_summary: RepositorySummary | None) -> list[str]:
    if verdict.expert_name == "team1_policy_expert":
        return _refs_for_categories(repository_summary, ["auth", "backend", "upload"])
    if verdict.expert_name == "team2_redteam_expert":
        return _refs_for_categories(repository_summary, ["upload", "request", "backend", "auth"])
    if verdict.expert_name == "team3_risk_expert":
        return _refs_for_categories(repository_summary, ["upload", "secret", "media", "backend"])
    return _default_refs(repository_summary)


def _refs_for_categories(repository_summary: RepositorySummary | None, categories: list[str], *, limit: int = 3) -> list[str]:
    if repository_summary is None:
        return []

    keyword_map = {
        "upload": ["upload route detected", "upload", "hostile file", "malicious file"],
        "request": ["uploaded files are read", "request.files", "payload"],
        "auth": ["authentication", "authorization", "access control", "no explicit authentication"],
        "backend": ["gpt-4o", "whisper", "openai", "claude", "external model", "model usage", "transcription"],
        "secret": ["secret-key", "secret key", "dev-key", "model identifier", "fine-tuned model"],
        "media": ["media", "transcription", "audio", "video", "ffmpeg", "moviepy", "whisper"],
    }

    refs: list[str] = []
    for category in categories:
        keywords = keyword_map.get(category, [])
        if not keywords:
            continue
        refs.extend(_match_refs(repository_summary, keywords))

    refs.extend(_default_refs(repository_summary))
    return list(dict.fromkeys(refs))[:limit]


def _match_refs(repository_summary: RepositorySummary, keywords: list[str]) -> list[str]:
    refs: list[str] = []
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for item in repository_summary.evidence_items:
        haystack = f"{item.path} {item.signal} {item.why_it_matters}".lower()
        if any(keyword in haystack for keyword in lowered_keywords):
            refs.append(item.path)
    return refs


def _upload_anchor(repository_summary: RepositorySummary | None) -> str:
    if repository_summary is None:
        return "the intake workflow"
    for path in repository_summary.entrypoints:
        if "upload" in path.lower():
            return path
    return repository_summary.entrypoints[0] if repository_summary.entrypoints else "the intake workflow"


def _backend_anchor(repository_summary: RepositorySummary | None) -> str:
    if repository_summary is None or not repository_summary.llm_backends:
        return "external AI services"
    return ", ".join(repository_summary.llm_backends[:3])


def _secret_anchor(repository_summary: RepositorySummary | None) -> str:
    if repository_summary is None or not repository_summary.secret_signals:
        return "secret-key configuration"
    if any(signal.startswith("default_secret_key") for signal in repository_summary.secret_signals):
        return "the default secret-key fallback"
    return repository_summary.secret_signals[0]


def _flatten_refs(critiques: list[DeliberationExchange]) -> list[str]:
    refs: list[str] = []
    for critique in critiques:
        refs.extend(critique.evidence_refs)
    return list(dict.fromkeys(refs))


def _coerce_risk_tier(verdict: ExpertVerdict, risk_score: float) -> str:
    if verdict.risk_tier.startswith("TIER_"):
        if risk_score >= 0.85:
            return "TIER_4"
        if risk_score >= 0.65:
            return "TIER_3"
        if risk_score >= 0.4:
            return "TIER_2"
        return "TIER_1"
    if risk_score >= 0.75:
        return "HIGH"
    if risk_score >= 0.45:
        return "LIMITED"
    return "MINIMAL"
