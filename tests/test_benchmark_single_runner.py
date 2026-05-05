from __future__ import annotations

import importlib.util
from pathlib import Path

from model_assets.benchmark_cases.loader import load_benchmark_pack, validation_pack_path


def test_single_benchmark_runner_builds_mode_aware_requests() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_benchmark_pack.py"
    spec = importlib.util.spec_from_file_location("run_benchmark_pack", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    pack = load_benchmark_pack(validation_pack_path())
    repo_case = next(case for case in pack.cases if case.evaluation_mode == "repository_only")
    behavior_case = next(case for case in pack.cases if case.evaluation_mode == "behavior_only")
    hybrid_case = next(case for case in pack.cases if case.evaluation_mode == "hybrid")

    repo_request = module.build_request_for_case(repo_case)
    behavior_request = module.build_request_for_case(behavior_case)
    hybrid_request = module.build_request_for_case(hybrid_case)

    assert repo_request.evaluation_mode == "repository_only"
    assert repo_request.submission is not None
    assert repo_request.conversation == []

    assert behavior_request.evaluation_mode == "behavior_only"
    assert behavior_request.submission is None
    assert len(behavior_request.conversation) == len(behavior_case.transcript)
    assert behavior_request.metadata["benchmark_case_id"] == behavior_case.case_id

    assert hybrid_request.evaluation_mode == "hybrid"
    assert hybrid_request.submission is not None
    assert hybrid_request.submission.github_url == hybrid_case.repo_url
    assert len(hybrid_request.conversation) == len(hybrid_case.transcript)
    assert hybrid_request.metadata["target_endpoint"] == hybrid_case.target_endpoint


def test_single_benchmark_runner_cli_mentions_evaluate_mode() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "run_benchmark_pack.py").read_text(encoding="utf-8")
    assert "evaluation_mode" in script
    assert "build_request_for_case" in script
