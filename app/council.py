from statistics import pstdev

from app.config import (
    COUNCIL_BLOCK_THRESHOLD,
    COUNCIL_DECISION_RULE_VERSION,
    COUNCIL_REVIEW_THRESHOLD,
    COUNCIL_STRONG_SIGNAL_THRESHOLD,
    FAIL_CLOSED_CRITICAL_THRESHOLD,
    HUMAN_REVIEW_MIN_CONFIDENCE,
)
from app.schemas import CouncilResult, ExpertVerdict


CRITICAL_DIMENSION_EXPERTS = {"team2_redteam_expert", "team1_policy_expert"}
EXPERT_LABELS = {
    "team1_policy_expert": "Team1 policy expert",
    "team2_redteam_expert": "Team2 red-team expert",
    "team3_risk_expert": "Team3 system-risk expert",
}

def synthesize_council(experts: list[ExpertVerdict]) -> CouncilResult:
    """Apply the named arbitration matrix to expert verdicts and produce an auditable council result."""
    if not experts:
        return CouncilResult(
            decision="REVIEW",
            council_score=0.5,
            needs_human_review=True,
            rationale="No expert verdicts available.",
            decision_rule_triggered="no_experts",
            consensus_summary="The council could not form a defensible decision because no expert outputs were available.",
            cross_expert_critique=["No expert viewpoints were available to compare or reconcile."],
            recommended_actions=["Re-run the evaluation so all three expert modules produce outputs before final review."],
            disagreement_index=1.0,
            triggered_by=["no_experts"],
            key_evidence=["No expert verdicts available."],
            ignored_signals=[],
            decision_rule_version=COUNCIL_DECISION_RULE_VERSION,
        )

    risk_scores = [verdict.risk_score for verdict in experts]
    disagreement = min(1.0, pstdev(risk_scores) * 2.0) if len(risk_scores) > 1 else 0.0
    avg_score = sum(risk_scores) / len(risk_scores)
    min_confidence = min(verdict.confidence for verdict in experts)

    triggered_by: list[str] = []
    key_evidence: list[str] = []
    ignored_signals: list[str] = []
    decision_rule_triggered = ""

    failed = [verdict for verdict in experts if verdict.evaluation_status == "failed"]
    degraded = [verdict for verdict in experts if verdict.evaluation_status == "degraded"]
    critical_flags = [
        verdict for verdict in experts if verdict.critical and verdict.risk_score >= FAIL_CLOSED_CRITICAL_THRESHOLD
    ]
    high = [verdict for verdict in experts if verdict.risk_score >= COUNCIL_BLOCK_THRESHOLD]
    medium = [verdict for verdict in experts if verdict.risk_score >= COUNCIL_REVIEW_THRESHOLD]

    if critical_flags:
        decision_rule_triggered = "critical_fail_closed"
        triggered_by.extend(verdict.expert_name for verdict in critical_flags)
        key_evidence.extend(
            f"{verdict.expert_name} marked critical at {verdict.risk_score:.2f}" for verdict in critical_flags
        )
        decision = "REJECT"
        rationale = f"Fail-closed: critical risk by {', '.join(verdict.expert_name for verdict in critical_flags)}."
    elif any(verdict.expert_name == "team2_redteam_expert" for verdict in high) and any(
        verdict.expert_name == "team1_policy_expert" for verdict in high
    ):
        decision_rule_triggered = "policy_and_misuse_alignment"
        decision = "REJECT"
        triggered_by.extend(["team2_redteam_expert", "team1_policy_expert"])
        key_evidence.append("Team2 and Team1 both produced high-risk verdicts.")
        rationale = "Behavioral attack risk and policy/compliance risk jointly require rejection."
    elif failed:
        decision_rule_triggered = "expert_failure_review"
        decision = "REVIEW"
        triggered_by.extend(verdict.expert_name for verdict in failed)
        key_evidence.extend(
            f"{verdict.expert_name} returned evaluation_status=failed" for verdict in failed
        )
        rationale = "At least one expert failed; human review required."
    elif any(verdict.expert_name in CRITICAL_DIMENSION_EXPERTS for verdict in degraded):
        decision_rule_triggered = "critical_expert_degraded"
        decision = "REVIEW"
        critical_degraded = [verdict for verdict in degraded if verdict.expert_name in CRITICAL_DIMENSION_EXPERTS]
        triggered_by.extend(verdict.expert_name for verdict in critical_degraded)
        key_evidence.extend(
            f"{verdict.expert_name} returned evaluation_status=degraded" for verdict in critical_degraded
        )
        rationale = "A critical expert degraded; human review required."
    elif len(high) >= 2:
        decision_rule_triggered = "multi_expert_high_risk"
        decision = "REJECT"
        triggered_by.extend(verdict.expert_name for verdict in high)
        key_evidence.append(f"{len(high)} experts crossed the high-risk threshold.")
        rationale = "Multiple experts indicate high combined risk."
    elif any(verdict.expert_name == "team3_risk_expert" for verdict in high):
        decision_rule_triggered = "system_risk_review"
        decision = "REVIEW"
        triggered_by.append("team3_risk_expert")
        key_evidence.append("Team3 flagged elevated system/deployment risk.")
        rationale = "System-level risk requires review even without cross-expert high risk."
    elif min_confidence < HUMAN_REVIEW_MIN_CONFIDENCE:
        decision_rule_triggered = "low_confidence_review"
        decision = "REVIEW"
        low_confidence = [verdict for verdict in experts if verdict.confidence < HUMAN_REVIEW_MIN_CONFIDENCE]
        triggered_by.extend(verdict.expert_name for verdict in low_confidence)
        key_evidence.extend(
            f"{verdict.expert_name} confidence={verdict.confidence:.2f}" for verdict in low_confidence
        )
        rationale = "One or more experts reported low confidence."
    elif disagreement >= 0.35:
        decision_rule_triggered = "expert_disagreement_review"
        decision = "REVIEW"
        triggered_by.append("disagreement")
        key_evidence.append(f"Expert disagreement index={disagreement:.2f}")
        rationale = "Expert disagreement requires review."
    elif medium:
        decision_rule_triggered = "moderate_risk_review"
        decision = "REVIEW"
        triggered_by.extend(verdict.expert_name for verdict in medium)
        key_evidence.append(f"Average risk score={avg_score:.2f}; moderate risk present.")
        rationale = "Moderate risk requires review before approval."
    else:
        decision_rule_triggered = "baseline_approve"
        decision = "APPROVE"
        key_evidence.append(f"Average risk score={avg_score:.2f} and all experts returned stable outputs.")
        rationale = "Risk profile is within baseline threshold."

    strong_but_not_triggering = [
        verdict for verdict in experts if verdict.risk_score >= COUNCIL_STRONG_SIGNAL_THRESHOLD and verdict.expert_name not in triggered_by
    ]
    ignored_signals.extend(
        f"{verdict.expert_name} had strong risk score {verdict.risk_score:.2f} but did not independently determine the final decision"
        for verdict in strong_but_not_triggering
    )

    consensus_summary = _build_consensus_summary(experts, decision, disagreement)
    cross_expert_critique = _build_cross_expert_critique(experts, decision, disagreement, failed, degraded)
    recommended_actions = _build_recommended_actions(experts, decision)

    return CouncilResult(
        decision=decision,
        council_score=round(avg_score, 4),
        needs_human_review=(decision == "REVIEW"),
        rationale=rationale,
        decision_rule_triggered=decision_rule_triggered,
        consensus_summary=consensus_summary,
        cross_expert_critique=cross_expert_critique,
        recommended_actions=recommended_actions,
        disagreement_index=round(disagreement, 4),
        triggered_by=triggered_by,
        key_evidence=key_evidence,
        ignored_signals=ignored_signals,
        decision_rule_version=COUNCIL_DECISION_RULE_VERSION,
    )

