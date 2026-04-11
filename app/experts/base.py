import os
from abc import ABC, abstractmethod

from app.config import EXPERT_EXECUTION_MODE
from app.schemas import EvaluationRequest, ExpertVerdict
from app.slm.base import SLMRunner


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
