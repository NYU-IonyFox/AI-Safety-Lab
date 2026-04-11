from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from model_assets.benchmark_cases.loader import (
    BenchmarkPack,
    default_pack_path,
    load_benchmark_pack,
    pack_summary,
    validation_pack_path,
)


def test_public_benchmark_pack_loads_cleanly() -> None:
    pack = load_benchmark_pack()

    assert isinstance(pack, BenchmarkPack)
    assert len(pack.cases) >= 8
    assert {case.evaluation_mode for case in pack.cases} == {"repository_only"}
    assert {case.expected_decision for case in pack.cases} == {"APPROVE", "REVIEW", "REJECT"}
    assert all(case.slice_labels == [] for case in pack.cases)
    assert all(case.baseline_metadata is None for case in pack.cases)

    case_ids = [case.case_id for case in pack.cases]
    assert len(case_ids) == len(set(case_ids))

    summary = pack_summary(pack)
    assert summary["case_count"] == len(pack.cases)
    assert summary["decision_counts"]["APPROVE"] >= 1
    assert summary["decision_counts"]["REVIEW"] >= 1
    assert summary["decision_counts"]["REJECT"] >= 1
    assert summary["mode_counts"]["repository_only"] == len(pack.cases)
    assert summary["mode_counts"]["behavior_only"] == 0
    assert summary["mode_counts"]["hybrid"] == 0
    assert summary["slice_labels"] == []


def test_validation_benchmark_pack_loads_multi_mode_with_baselines() -> None:
    pack = load_benchmark_pack(validation_pack_path())

    assert isinstance(pack, BenchmarkPack)
    assert {case.evaluation_mode for case in pack.cases} == {"repository_only", "behavior_only", "hybrid"}
    assert {case.expected_decision for case in pack.cases} == {"APPROVE", "REVIEW", "REJECT"}
    assert all(case.slice_labels for case in pack.cases)
    assert all(case.baseline_metadata is not None for case in pack.cases)
    assert any(case.transcript for case in pack.cases if case.evaluation_mode != "repository_only")

    summary = pack_summary(pack)
    assert summary["case_count"] == 6
    assert summary["mode_counts"]["repository_only"] == 2
    assert summary["mode_counts"]["behavior_only"] == 2
    assert summary["mode_counts"]["hybrid"] == 2
    assert summary["baseline_kinds"] == ["behavior_probe", "hybrid_assurance", "repository_static"]
    assert "slice:behavior:multilingual" in summary["slice_labels"]
    assert "slice:hybrid:discordant" in summary["slice_labels"]
    assert summary["baseline_decision_counts"]["APPROVE"] >= 1
    assert summary["baseline_decision_counts"]["REVIEW"] >= 1
    assert summary["baseline_decision_counts"]["REJECT"] >= 1


def test_benchmark_pack_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = json.loads(default_pack_path().read_text(encoding="utf-8"))
    payload["cases"][1]["case_id"] = payload["cases"][0]["case_id"]
    temp_pack = tmp_path / "broken_pack.json"
    temp_pack.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_benchmark_pack(temp_pack)


def test_validation_pack_rejects_mode_payload_mismatch(tmp_path: Path) -> None:
    payload = json.loads(validation_pack_path().read_text(encoding="utf-8"))
    for case in payload["cases"]:
        if case["evaluation_mode"] == "behavior_only":
            case["transcript"] = []
            break
    temp_pack = tmp_path / "broken_validation_pack.json"
    temp_pack.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="transcript is required for behavior_only"):
        load_benchmark_pack(temp_pack)
