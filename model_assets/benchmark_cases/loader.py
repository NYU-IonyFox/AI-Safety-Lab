from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


Decision = Literal["APPROVE", "REVIEW", "REJECT"]
EvaluationMode = Literal["repository_only", "behavior_only", "hybrid"]


class BenchmarkTranscriptTurn(BaseModel):
    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str
    language: str | None = None


class BenchmarkBaselineMetadata(BaseModel):
    baseline_name: str
    baseline_kind: Literal["repository_static", "behavior_probe", "hybrid_assurance"] = "repository_static"
    baseline_version: str = "1.0.0"
    baseline_decision: Decision | None = None
    baseline_source: str = ""
    baseline_notes: str = ""


class BenchmarkCase(BaseModel):
    case_id: str
    title: str
    evaluation_mode: EvaluationMode = "repository_only"
    repo_url: str | None = None
    source_type: Literal["github_url", "behavior_transcript", "hybrid"] = "github_url"
    category: str
    agent_name: str
    description: str
    domain: str = "Other"
    capabilities: list[str] = Field(default_factory=list)
    high_autonomy: bool = False
    selected_policies: list[str] = Field(default_factory=lambda: ["eu_ai_act", "us_nist", "iso", "unesco"])
    expected_decision: Decision
    expected_rationale: str
    transcript: list[BenchmarkTranscriptTurn] = Field(default_factory=list)
    target_endpoint: str = ""
    baseline_metadata: BenchmarkBaselineMetadata | None = None
    slice_labels: list[str] = Field(default_factory=list)
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
    def _repo_url_must_be_public_github(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
            raise ValueError("repo_url must be a public https://github.com/... URL")
        return value.rstrip("/")

    @model_validator(mode="after")
    def _validate_mode_and_payload(self) -> "BenchmarkCase":
        expected_source_type = {
            "repository_only": "github_url",
            "behavior_only": "behavior_transcript",
            "hybrid": "hybrid",
        }[self.evaluation_mode]
        if self.source_type != expected_source_type:
            raise ValueError(
                f"source_type must be {expected_source_type!r} when evaluation_mode is {self.evaluation_mode!r}"
            )
        if self.evaluation_mode in {"repository_only", "hybrid"} and not self.repo_url:
            raise ValueError(f"repo_url is required for {self.evaluation_mode} benchmark cases")
        if self.evaluation_mode in {"behavior_only", "hybrid"} and not self.transcript:
            raise ValueError(f"transcript is required for {self.evaluation_mode} benchmark cases")
        if self.evaluation_mode == "repository_only" and self.transcript:
            raise ValueError("repository_only benchmark cases must not include transcript turns")
        return self

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


def validation_pack_path() -> Path:
    return Path(__file__).with_name("validation_benchmark_pack.json")


def load_benchmark_pack(path: str | Path | None = None) -> BenchmarkPack:
    pack_path = Path(path) if path is not None else default_pack_path()
    payload = json.loads(pack_path.read_text(encoding="utf-8"))
    return BenchmarkPack.model_validate(payload)


def pack_summary(pack: BenchmarkPack) -> dict[str, object]:
    decision_counts: dict[str, int] = {"APPROVE": 0, "REVIEW": 0, "REJECT": 0}
    mode_counts: dict[str, int] = {"repository_only": 0, "behavior_only": 0, "hybrid": 0}
    slice_labels: set[str] = set()
    baseline_kinds: set[str] = set()
    baseline_decisions: dict[str, int] = {"APPROVE": 0, "REVIEW": 0, "REJECT": 0}
    for case in pack.cases:
        decision_counts[case.expected_decision] += 1
        mode_counts[case.evaluation_mode] += 1
        slice_labels.update(case.slice_labels)
        if case.baseline_metadata is not None:
            baseline_kinds.add(case.baseline_metadata.baseline_kind)
            if case.baseline_metadata.baseline_decision is not None:
                baseline_decisions[case.baseline_metadata.baseline_decision] += 1
    return {
        "benchmark_name": pack.benchmark_name,
        "version": pack.version,
        "case_count": len(pack.cases),
        "decision_counts": decision_counts,
        "mode_counts": mode_counts,
        "categories": sorted({case.category for case in pack.cases}),
        "slice_labels": sorted(slice_labels),
        "baseline_kinds": sorted(baseline_kinds),
        "baseline_decision_counts": baseline_decisions,
    }


__all__ = [
    "BenchmarkBaselineMetadata",
    "BenchmarkCase",
    "BenchmarkPack",
    "BenchmarkTranscriptTurn",
    "ValidationError",
    "default_pack_path",
    "load_benchmark_pack",
    "pack_summary",
    "validation_pack_path",
]
