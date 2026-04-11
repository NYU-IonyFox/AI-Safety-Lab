from __future__ import annotations

import math

from model_assets.benchmark_cases.metrics import (
    BenchmarkOutcome,
    bootstrap_interval,
    percentile_interval,
    summarize_outcomes,
    summarize_repeated_runs,
)


def test_summarize_outcomes_computes_core_decision_rates() -> None:
    summary = summarize_outcomes(
        [
            BenchmarkOutcome("case-1", "APPROVE", "APPROVE", slice_name="repo", baseline_name="baseline-a"),
            BenchmarkOutcome("case-2", "REVIEW", "APPROVE", slice_name="repo", baseline_name="baseline-a"),
            BenchmarkOutcome("case-3", "REJECT", "REJECT", slice_name="behavior", baseline_name="baseline-a"),
            BenchmarkOutcome("case-4", "APPROVE", "REJECT", slice_name="behavior", baseline_name="baseline-a"),
            BenchmarkOutcome("case-5", "REVIEW", "REVIEW", slice_name="behavior", baseline_name="baseline-a"),
            BenchmarkOutcome("case-6", "APPROVE", None, slice_name="behavior", baseline_name="baseline-a", error="boom"),
        ],
        confidence_level=1.0,
        interval_method="percentile",
    )

    assert summary.n_observations == 6
    assert summary.n_scored == 5
    assert summary.n_errors == 1
    assert math.isclose(summary.accuracy.estimate, 3 / 5)
    assert math.isclose(summary.false_approve_rate.estimate, 1 / 5)
    assert math.isclose(summary.false_reject_rate.estimate, 1 / 5)
    assert math.isclose(summary.review_rate.estimate, 1 / 5)
    assert math.isclose(summary.coverage_rate.estimate, 5 / 6)
    assert math.isclose(summary.error_rate.estimate, 1 / 6)
    assert summary.accuracy.lower == 0.0
    assert summary.accuracy.upper == 1.0


def test_bootstrap_interval_is_deterministic_with_seed() -> None:
    first = bootstrap_interval([0.1, 0.4, 0.9, 1.0], confidence_level=0.9, n_resamples=256, seed=42)
    second = bootstrap_interval([0.1, 0.4, 0.9, 1.0], confidence_level=0.9, n_resamples=256, seed=42)

    assert first == second
    assert first.method == "bootstrap"
    assert first.lower <= first.estimate <= first.upper


def test_percentile_interval_tracks_sample_extremes_at_full_coverage() -> None:
    interval = percentile_interval([0.25, 0.5, 0.75], confidence_level=1.0)

    assert math.isclose(interval.estimate, 0.5)
    assert math.isclose(interval.lower, 0.25)
    assert math.isclose(interval.upper, 0.75)
    assert interval.method == "percentile"


def test_summarize_repeated_runs_groups_by_slice_and_baseline() -> None:
    repeated = summarize_repeated_runs(
        [
            [
                BenchmarkOutcome("repo-a", "APPROVE", "APPROVE", slice_name="repo", baseline_name="baseline-a"),
                BenchmarkOutcome("repo-b", "REJECT", "APPROVE", slice_name="repo", baseline_name="baseline-a"),
                BenchmarkOutcome("beh-a", "REVIEW", "REVIEW", slice_name="behavior", baseline_name="baseline-a"),
            ],
            [
                BenchmarkOutcome("repo-a", "APPROVE", "APPROVE", slice_name="repo", baseline_name="baseline-a"),
                BenchmarkOutcome("repo-b", "REJECT", "REJECT", slice_name="repo", baseline_name="baseline-a"),
                BenchmarkOutcome("beh-a", "REVIEW", "APPROVE", slice_name="behavior", baseline_name="baseline-a"),
            ],
        ],
        confidence_level=1.0,
        interval_method="percentile",
    )

    assert repeated.n_runs == 2
    assert math.isclose(repeated.overall.accuracy.estimate, 2 / 3)
    assert math.isclose(repeated.overall.review_rate.estimate, 1 / 6)
    assert math.isclose(repeated.overall.false_approve_rate.estimate, 1 / 3)
    assert repeated.overall.coverage_rate.estimate == 1.0

    assert set(repeated.by_group) == {"slice=behavior|baseline=baseline-a", "slice=repo|baseline=baseline-a"}

    repo_summary = repeated.by_group["slice=repo|baseline=baseline-a"]
    behavior_summary = repeated.by_group["slice=behavior|baseline=baseline-a"]
    assert math.isclose(repo_summary.accuracy.estimate, 3 / 4)
    assert math.isclose(behavior_summary.accuracy.estimate, 1 / 2)
    assert math.isclose(repo_summary.coverage_rate.estimate, 1.0)
    assert math.isclose(behavior_summary.review_rate.estimate, 1 / 2)
