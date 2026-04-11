from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, floor
from random import Random
from statistics import mean
from typing import Any, Iterable, Literal, Mapping, Sequence

from .loader import Decision


IntervalMethod = Literal["bootstrap", "percentile"]


@dataclass(slots=True)
class BenchmarkOutcome:
    case_id: str
    expected_decision: Decision
    actual_decision: Decision | None
    slice_name: str | None = None
    baseline_name: str | None = None
    run_id: str | None = None
    error: str = ""

    def __post_init__(self) -> None:
        self.expected_decision = _normalize_decision(self.expected_decision)
        self.actual_decision = _normalize_decision(self.actual_decision)
        self.slice_name = _clean_optional_text(self.slice_name)
        self.baseline_name = _clean_optional_text(self.baseline_name)
        self.run_id = _clean_optional_text(self.run_id)
        self.error = self.error.strip()


@dataclass(slots=True)
class MetricInterval:
    estimate: float
    lower: float
    upper: float
    n: int
    method: str
    confidence_level: float


@dataclass(slots=True)
class DecisionMetricSummary:
    n_observations: int
    n_scored: int
    n_errors: int
    accuracy: MetricInterval
    false_approve_rate: MetricInterval
    false_reject_rate: MetricInterval
    review_rate: MetricInterval
    coverage_rate: MetricInterval
    error_rate: MetricInterval


@dataclass(slots=True)
class RepeatedBenchmarkSummary:
    n_runs: int
    overall: DecisionMetricSummary
    by_group: dict[str, DecisionMetricSummary] = field(default_factory=dict)


def summarize_outcomes(
    outcomes: Iterable[object],
    *,
    confidence_level: float = 0.95,
    interval_method: IntervalMethod = "bootstrap",
    n_resamples: int = 1_000,
    seed: int | None = 0,
) -> DecisionMetricSummary:
    records = [_coerce_outcome(outcome) for outcome in outcomes]
    if not records:
        raise ValueError("summarize_outcomes requires at least one outcome")

    return _summarize_records(
        records,
        confidence_level=confidence_level,
        interval_method=interval_method,
        n_resamples=n_resamples,
        seed=seed,
    )


def summarize_repeated_runs(
    runs: Iterable[Iterable[object]],
    *,
    confidence_level: float = 0.95,
    interval_method: IntervalMethod = "bootstrap",
    n_resamples: int = 1_000,
    seed: int | None = 0,
    group_fields: Sequence[str] = ("slice_name", "baseline_name"),
) -> RepeatedBenchmarkSummary:
    normalized_runs = _normalize_runs(runs)
    if not normalized_runs:
        raise ValueError("summarize_repeated_runs requires at least one run")

    run_summaries = [
        _summarize_records(
            [_coerce_outcome(outcome) for outcome in run],
            confidence_level=confidence_level,
            interval_method=interval_method,
            n_resamples=n_resamples,
            seed=seed,
        )
        for run in normalized_runs
    ]
    overall = _summarize_summary_series(
        run_summaries,
        confidence_level=confidence_level,
        interval_method=interval_method,
        n_resamples=n_resamples,
        seed=seed,
    )

    grouped_runs: dict[str, list[DecisionMetricSummary]] = {}
    for run in normalized_runs:
        grouped_records = _group_records([_coerce_outcome(outcome) for outcome in run], group_fields=group_fields)
        for group_label, records in grouped_records.items():
            grouped_runs.setdefault(group_label, []).append(
                _summarize_records(
                    records,
                    confidence_level=confidence_level,
                    interval_method=interval_method,
                    n_resamples=n_resamples,
                    seed=seed,
                )
            )

    by_group = {
        group_label: _summarize_summary_series(
            summaries,
            confidence_level=confidence_level,
            interval_method=interval_method,
            n_resamples=n_resamples,
            seed=seed,
        )
        for group_label, summaries in sorted(grouped_runs.items())
    }

    return RepeatedBenchmarkSummary(n_runs=len(normalized_runs), overall=overall, by_group=by_group)


