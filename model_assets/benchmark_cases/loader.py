from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


Decision = Literal["APPROVE", "REVIEW", "REJECT"]


class BenchmarkCase(BaseModel):
    case_id: str
    title: str
    repo_url: str
    source_type: Literal["github_url"] = "github_url"
    category: str
    agent_name: str
    description: str
    domain: str = "Other"
    capabilities: list[str] = Field(default_factory=list)
    high_autonomy: bool = False
    selected_policies: list[str] = Field(default_factory=lambda: ["eu_ai_act", "us_nist", "iso", "unesco"])
    expected_decision: Decision
    expected_rationale: str
    evidence_targets: list[str] = Field(default_factory=list)
    likely_false_positives: list[str] = Field(default_factory=list)
    likely_false_negatives: list[str] = Field(default_factory=list)
    benchmark_tags: list[str] = Field(default_factory=list)
    labeler: str
    labeled_at: str
    label_confidence: float = Field(ge=0.0, le=1.0)
    label_basis: str = "Static review of the public repository README and visible code surface."

    @field_validator("repo_url")
    @classmethod
    def _repo_url_must_be_public_github(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
            raise ValueError("repo_url must be a public https://github.com/... URL")
        return value.rstrip("/")

    @field_validator("evidence_targets")
    @classmethod
    def _evidence_targets_required(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("evidence_targets must contain at least one item")
        return value


class BenchmarkPack(BaseModel):
    benchmark_name: str
    version: str
    created_at: str
    description: str
    label_method: str
    cases: list[BenchmarkCase]

    @model_validator(mode="after")
    def _validate_cases(self) -> "BenchmarkPack":
        if not self.cases:
            raise ValueError("benchmark pack must contain at least one case")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("benchmark case ids must be unique")
        return self


def default_pack_path() -> Path:
    return Path(__file__).with_name("public_repo_benchmark_pack.json")


def load_benchmark_pack(path: str | Path | None = None) -> BenchmarkPack:
    pack_path = Path(path) if path is not None else default_pack_path()
    payload = json.loads(pack_path.read_text(encoding="utf-8"))
    return BenchmarkPack.model_validate(payload)


def pack_summary(pack: BenchmarkPack) -> dict[str, object]:
    decision_counts: dict[str, int] = {"APPROVE": 0, "REVIEW": 0, "REJECT": 0}
    for case in pack.cases:
        decision_counts[case.expected_decision] += 1
    return {
        "benchmark_name": pack.benchmark_name,
        "version": pack.version,
        "case_count": len(pack.cases),
        "decision_counts": decision_counts,
        "categories": sorted({case.category for case in pack.cases}),
    }


__all__ = [
    "BenchmarkCase",
    "BenchmarkPack",
    "ValidationError",
    "default_pack_path",
    "load_benchmark_pack",
    "pack_summary",
]
