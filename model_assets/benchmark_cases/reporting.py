from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .metrics import BenchmarkOutcome, summarize_outcomes


@dataclass(slots=True)
class WorstCaseSliceSummary:
    slice_label: str
    observation_count: int
    unique_case_count: int
    accuracy: float
    false_approve_rate: float
    false_reject_rate: float
    review_rate: float
    error_rate: float


@dataclass(slots=True)
class WorstCaseCaseSummary:
    case_id: str
    title: str
    evaluation_mode: str
    expected_decision: str
    baseline_name: str
    slice_labels: list[str] = field(default_factory=list)
    total_runs: int = 0
    mismatch_count: int = 0
    mismatch_rate: float = 0.0
    false_approve_count: int = 0
    false_reject_count: int = 0
    error_count: int = 0
    instability_score: float = 0.0
    observed_decisions: dict[str, int] = field(default_factory=dict)
    likely_failure_mode: str = ""


@dataclass(slots=True)
class WorstCaseReport:
    total_runs: int
    total_observations: int
    worst_slices: list[WorstCaseSliceSummary] = field(default_factory=list)
    critical_failures: list[WorstCaseCaseSummary] = field(default_factory=list)
    most_unstable_cases: list[WorstCaseCaseSummary] = field(default_factory=list)


def build_worst_case_report(
    runs: Sequence[object],
    *,
    case_lookup: Mapping[str, object],
    top_n: int = 5,
) -> WorstCaseReport:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    slice_outcomes: dict[str, list[BenchmarkOutcome]] = defaultdict(list)
    case_groups: dict[str, list[BenchmarkOutcome]] = defaultdict(list)
    total_observations = 0

    for run in runs:
        run_id = _extract_value(run, "run_id", default="")
        baseline_id = _extract_value(run, "baseline_id", default="")
        for result in _extract_value(run, "results", required=True):
            case_id = str(_extract_value(result, "case_id", required=True))
            case = case_lookup[case_id]
            expected_decision = str(_extract_value(result, "expected_decision", required=True))
            actual_decision = _extract_value(result, "actual_decision")
            error = str(_extract_value(result, "error", default="") or "")
            baseline_name = _case_baseline_name(case, baseline_id)
            labels = _case_slice_labels(case)

            outcome = BenchmarkOutcome(
                case_id=case_id,
                expected_decision=expected_decision,  # type: ignore[arg-type]
                actual_decision=actual_decision,  # type: ignore[arg-type]
                baseline_name=baseline_name,
                run_id=str(run_id or ""),
                error=error,
            )
            case_groups[case_id].append(outcome)
            total_observations += 1

            for label in labels:
                slice_outcomes[label].append(
                    BenchmarkOutcome(
                        case_id=case_id,
                        expected_decision=expected_decision,  # type: ignore[arg-type]
                        actual_decision=actual_decision,  # type: ignore[arg-type]
                        slice_name=label,
                        baseline_name=baseline_name,
                        run_id=str(run_id or ""),
                        error=error,
                    )
                )

    worst_slices = _build_worst_slices(slice_outcomes, top_n=top_n)
    critical_failures, unstable_cases = _build_case_reports(case_groups, case_lookup, top_n=top_n)

    return WorstCaseReport(
        total_runs=len(runs),
        total_observations=total_observations,
        worst_slices=worst_slices,
        critical_failures=critical_failures,
        most_unstable_cases=unstable_cases,
    )


def _build_worst_slices(
    slice_outcomes: Mapping[str, Sequence[BenchmarkOutcome]],
    *,
    top_n: int,
) -> list[WorstCaseSliceSummary]:
    summaries: list[WorstCaseSliceSummary] = []
    for label, outcomes in slice_outcomes.items():
        summary = summarize_outcomes(outcomes, interval_method="percentile", confidence_level=1.0)
        summaries.append(
            WorstCaseSliceSummary(
                slice_label=label,
                observation_count=summary.n_observations,
                unique_case_count=len({outcome.case_id for outcome in outcomes}),
                accuracy=summary.accuracy.estimate,
                false_approve_rate=summary.false_approve_rate.estimate,
                false_reject_rate=summary.false_reject_rate.estimate,
                review_rate=summary.review_rate.estimate,
                error_rate=summary.error_rate.estimate,
            )
        )

    summaries.sort(
        key=lambda item: (
            -item.false_approve_rate,
            -item.error_rate,
            item.accuracy,
            -item.review_rate,
            item.slice_label,
        )
    )
    return summaries[:top_n]