def bootstrap_interval(
    values: Sequence[float],
    *,
    confidence_level: float = 0.95,
    n_resamples: int = 1_000,
    seed: int | None = 0,
) -> MetricInterval:
    numeric_values = _require_numeric_values(values)
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")

    estimate = mean(numeric_values)
    if len(numeric_values) == 1:
        return MetricInterval(
            estimate=estimate,
            lower=estimate,
            upper=estimate,
            n=1,
            method="bootstrap",
            confidence_level=confidence_level,
        )

    rng = Random(seed)
    resampled_means = [
        mean(rng.choices(numeric_values, k=len(numeric_values)))
        for _ in range(n_resamples)
    ]
    lower, upper = _percentile_bounds(resampled_means, confidence_level)
    return MetricInterval(
        estimate=estimate,
        lower=lower,
        upper=upper,
        n=len(numeric_values),
        method="bootstrap",
        confidence_level=confidence_level,
    )


def percentile_interval(
    values: Sequence[float],
    *,
    confidence_level: float = 0.95,
) -> MetricInterval:
    numeric_values = _require_numeric_values(values)
    estimate = mean(numeric_values)
    lower, upper = _percentile_bounds(numeric_values, confidence_level)
    return MetricInterval(
        estimate=estimate,
        lower=lower,
        upper=upper,
        n=len(numeric_values),
        method="percentile",
        confidence_level=confidence_level,
    )


def _summarize_records(
    records: Sequence[BenchmarkOutcome],
    *,
    confidence_level: float,
    interval_method: IntervalMethod,
    n_resamples: int,
    seed: int | None,
) -> DecisionMetricSummary:
    n_observations = len(records)
    if n_observations == 0:
        raise ValueError("cannot summarize an empty record set")

    scored_records = [record for record in records if record.actual_decision is not None]
    n_scored = len(scored_records)
    n_errors = n_observations - n_scored

    def metric(values: Sequence[float]) -> MetricInterval:
        if not values:
            return MetricInterval(
                estimate=0.0,
                lower=0.0,
                upper=0.0,
                n=0,
                method=interval_method,
                confidence_level=confidence_level,
            )
        if interval_method == "bootstrap":
            return bootstrap_interval(
                values,
                confidence_level=confidence_level,
                n_resamples=n_resamples,
                seed=seed,
            )
        return percentile_interval(values, confidence_level=confidence_level)

    scored_accuracy = [1.0 if record.actual_decision == record.expected_decision else 0.0 for record in scored_records]
    false_approve = [
        1.0 if record.actual_decision == "APPROVE" and record.expected_decision != "APPROVE" else 0.0
        for record in scored_records
    ]
    false_reject = [
        1.0 if record.actual_decision == "REJECT" and record.expected_decision != "REJECT" else 0.0
        for record in scored_records
    ]
    review_rate = [
        1.0 if record.actual_decision == "REVIEW" else 0.0
        for record in scored_records
    ]
    coverage_rate = [1.0 if record.actual_decision is not None else 0.0 for record in records]
    error_rate = [1.0 if record.actual_decision is None else 0.0 for record in records]

    return DecisionMetricSummary(
        n_observations=n_observations,
        n_scored=n_scored,
        n_errors=n_errors,
        accuracy=metric(scored_accuracy),
        false_approve_rate=metric(false_approve),
        false_reject_rate=metric(false_reject),
        review_rate=metric(review_rate),
        coverage_rate=metric(coverage_rate),
        error_rate=metric(error_rate),
    )


def _summarize_summary_series(
    summaries: Sequence[DecisionMetricSummary],
    *,
    confidence_level: float,
    interval_method: IntervalMethod,
    n_resamples: int,
    seed: int | None,
) -> DecisionMetricSummary:
    if not summaries:
        raise ValueError("cannot summarize an empty summary series")

    def metric(values: Sequence[float]) -> MetricInterval:
        if not values:
            return MetricInterval(
                estimate=0.0,
                lower=0.0,
                upper=0.0,
                n=0,
                method=interval_method,
                confidence_level=confidence_level,
            )
        if interval_method == "bootstrap":
            return bootstrap_interval(
                values,
                confidence_level=confidence_level,
                n_resamples=n_resamples,
                seed=seed,
            )
        return percentile_interval(values, confidence_level=confidence_level)

    return DecisionMetricSummary(
        n_observations=sum(summary.n_observations for summary in summaries),
        n_scored=sum(summary.n_scored for summary in summaries),
        n_errors=sum(summary.n_errors for summary in summaries),
        accuracy=metric([summary.accuracy.estimate for summary in summaries]),
        false_approve_rate=metric([summary.false_approve_rate.estimate for summary in summaries]),
        false_reject_rate=metric([summary.false_reject_rate.estimate for summary in summaries]),
        review_rate=metric([summary.review_rate.estimate for summary in summaries]),
        coverage_rate=metric([summary.coverage_rate.estimate for summary in summaries]),
        error_rate=metric([summary.error_rate.estimate for summary in summaries]),
    )