def _build_consensus_summary(experts: list[ExpertVerdict], decision: str, disagreement: float) -> str:
    if not experts:
        return "No council summary available."

    ordered = sorted(experts, key=lambda verdict: verdict.risk_score, reverse=True)
    leader = ordered[0]
    tail = ordered[-1]
    leader_label = _expert_label(leader.expert_name)
    tail_label = _expert_label(tail.expert_name)

    if disagreement >= 0.35:
        return (
            f"The council reached {decision} with material disagreement: {leader_label} was most concerned "
            f"({leader.risk_score:.2f}) while {tail_label} was least concerned ({tail.risk_score:.2f})."
        )

    if decision == "REJECT":
        return (
            f"The council converged on REJECT because multiple experts aligned on risk and the strongest signal came from "
            f"{leader_label} ({leader.risk_score:.2f})."
        )
    if decision == "REVIEW":
        return (
            f"The council converged on REVIEW: the evidence was strong enough to block approval, but not uniform enough "
            f"for an automatic reject across all experts."
        )
    return "The council found broadly consistent low-to-moderate risk signals and approved the submission without escalation."

def _build_cross_expert_critique(
    experts: list[ExpertVerdict],
    decision: str,
    disagreement: float,
    failed: list[ExpertVerdict],
    degraded: list[ExpertVerdict],
) -> list[str]:
    verdicts = {verdict.expert_name: verdict for verdict in experts}
    team1 = verdicts.get("team1_policy_expert")
    team2 = verdicts.get("team2_redteam_expert")
    team3 = verdicts.get("team3_risk_expert")

    critique: list[str] = []

    if team1 and team2:
        if team1.risk_score >= COUNCIL_BLOCK_THRESHOLD and team2.risk_score >= COUNCIL_BLOCK_THRESHOLD:
            critique.append(
                "Team1 and Team2 independently reached high-risk conclusions, so the council treated governance risk and misuse risk as mutually reinforcing rather than redundant."
            )
        elif abs(team1.risk_score - team2.risk_score) >= 0.2:
            higher = team1 if team1.risk_score > team2.risk_score else team2
            lower = team2 if higher is team1 else team1
            critique.append(
                f"{_expert_label(higher.expert_name)} was materially more severe than {_expert_label(lower.expert_name)}, which signals that policy exposure and abuse-path exposure are not perfectly aligned in this submission."
            )
        else:
            critique.append(
                "Team1 and Team2 were directionally aligned, which increased confidence that both compliance and misuse concerns are describing the same underlying system weaknesses."
            )

    if team3:
        if team3.risk_score >= COUNCIL_BLOCK_THRESHOLD:
            critique.append(
                "Team3 elevated the case on architecture and deployment grounds, meaning the council could not dismiss the result as only prompt-level or policy-only concern."
            )
        elif team3.risk_score >= COUNCIL_REVIEW_THRESHOLD:
            critique.append(
                "Team3 did not force rejection, but it confirmed the repository has system-level exposure that keeps the case above a simple approve threshold."
            )
        else:
            critique.append(
                "Team3 was less severe than the other experts, so the council interpreted some risk as workflow- and governance-driven rather than purely architectural."
            )

    if failed:
        critique.append(
            "Because one or more experts failed outright, the council downgraded confidence in any apparent consensus and required human review instead of over-trusting partial automation."
        )
    elif degraded:
        critique.append(
            "At least one expert returned degraded output, so the council treated agreement as provisional and preserved review rather than overclaiming certainty."
        )

    if disagreement >= 0.35:
        critique.append(
            "The disagreement index was high enough that the council explicitly weighted divergence as a signal: the experts are identifying different failure modes, not simply repeating the same finding."
        )
    elif decision == "APPROVE":
        critique.append(
            "The experts were sufficiently aligned that the council did not see a hidden dissenting view strong enough to justify escalation."
        )

    return critique

