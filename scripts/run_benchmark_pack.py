#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_assets.benchmark_cases.loader import default_pack_path, load_benchmark_pack, pack_summary  # noqa: E402
from model_assets.benchmark_cases.runner import evaluate_pack  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or inspect the public benchmark pack.")
    parser.add_argument("--pack", default=str(default_pack_path()), help="Path to the benchmark pack JSON file.")
    parser.add_argument(
        "--mode",
        choices={"inspect", "evaluate"},
        default="inspect",
        help="Inspect the pack locally or run the repo evaluation flow.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        default=[],
        help="Limit evaluation to a case id. May be repeated.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON results.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pack = load_benchmark_pack(args.pack)

    if args.mode == "inspect":
        summary = pack_summary(pack)
        if args.json:
            print(json.dumps({"pack": summary}, indent=2, ensure_ascii=False))
            return
        print(f"Benchmark pack: {summary['benchmark_name']} ({summary['version']})")
        print(f"Cases: {summary['case_count']}")
        print(f"Decision counts: {summary['decision_counts']}")
        print(f"Categories: {', '.join(summary['categories'])}")
        return

    try:
        from app.orchestrator import SafetyLabOrchestrator
        from app.schemas import AgentContext, EvaluationRequest, SubmissionTarget
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Unable to import the evaluation app: {exc}") from exc

    orchestrator = SafetyLabOrchestrator()

    def evaluate_case(case):
        request = EvaluationRequest(
            context=AgentContext(
                agent_name=case.agent_name,
                description=case.description,
                domain=case.domain,
                capabilities=list(case.capabilities),
                high_autonomy=case.high_autonomy,
            ),
            selected_policies=list(case.selected_policies),
            conversation=[],
            metadata={"benchmark_case_id": case.case_id, "benchmark_title": case.title},
            submission=SubmissionTarget(
                source_type="github_url",
                github_url=case.repo_url,
                target_name=case.agent_name,
                description=case.description,
            ),
        )
        response = orchestrator.evaluate(request)
        return response.decision, response.council_result.decision_rule_triggered, response.report_path, response.archive_path

    selected_case_ids = args.case_ids or None
    results = evaluate_pack(pack, case_ids=selected_case_ids, evaluator=evaluate_case)
    passed = sum(1 for result in results if result.match)
    payload = {
        "pack": pack_summary(pack),
        "results": [asdict(result) for result in results],
        "accuracy": round((passed / len(results)) if results else 0.0, 4),
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"Evaluated {len(results)} cases from {pack.benchmark_name}")
    print(f"Exact-match accuracy: {payload['accuracy']:.2%}")
    for result in results:
        status = "match" if result.match else "mismatch"
        print(
            f"- {result.case_id}: expected={result.expected_decision} actual={result.actual_decision or 'ERROR'} "
            f"({status}) rule={result.decision_rule_triggered or 'n/a'}"
        )
        if result.error:
            print(f"  error: {result.error}")


if __name__ == "__main__":
    main()
