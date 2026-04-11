#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_assets.benchmark_cases import (  # noqa: E402
    BenchmarkOutcome,
    build_worst_case_report,
    default_pack_path,
    load_benchmark_pack,
    summarize_repeated_runs,
)
from model_assets.benchmark_cases.runner import BenchmarkRunContext, evaluate_pack_repeated  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the public benchmark pack repeatedly.")
    parser.add_argument("--pack", default=str(default_pack_path()), help="Path to the benchmark pack JSON file.")
    parser.add_argument("--repeats", type=int, default=5, help="How many full benchmark runs to execute.")
    parser.add_argument(
        "--baseline-id",
        default="current",
        help="Identifier for the system baseline used in the repeated benchmark report.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Starting seed for the first run.")
    parser.add_argument("--seed-step", type=int, default=1, help="Seed increment between repeated runs.")
    parser.add_argument(
        "--interval-method",
        choices={"bootstrap", "percentile"},
        default="bootstrap",
        help="Interval method for repeated-run metrics.",
    )
    parser.add_argument(
        "--confidence-level",
        type=float,
        default=0.95,
        help="Confidence level for interval reporting.",
    )
    parser.add_argument(
        "--n-resamples",
        type=int,
        default=1000,
        help="Bootstrap resample count when interval-method=bootstrap.",
    )
    parser.add_argument(
        "--worst-case-top-n",
        type=int,
        default=5,
        help="How many worst-case slices and cases to include in the long-tail report.",
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


def build_request_for_case(case: Any, context: BenchmarkRunContext):
    from app.schemas import AgentContext, ConversationTurn, EvaluationRequest, SubmissionTarget

    conversation = [
        ConversationTurn(role=_normalize_role(turn.role), content=turn.content)
        for turn in getattr(case, "transcript", [])
    ]
    metadata = {
        "benchmark_case_id": case.case_id,
        "benchmark_title": case.title,
        "benchmark_run_id": context.run_id,
        "benchmark_seed": context.seed,
        "baseline_id": context.baseline_id,
    }
    target_endpoint = str(getattr(case, "target_endpoint", "") or "").strip()
    if target_endpoint:
        metadata["target_endpoint"] = target_endpoint

    submission = None
    if getattr(case, "evaluation_mode", "repository_only") in {"repository_only", "hybrid"}:
        submission = SubmissionTarget(
            source_type="github_url",
            github_url=case.repo_url or "",
            target_name=case.agent_name,
            description=case.description,
        )

    return EvaluationRequest(
        evaluation_mode=getattr(case, "evaluation_mode", "repository_only"),
        context=AgentContext(
            agent_name=case.agent_name,
            description=case.description,
            domain=case.domain,
            capabilities=list(case.capabilities),
            high_autonomy=case.high_autonomy,
        ),
        selected_policies=list(case.selected_policies),
        conversation=conversation,
        metadata=metadata,
        submission=submission,
        calibration_case_id=case.case_id,
    )


def repeated_results_to_outcome_runs(repeated: Any, pack: Any) -> list[list[BenchmarkOutcome]]:
    case_lookup = {case.case_id: case for case in pack.cases}
    outcome_runs: list[list[BenchmarkOutcome]] = []
    for run in repeated.runs:
        run_outcomes: list[BenchmarkOutcome] = []
        for result in run.results:
            case = case_lookup[result.case_id]
            baseline_name = (
                case.baseline_metadata.baseline_name
                if getattr(case, "baseline_metadata", None) is not None
                else run.baseline_id
            )
            run_outcomes.append(
                BenchmarkOutcome(
                    case_id=result.case_id,
                    expected_decision=result.expected_decision,  # type: ignore[arg-type]
                    actual_decision=result.actual_decision,  # type: ignore[arg-type]
                    slice_name=getattr(case, "evaluation_mode", "repository_only"),
                    baseline_name=baseline_name,
                    run_id=run.run_id,
                    error=result.error,
                )
            )
        outcome_runs.append(run_outcomes)
    return outcome_runs


def _normalize_role(role: str) -> str:
    normalized = str(role or "user").strip().lower()
    if normalized not in {"system", "user", "assistant"}:
        return "user"
    return normalized


def main() -> None:
    args = parse_args()
    pack = load_benchmark_pack(args.pack)
    selected_case_ids = args.case_ids or None

    try:
        from app.orchestrator import SafetyLabOrchestrator
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Unable to import the evaluation app: {exc}") from exc

    orchestrator = SafetyLabOrchestrator()

    def evaluate_case(case, context):
        request = build_request_for_case(case, context)
        response = orchestrator.evaluate(request)
        return response.decision, response.council_result.decision_rule_triggered, response.report_path, response.archive_path

    repeated = evaluate_pack_repeated(
        pack,
        repeats=args.repeats,
        baseline_id=args.baseline_id,
        seed=args.seed,
        seed_step=args.seed_step,
        case_ids=selected_case_ids,
        evaluator=evaluate_case,
    )
    outcome_runs = repeated_results_to_outcome_runs(repeated, pack)
    metric_summary = summarize_repeated_runs(
        outcome_runs,
        confidence_level=args.confidence_level,
        interval_method=args.interval_method,
        n_resamples=args.n_resamples,
        seed=args.seed,
        group_fields=("slice_name", "baseline_name"),
    )
    worst_case_report = build_worst_case_report(
        repeated.runs,
        case_lookup={case.case_id: case for case in pack.cases},
        top_n=args.worst_case_top_n,
    )
    payload = {
        "repeated": asdict(repeated),
        "metrics": asdict(metric_summary),
        "worst_case_report": asdict(worst_case_report),
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"Repeated benchmark pack: {repeated.pack['benchmark_name']} ({repeated.pack['version']})")
    print(f"Baseline: {repeated.baseline_id}")
    print(f"Repeats: {repeated.repeat_count}")
    print(f"Seed start: {repeated.seed_start}")
    print(f"Seed step: {repeated.seed_step}")
    print(f"Selected cases: {len(repeated.selected_case_ids)}")
    print(f"Mean accuracy: {repeated.mean_accuracy:.2%} (min={repeated.min_accuracy:.2%}, max={repeated.max_accuracy:.2%})")
    print(
        "Repeated metrics: "
        f"accuracy={metric_summary.overall.accuracy.estimate:.2%} "
        f"false_approve={metric_summary.overall.false_approve_rate.estimate:.2%} "
        f"false_reject={metric_summary.overall.false_reject_rate.estimate:.2%} "
        f"review_rate={metric_summary.overall.review_rate.estimate:.2%}"
    )
    for run in repeated.runs:
        print(f"- {run.run_id} | seed={run.seed} | accuracy={run.accuracy:.2%} | {run.match_count}/{run.case_count} matched")
        for result in run.results:
            status = "match" if result.match else "mismatch"
            print(
                f"  - {result.case_id}: expected={result.expected_decision} actual={result.actual_decision or 'ERROR'} "
                f"({status}) rule={result.decision_rule_triggered or 'n/a'}"
            )
            if result.error:
                print(f"    error: {result.error}")
    if worst_case_report.worst_slices:
        print("Worst-case slices:")
        for item in worst_case_report.worst_slices:
            print(
                f"- {item.slice_label}: accuracy={item.accuracy:.2%} "
                f"false_approve={item.false_approve_rate:.2%} error_rate={item.error_rate:.2%}"
            )
    if worst_case_report.critical_failures:
        print("Critical failures:")
        for item in worst_case_report.critical_failures:
            print(
                f"- {item.case_id}: mismatch_rate={item.mismatch_rate:.2%} "
                f"false_approve={item.false_approve_count} instability={item.instability_score:.2f} "
                f"mode={item.likely_failure_mode}"
            )


if __name__ == "__main__":
    main()
