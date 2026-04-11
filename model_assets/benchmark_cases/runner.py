from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .loader import BenchmarkCase, BenchmarkPack, pack_summary


@dataclass(slots=True)
class BenchmarkRunResult:
    case_id: str
    title: str
    expected_decision: str
    actual_decision: str | None
    match: bool
    decision_rule_triggered: str = ""
    error: str = ""
    report_path: str = ""
    archive_path: str = ""


def inspect_pack(pack: BenchmarkPack) -> dict[str, Any]:
    summary = pack_summary(pack)
    summaries = []
    for case in pack.cases:
        summaries.append(
            {
                "case_id": case.case_id,
                "title": case.title,
                "repo_url": case.repo_url,
                "expected_decision": case.expected_decision,
                "category": case.category,
                "tags": list(case.benchmark_tags),
            }
        )
    return {"summary": summary, "cases": summaries}


def evaluate_pack(
    pack: BenchmarkPack,
    *,
    case_ids: Iterable[str] | None = None,
    evaluator: Callable[[BenchmarkCase], tuple[str, str, str, str]] | None = None,
) -> list[BenchmarkRunResult]:
    selected = {case_id for case_id in case_ids} if case_ids is not None else None
    if evaluator is None:
        raise RuntimeError("evaluate_pack requires an evaluator callback")
    results: list[BenchmarkRunResult] = []

    for case in pack.cases:
        if selected is not None and case.case_id not in selected:
            continue

        try:
            actual_decision, decision_rule_triggered, report_path, archive_path = evaluator(case)
            results.append(
                BenchmarkRunResult(
                    case_id=case.case_id,
                    title=case.title,
                    expected_decision=case.expected_decision,
                    actual_decision=actual_decision,
                    match=actual_decision == case.expected_decision,
                    decision_rule_triggered=decision_rule_triggered,
                    report_path=report_path,
                    archive_path=archive_path,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                BenchmarkRunResult(
                    case_id=case.case_id,
                    title=case.title,
                    expected_decision=case.expected_decision,
                    actual_decision=None,
                    match=False,
                    error=str(exc),
                )
            )

    return results


__all__ = ["BenchmarkRunResult", "evaluate_pack", "inspect_pack"]