def _build_case_reports(
    case_groups: Mapping[str, Sequence[BenchmarkOutcome]],
    case_lookup: Mapping[str, object],
    *,
    top_n: int,
) -> tuple[list[WorstCaseCaseSummary], list[WorstCaseCaseSummary]]:
    critical: list[WorstCaseCaseSummary] = []
    unstable: list[WorstCaseCaseSummary] = []

    for case_id, outcomes in case_groups.items():
        case = case_lookup[case_id]
        summary = _summarize_case(case, outcomes)
        if _is_critical_case(case, summary):
            critical.append(summary)
        unstable.append(summary)

    critical.sort(
        key=lambda item: (
            -item.false_approve_count,
            -item.error_count,
            -item.mismatch_rate,
            -item.instability_score,
            item.case_id,
        )
    )
    unstable.sort(
        key=lambda item: (
            -item.instability_score,
            -item.mismatch_rate,
            -item.error_count,
            -item.false_approve_count,
            item.case_id,
        )
    )
    return critical[:top_n], unstable[:top_n]


def _summarize_case(case: object, outcomes: Sequence[BenchmarkOutcome]) -> WorstCaseCaseSummary:
    title = str(_extract_value(case, "title", default=""))
    evaluation_mode = str(_extract_value(case, "evaluation_mode", default="repository_only"))
    expected_decision = str(_extract_value(case, "expected_decision", default="REVIEW"))
    baseline_name = _case_baseline_name(case, "")
    slice_labels = _case_slice_labels(case)

    total_runs = len(outcomes)
    mismatch_count = sum(1 for item in outcomes if item.actual_decision != item.expected_decision)
    false_approve_count = sum(
        1 for item in outcomes if item.actual_decision == "APPROVE" and item.expected_decision != "APPROVE"
    )
    false_reject_count = sum(
        1 for item in outcomes if item.actual_decision == "REJECT" and item.expected_decision != "REJECT"
    )
    error_count = sum(1 for item in outcomes if item.actual_decision is None)
    observed = Counter(item.actual_decision or "ERROR" for item in outcomes)
    dominant = max(observed.values()) if observed else 0
    instability_score = 0.0 if total_runs == 0 else 1.0 - (dominant / total_runs)

    return WorstCaseCaseSummary(
        case_id=str(_extract_value(case, "case_id", default="")),
        title=title,
        evaluation_mode=evaluation_mode,
        expected_decision=expected_decision,
        baseline_name=baseline_name,
        slice_labels=slice_labels,
        total_runs=total_runs,
        mismatch_count=mismatch_count,
        mismatch_rate=(mismatch_count / total_runs) if total_runs else 0.0,
        false_approve_count=false_approve_count,
        false_reject_count=false_reject_count,
        error_count=error_count,
        instability_score=instability_score,
        observed_decisions=dict(observed),
        likely_failure_mode=_likely_failure_mode(
            expected_decision=expected_decision,
            false_approve_count=false_approve_count,
            false_reject_count=false_reject_count,
            error_count=error_count,
            instability_score=instability_score,
        ),
    )


def _case_baseline_name(case: object, default: str) -> str:
    baseline = _extract_value(case, "baseline_metadata")
    if baseline is None:
        return default
    baseline_name = _extract_value(baseline, "baseline_name", default=default)
    return str(baseline_name or default)


def _case_slice_labels(case: object) -> list[str]:
    labels = _extract_value(case, "slice_labels", default=[])
    cleaned = [str(label).strip() for label in labels if str(label).strip()]
    if cleaned:
        return cleaned
    evaluation_mode = str(_extract_value(case, "evaluation_mode", default="repository_only"))
    return [f"mode:{evaluation_mode}"]


def _is_critical_case(case: object, summary: WorstCaseCaseSummary) -> bool:
    benchmark_tags = {str(tag).strip().lower() for tag in _extract_value(case, "benchmark_tags", default=[])}
    if summary.expected_decision == "REJECT":
        return True
    if "critical" in benchmark_tags:
        return True
    return summary.false_approve_count > 0


def _likely_failure_mode(
    *,
    expected_decision: str,
    false_approve_count: int,
    false_reject_count: int,
    error_count: int,
    instability_score: float,
) -> str:
    if false_approve_count > 0 and expected_decision == "REJECT":
        return "unsafe_false_approve"
    if error_count > 0:
        return "execution_error"
    if false_reject_count > 0 and expected_decision == "APPROVE":
        return "overblocking_false_reject"
    if instability_score >= 0.4:
        return "decision_instability"
    if false_approve_count > 0:
        return "false_approve"
    if false_reject_count > 0:
        return "false_reject"
    return "mismatch"


def _extract_value(item: object, field_name: str, *, required: bool = False, default: Any = None) -> Any:
    value: Any
    if isinstance(item, Mapping):
        value = item.get(field_name, default)
    else:
        value = getattr(item, field_name, default)
    if required and value is None:
        raise ValueError(f"missing required field: {field_name}")
    return value


__all__ = [
    "WorstCaseCaseSummary",
    "WorstCaseReport",
    "WorstCaseSliceSummary",
    "build_worst_case_report",
]
