from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod


# ---------------------------------------------------------------------------
# New SAFE Phase 4: compute_overall + BaseExpert
# ---------------------------------------------------------------------------

def compute_overall(dimension_scores: list[dict]) -> str:
    """Five E-rules in strict priority order."""
    # E-Rule 1: any CORE dimension = HIGH
    if any(d.get("tier") == "CORE" and d.get("level") == "HIGH" for d in dimension_scores):
        return "HIGH"
    # E-Rule 2: any CORE dimension = MEDIUM
    if any(d.get("tier") == "CORE" and d.get("level") == "MEDIUM" for d in dimension_scores):
        return "MEDIUM"
    # E-Rule 3: >=2 IMPORTANT dimensions = HIGH
    important_high = sum(
        1 for d in dimension_scores
        if d.get("tier") == "IMPORTANT" and d.get("level") == "HIGH"
    )
    if important_high >= 2:
        return "HIGH"
    # E-Rule 4: exactly 1 IMPORTANT dimension = HIGH
    if important_high == 1:
        return "MEDIUM"
    # E-Rule 5: all else
    return "LOW"


class BaseExpert(ABC):
    expert_id: str
    dimensions: list[dict]  # each entry: {"name": str, "tier": "CORE"|"IMPORTANT"}

    def execution_mode(self) -> str:
        return os.getenv("EXECUTION_MODE", "llm_api").strip().lower()

    def _mock_result(self) -> dict:
        """All dimensions LOW — used in rules/test mode."""
        return {
            "id": self.expert_id,
            "overall": "LOW",
            "triggered_dimensions": [],
        }

    def _parse_llm_raw(self, raw: str) -> list:
        """Robustly extract a JSON array from raw LLM output."""
        raw = raw.strip()
        # Strip markdown code fences
        if "```" in raw:
            first = raw.find("```")
            last = raw.rfind("```")
            if first != last:
                raw = raw[first + 3:last].strip()
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()
        # Locate the JSON array
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        try:
            items = json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            return []
        # Normalise each item's required enum fields
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("level") not in ("HIGH", "MEDIUM", "LOW"):
                item["level"] = "LOW"
            if item.get("evidence_quality") not in ("Strong", "Partial", "Weak", "NA"):
                item["evidence_quality"] = "Partial"
        return items

    @abstractmethod
    def assess(self, evidence_bundle: dict) -> dict:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Legacy ExpertModule — deprecated (Phase 3 and earlier), kept for reference
# ---------------------------------------------------------------------------

from app.config import EXPERT_EXECUTION_MODE  # noqa: E402
from app.schemas import EvaluationRequest, ExpertVerdict  # noqa: E402
from app.slm.base import SLMRunner  # noqa: E402


class ExpertModule(ABC):
    name: str

    def __init__(self, runner: SLMRunner | None = None):
        self.runner = runner

    def configured_execution_mode(self) -> str:
        return os.getenv("EXPERT_EXECUTION_MODE", EXPERT_EXECUTION_MODE).strip().lower()

    def _should_use_slm(self) -> bool:
        return self.configured_execution_mode() in {"slm", "hybrid"} and self.runner is not None

    def _runner_backend(self) -> str:
        if self.runner is None:
            return "rules"
        return str(self.runner.describe().get("backend", "slm"))

    def _mark_execution(
        self,
        verdict: ExpertVerdict,
        *,
        execution_path: str,
        fallback_reason: str = "",
    ) -> ExpertVerdict:
        evidence = dict(verdict.evidence)
        evidence["execution_path"] = execution_path
        evidence["configured_backend"] = self._runner_backend()
        if fallback_reason:
            evidence["fallback_reason"] = fallback_reason
        return verdict.model_copy(update={"evidence": evidence})

    @abstractmethod
    def assess(self, request: EvaluationRequest) -> ExpertVerdict:
        raise NotImplementedError
