from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.orchestrator import SafetyLabOrchestrator
from app.schemas import AgentContext, EvaluationRequest, SubmissionTarget


def build_request(local_path: str) -> EvaluationRequest:
    target_path = Path(local_path).resolve()
    return EvaluationRequest(
        context=AgentContext(agent_name=target_path.name or "local-diagnosis", description="Local SLM diagnosis probe"),
        selected_policies=["eu_ai_act", "us_nist", "iso", "unesco"],
        conversation=[],
        metadata={},
        submission=SubmissionTarget(
            source_type="local_path",
            local_path=str(target_path),
            target_name=target_path.name or "local-diagnosis",
            description="Diagnostic evaluation for local SLM runtime",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose why local SLM expert execution degraded or fell back.")
    parser.add_argument(
        "--local-path",
        default=".",
        help="Repository path to run through the three experts. Defaults to the current directory.",
    )
    parser.add_argument(
        "--as-json",
        action="store_true",
        help="Emit a JSON summary instead of the plain-text diagnostic view.",
    )
    args = parser.parse_args()

    orchestrator = SafetyLabOrchestrator()
    response = orchestrator.evaluate(build_request(args.local_path))

    payload = {
        "evaluation_id": response.evaluation_id,
        "decision": response.decision,
        "decision_rule_triggered": response.council_result.decision_rule_triggered,
        "configured_backend": response.version.expert_model_backend,
        "experts": [
            {
                "expert_name": expert.expert_name,
                "evaluation_status": expert.evaluation_status,
                "runner_mode": expert.metadata.runner_mode,
                "configured_backend": expert.metadata.configured_backend,
                "actual_backend": expert.metadata.actual_backend,
                "fallback_reason": expert.metadata.fallback_reason,
                "summary": expert.summary,
                "raw_output_preview": str(getattr(expert, "evidence", {}).get("raw", {}).get("_raw_text_preview", "")),
            }
            for expert in response.experts
        ],
    }

    if args.as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"evaluation_id: {payload['evaluation_id']}")
    print(f"decision: {payload['decision']}")
    print(f"decision_rule_triggered: {payload['decision_rule_triggered']}")
    print(f"configured_backend: {payload['configured_backend']}")
    for expert in payload["experts"]:
        print(f"\n== {expert['expert_name']} ==")
        print(f"status: {expert['evaluation_status']}")
        print(f"runner: {expert['runner_mode']}")
        print(f"configured_backend: {expert['configured_backend']}")
        print(f"actual_backend: {expert['actual_backend']}")
        print(f"fallback_reason: {expert['fallback_reason'] or '<none>'}")
        print(f"summary: {expert['summary']}")
        if expert["raw_output_preview"]:
            print(f"raw_output_preview: {expert['raw_output_preview']}")


if __name__ == "__main__":
    main()
