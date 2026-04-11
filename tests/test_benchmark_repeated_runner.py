from __future__ import annotations

import importlib.util
from pathlib import Path

from model_assets.benchmark_cases.loader import BenchmarkPack, load_benchmark_pack
from model_assets.benchmark_cases.runner import evaluate_pack_repeated


def test_evaluate_pack_repeated_records_run_metadata_and_seeds() -> None:
    pack = load_benchmark_pack()
    mini_pack = pack.model_copy(update={"cases": [pack.cases[0]]})

    observed: list[tuple[str, str, int | None, str]] = []

    def evaluator(case, context):
        observed.append((case.case_id, context.run_id, context.seed, context.baseline_id))
        return case.expected_decision, "baseline_approve", "", ""

    repeated = evaluate_pack_repeated(
        mini_pack,
        repeats=3,
        baseline_id="legacy-rules",
        seed=11,
        seed_step=2,
        evaluator=evaluator,
    )

    assert repeated.baseline_id == "legacy-rules"
    assert repeated.repeat_count == 3
    assert repeated.seed_start == 11
    assert repeated.seed_step == 2
    assert repeated.selected_case_ids == [pack.cases[0].case_id]
    assert repeated.total_case_count == 3
    assert repeated.total_match_count == 3
    assert repeated.mean_accuracy == 1.0
    assert repeated.min_accuracy == 1.0
    assert repeated.max_accuracy == 1.0
    assert [run.seed for run in repeated.runs] == [11, 13, 15]
    assert all(run.baseline_id == "legacy-rules" for run in repeated.runs)
    assert all(run.match_count == 1 and run.case_count == 1 for run in repeated.runs)
    assert observed[0][1].startswith(f"{mini_pack.benchmark_name}:legacy-rules:run-001:seed-11")


def test_repeated_benchmark_cli_script_exposes_repeated_run_args_and_metadata() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "run_benchmark_pack_repeated.py").read_text(
        encoding="utf-8"
    )

    assert "--repeats" in script
    assert "--baseline-id" in script
    assert "--seed-step" in script
    assert "benchmark_run_id" in script
    assert "benchmark_seed" in script
    assert "baseline_id" in script
    assert "evaluate_pack_repeated" in script
    assert "summarize_repeated_runs" in script
    assert "build_worst_case_report" in script


def test_build_request_for_case_supports_behavior_and_hybrid_modes() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_benchmark_pack_repeated.py"
    spec = importlib.util.spec_from_file_location("run_benchmark_pack_repeated", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    pack = load_benchmark_pack(Path(__file__).resolve().parents[1] / "model_assets" / "benchmark_cases" / "validation_benchmark_pack.json")
    behavior_case = next(case for case in pack.cases if case.evaluation_mode == "behavior_only")
    hybrid_case = next(case for case in pack.cases if case.evaluation_mode == "hybrid")

    behavior_context = module.BenchmarkRunContext(
        run_id="behavior-run",
        baseline_id="baseline-a",
        seed=7,
        repeat_index=0,
        repeat_count=2,
    )
    hybrid_context = module.BenchmarkRunContext(
        run_id="hybrid-run",
        baseline_id="baseline-b",
        seed=9,
        repeat_index=1,
        repeat_count=2,
    )

    behavior_request = module.build_request_for_case(behavior_case, behavior_context)
    hybrid_request = module.build_request_for_case(hybrid_case, hybrid_context)

    assert behavior_request.evaluation_mode == "behavior_only"
    assert behavior_request.submission is None
    assert behavior_request.conversation
    assert behavior_request.metadata["benchmark_run_id"] == "behavior-run"

    assert hybrid_request.evaluation_mode == "hybrid"
    assert hybrid_request.submission is not None
    assert hybrid_request.submission.github_url == hybrid_case.repo_url
    assert hybrid_request.conversation
    assert hybrid_request.metadata["target_endpoint"] == hybrid_case.target_endpoint
