from __future__ import annotations

import os
import random
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


@dataclass(slots=True)
class BenchmarkRunContext:
    run_id: str
    baseline_id: str
    seed: int | None
    repeat_index: int
    repeat_count: int


@dataclass(slots=True)
class BenchmarkRepeatedRunResult:
    run_id: str
    baseline_id: str
    seed: int | None
    repeat_index: int
    repeat_count: int
    match_count: int
    case_count: int
    accuracy: float
    results: list[BenchmarkRunResult]


@dataclass(slots=True)
class BenchmarkRepeatedPackResult:
    pack: dict[str, Any]
    baseline_id: str
    repeat_count: int
    seed_start: int | None
    seed_step: int
    selected_case_ids: list[str]
    total_case_count: int
    total_match_count: int
    mean_accuracy: float
    min_accuracy: float
    max_accuracy: float
    runs: list[BenchmarkRepeatedRunResult]


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


def seed_everything(seed: int | None) -> None:
    if seed is None:
        return

    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)

    try:
        import numpy as np  # type: ignore
    except ModuleNotFoundError:
        np = None
    if np is not None:
        np.random.seed(seed)

    try:
        import torch
    except ModuleNotFoundError:
        return

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _build_run_id(pack_name: str, baseline_id: str, repeat_index: int, seed: int | None) -> str:
    safe_baseline = baseline_id.strip() or "baseline"
    seed_part = "none" if seed is None else str(seed)
    return f"{pack_name}:{safe_baseline}:run-{repeat_index:03d}:seed-{seed_part}"


def _accuracy(results: list[BenchmarkRunResult]) -> float:
    if not results:
        return 0.0
    return sum(1 for result in results if result.match) / len(results)


def evaluate_pack_repeated(
    pack: BenchmarkPack,
    *,
    repeats: int,
    baseline_id: str = "current",
    seed: int | None = None,
    seed_step: int = 1,
    case_ids: Iterable[str] | None = None,
    evaluator: Callable[[BenchmarkCase, BenchmarkRunContext], tuple[str, str, str, str]] | None = None,
) -> BenchmarkRepeatedPackResult:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if evaluator is None:
        raise RuntimeError("evaluate_pack_repeated requires an evaluator callback")

    selected_case_ids = list(dict.fromkeys(case_ids)) if case_ids is not None else [case.case_id for case in pack.cases]
    runs: list[BenchmarkRepeatedRunResult] = []
    run_accuracies: list[float] = []
    total_match_count = 0
    total_case_count = 0

    for repeat_index in range(repeats):
        run_seed = None if seed is None else seed + (repeat_index * seed_step)
        run_id = _build_run_id(pack.benchmark_name, baseline_id, repeat_index + 1, run_seed)
        seed_everything(run_seed)
        context = BenchmarkRunContext(
            run_id=run_id,
            baseline_id=baseline_id,
            seed=run_seed,
            repeat_index=repeat_index,
            repeat_count=repeats,
        )

        def _evaluate_case(case: BenchmarkCase) -> tuple[str, str, str, str]:
            return evaluator(case, context)

        run_results = evaluate_pack(pack, case_ids=selected_case_ids, evaluator=_evaluate_case)
        match_count = sum(1 for result in run_results if result.match)
        case_count = len(run_results)
        accuracy = _accuracy(run_results)
        total_match_count += match_count
        total_case_count += case_count
        run_accuracies.append(accuracy)
        runs.append(
            BenchmarkRepeatedRunResult(
                run_id=run_id,
                baseline_id=baseline_id,
                seed=run_seed,
                repeat_index=repeat_index,
                repeat_count=repeats,
                match_count=match_count,
                case_count=case_count,
                accuracy=accuracy,
                results=run_results,
            )
        )

    mean_accuracy = sum(run_accuracies) / len(run_accuracies) if run_accuracies else 0.0
    min_accuracy = min(run_accuracies) if run_accuracies else 0.0
    max_accuracy = max(run_accuracies) if run_accuracies else 0.0

    return BenchmarkRepeatedPackResult(
        pack=pack_summary(pack),
        baseline_id=baseline_id,
        repeat_count=repeats,
        seed_start=seed,
        seed_step=seed_step,
        selected_case_ids=selected_case_ids,
        total_case_count=total_case_count,
        total_match_count=total_match_count,
        mean_accuracy=mean_accuracy,
        min_accuracy=min_accuracy,
        max_accuracy=max_accuracy,
        runs=runs,
    )


__all__ = [
    "BenchmarkRepeatedPackResult",
    "BenchmarkRepeatedRunResult",
    "BenchmarkRunContext",
    "BenchmarkRunResult",
    "evaluate_pack",
    "evaluate_pack_repeated",
    "inspect_pack",
    "seed_everything",
]