def _build_recommended_actions(experts: list[ExpertVerdict], decision: str) -> list[str]:
    verdicts = {verdict.expert_name: verdict for verdict in experts}
    actions: list[str] = []

    team3 = verdicts.get("team3_risk_expert")
    if team3 and team3.risk_score >= COUNCIL_REVIEW_THRESHOLD:
        upload_path = _team2_public_upload_path(verdicts.get("team2_redteam_expert"))
        if upload_path:
            actions.append(
                f"Harden the deployment boundary around `{upload_path}`: require authentication, isolate media-processing steps, and review how uploaded content reaches external AI services."
            )
        else:
            actions.append("Harden the deployment boundary: review upload, execution, and external-model integration paths before approval.")

    team2 = verdicts.get("team2_redteam_expert")
    if team2 and team2.risk_score >= COUNCIL_REVIEW_THRESHOLD:
        owasp = _team2_taxonomy(team2, "owasp_categories")
        mitre = _team2_taxonomy(team2, "mitre_tactics")
        taxonomy_hint = []
        if owasp:
            taxonomy_hint.append(f"OWASP focus: {', '.join(owasp[:2])}")
        if mitre:
            taxonomy_hint.append(f"MITRE focus: {', '.join(mitre[:2])}")
        suffix = f" ({'; '.join(taxonomy_hint)})" if taxonomy_hint else ""
        actions.append(
            f"Reduce abuse-path exposure by validating unauthenticated entry points, hostile file handling, and prompt-injection safeguards before approval{suffix}."
        )

    team1 = verdicts.get("team1_policy_expert")
    if team1 and team1.risk_score >= COUNCIL_REVIEW_THRESHOLD:
        policy_signal = _team1_policy_focus(team1)
        if policy_signal:
            actions.append(
                f"Document policy controls, access control, and accountability evidence so governance claims match the runtime design, especially around {policy_signal}."
            )
        else:
            actions.append("Document policy controls, access control, and accountability evidence so governance claims match the actual runtime design.")

    if decision == "APPROVE" and not actions:
        actions.append("Keep the current controls stable and preserve the documented evidence trail used for this approval.")

    return actions[:4]



