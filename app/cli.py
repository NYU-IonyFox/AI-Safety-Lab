from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.orchestrator import SafetyLabOrchestrator
from app.schemas import AgentContext, EvaluationRequest, SubmissionTarget


def build_request(args: argparse.Namespace) -> EvaluationRequest:
    source_type = "github_url" if args.github_url else "local_path"
    if args.name:
        target_name = args.name
    elif args.local_path:
        target_name = Path(args.local_path).name
    elif args.github_url:
        target_name = args.github_url.rstrip("/").split("/")[-1] or "Submitted Repository"
    else:
        target_name = "Submitted Repository"
    return EvaluationRequest(
        context=AgentContext(
            agent_name=target_name,
            description=args.description,
            domain="Other",
            capabilities=[],
            high_autonomy=False,
        ),
        selected_policies=["eu_ai_act", "us_nist", "iso", "unesco"],
        conversation=[],
        metadata={},
        submission=SubmissionTarget(
            source_type=source_type,
            github_url=args.github_url or "",
            local_path=args.local_path or "",
            target_name=target_name,
            description=args.description,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a repository evaluation without hand-writing the JSON schema.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--github-url", help="Public GitHub repository URL to evaluate.")
    source.add_argument("--local-path", help="Absolute local repository path to evaluate.")
    parser.add_argument("--name", default="", help="Optional display name for the repository.")
    parser.add_argument("--description", default="Repository submission for AI safety review.", help="Short description shown in the report.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON response instead of a short summary.")
    args = parser.parse_args()

    response = SafetyLabOrchestrator().evaluate(build_request(args))
    if args.json:
        print(json.dumps(response.model_dump(), indent=2, ensure_ascii=False))
        return

    print(f"Evaluation ID: {response.evaluation_id}")
    print(f"Decision: {response.decision}")
    print(f"Rule: {response.council_result.decision_rule_triggered}")
    print(f"Report: {response.report_path}")
    print(f"Archive: {response.archive_path}")


if __name__ == "__main__":
    main()
