from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from model_assets.benchmark_cases.loader import BenchmarkPack, default_pack_path, load_benchmark_pack, pack_summary


def test_public_benchmark_pack_loads_cleanly() -> None:
    pack = load_benchmark_pack()

    assert isinstance(pack, BenchmarkPack)
    assert len(pack.cases) >= 8
    assert {case.expected_decision for case in pack.cases} == {"APPROVE", "REVIEW", "REJECT"}

    case_ids = [case.case_id for case in pack.cases]
    assert len(case_ids) == len(set(case_ids))

    summary = pack_summary(pack)
    assert summary["case_count"] == len(pack.cases)
    assert summary["decision_counts"]["APPROVE"] >= 1
    assert summary["decision_counts"]["REVIEW"] >= 1
    assert summary["decision_counts"]["REJECT"] >= 1


def test_benchmark_pack_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = json.loads(default_pack_path().read_text(encoding="utf-8"))
    payload["cases"][1]["case_id"] = payload["cases"][0]["case_id"]
    temp_pack = tmp_path / "broken_pack.json"
    temp_pack.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_benchmark_pack(temp_pack)