def _expert_label(expert_name: str) -> str:
    return EXPERT_LABELS.get(expert_name, expert_name)


def _team2_public_upload_path(verdict: ExpertVerdict | None) -> str:
    if verdict is None:
        return ""
    evidence = verdict.evidence or {}
    surface = evidence.get("redteam_surface", {})
    if not isinstance(surface, dict):
        return ""
    candidates: list[str] = []
    for route in surface.get("route_inventory", []):
        if not isinstance(route, dict):
            continue
        if route.get("has_upload") and not route.get("auth_guarded", False):
            path = str(route.get("path", "")).strip()
            if path:
                candidates.append(path)
    prioritized = [path for path in candidates if "upload" in path.lower()]
    if prioritized:
        return prioritized[0]
    return candidates[0] if candidates else ""


def _team2_taxonomy(verdict: ExpertVerdict | None, key: str) -> list[str]:
    if verdict is None:
        return []
    evidence = verdict.evidence or {}
    taxonomy = evidence.get("taxonomy", {})
    if not isinstance(taxonomy, dict):
        return []
    return [str(item) for item in taxonomy.get(key, []) if str(item).strip()]


def _team1_policy_focus(verdict: ExpertVerdict | None) -> str:
    if verdict is None:
        return ""
    evidence = verdict.evidence or {}
    controls = [str(item) for item in evidence.get("policy_scope_controls", []) if str(item).strip()]
    if controls:
        return controls[0].rstrip(".").lower()
    for item in evidence.get("policy_scope_evidence", []):
        if isinstance(item, dict) and item.get("signal"):
            return str(item["signal"]).rstrip(".").lower()
    return ""
