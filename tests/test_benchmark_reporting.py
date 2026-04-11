from __future__ import annotations

from types import SimpleNamespace

from model_assets.benchmark_cases.loader import load_benchmark_pack, validation_pack_path
from model_assets.benchmark_cases.reporting import build_worst_case_report


def test_build_worst_case_report_surfaces_critical_false_approves_and_instability() -> None:
    pack = load_benchmark_pack(validation_pack_path())
    case_lookup = {case.case_id: case for case in pack.cases}

    runs = [
        SimpleNamespace(
            run_id="run-1",
            baseline_id="current",
            results=[
                SimpleNamespace(
                    case_id="behavior-only-secret-leak",
                    expected_decision="REJECT",
                    actual_decision="APPROVE",
                    error="",
                ),
                SimpleNamespace(
                    case_id="hybrid-discordant-repo-risk",
                    expected_decision="REVIEW",
                    actual_decision="REJECT",
                    error="",
                ),
            ],
        ),
        SimpleNamespace(
            run_id="run-2",
            baseline_id="current",
            results=[
                SimpleNamespace(
                    case_id="behavior-only-secret-leak",
                    expected_decision="REJECT",
                    actual_decision="REJECT",
                    error="",
                ),
                SimpleNamespace(
                    case_id="hybrid-discordant-repo-risk",
                    expected_decision="REVIEW",
                    actual_decision="REVIEW",
                    error="",
                ),
            ],
        ),
    ]

    report = build_worst_case_report(runs, case_lookup=case_lookup, top_n=3)

    assert report.total_runs == 2
    assert report.total_observations == 4
    assert report.worst_slices
    assert report.critical_failures
    assert report.most_unstable_cases

    critical = report.critical_failures[0]
    assert critical.case_id == "behavior-only-secret-leak"
    assert critical.false_approve_count == 1
    assert critical.likely_failure_mode == "unsafe_false_approve"

    unstable_ids = {item.case_id for item in report.most_unstable_cases}
    assert "hybrid-discordant-repo-risk" in unstable_ids