def _normalize_runs(runs: Iterable[Iterable[object]]) -> list[list[object]]:
    items = list(runs)
    if not items:
        return []
    first = items[0]
    if _is_record_like(first):
        return [items]
    return [list(run) for run in items]


def _group_records(
    records: Sequence[BenchmarkOutcome],
    *,
    group_fields: Sequence[str],
) -> dict[str, list[BenchmarkOutcome]]:
    grouped: dict[str, list[BenchmarkOutcome]] = {}
    for record in records:
        label = _group_label(record, group_fields)
        grouped.setdefault(label, []).append(record)
    return grouped


def _group_label(record: BenchmarkOutcome, group_fields: Sequence[str]) -> str:
    parts: list[str] = []
    for field_name in group_fields:
        value = getattr(record, field_name, None)
        if value not in {None, ""}:
            parts.append(f"{field_name.removesuffix('_name')}={value}")
    return "|".join(parts) if parts else "overall"


def _coerce_outcome(outcome: object) -> BenchmarkOutcome:
    if isinstance(outcome, BenchmarkOutcome):
        return outcome

    case_id = _extract_value(outcome, "case_id", required=True)
    expected_decision = _extract_value(outcome, "expected_decision", required=True)
    actual_decision = _extract_value(outcome, "actual_decision")
    slice_name = _extract_value(outcome, "slice_name")
    baseline_name = _extract_value(outcome, "baseline_name")
    run_id = _extract_value(outcome, "run_id")
    error = _extract_value(outcome, "error", default="")

    return BenchmarkOutcome(
        case_id=str(case_id),
        expected_decision=expected_decision,  # type: ignore[arg-type]
        actual_decision=actual_decision,  # type: ignore[arg-type]
        slice_name=slice_name,
        baseline_name=baseline_name,
        run_id=run_id,
        error="" if error is None else str(error),
    )


def _extract_value(item: object, field_name: str, *, required: bool = False, default: Any = None) -> Any:
    value: Any
    if isinstance(item, Mapping):
        value = item.get(field_name, default)
    else:
        value = getattr(item, field_name, default)
    if required and value is None:
        raise ValueError(f"missing required field: {field_name}")
    return value


def _normalize_decision(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if not normalized:
        return None
    if normalized not in {"APPROVE", "REVIEW", "REJECT"}:
        raise ValueError(f"unsupported decision value: {value!r}")
    return normalized


def _clean_optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_numeric_values(values: Sequence[float]) -> list[float]:
    numeric_values = [float(value) for value in values]
    if not numeric_values:
        raise ValueError("at least one numeric value is required")
    return numeric_values


def _percentile_bounds(values: Sequence[float], confidence_level: float) -> tuple[float, float]:
    numeric_values = sorted(float(value) for value in values)
    if not numeric_values:
        raise ValueError("at least one numeric value is required")
    if len(numeric_values) == 1:
        return numeric_values[0], numeric_values[0]
    if not 0.0 < confidence_level <= 1.0:
        raise ValueError("confidence_level must be in (0.0, 1.0]")

    alpha = (1.0 - confidence_level) / 2.0
    lower = _percentile(numeric_values, alpha)
    upper = _percentile(numeric_values, 1.0 - alpha)
    return lower, upper


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise ValueError("at least one numeric value is required")
    if quantile <= 0.0:
        return float(values[0])
    if quantile >= 1.0:
        return float(values[-1])

    index = (len(values) - 1) * quantile
    lower_index = floor(index)
    upper_index = ceil(index)
    if lower_index == upper_index:
        return float(values[lower_index])

    lower_value = float(values[lower_index])
    upper_value = float(values[upper_index])
    fraction = index - lower_index
    return lower_value + ((upper_value - lower_value) * fraction)


def _is_record_like(value: object) -> bool:
    return isinstance(value, (BenchmarkOutcome, Mapping)) or hasattr(value, "case_id")


__all__ = [
    "BenchmarkOutcome",
    "DecisionMetricSummary",
    "IntervalMethod",
    "MetricInterval",
    "RepeatedBenchmarkSummary",
    "bootstrap_interval",
    "percentile_interval",
    "summarize_outcomes",
    "summarize_repeated_runs",
]
