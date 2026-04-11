from abc import ABC, abstractmethod

from app.config import EXPERT_EXECUTION_MODE
from app.schemas import EvaluationRequest, ExpertVerdict
from app.slm.base import SLMRunner


class ExpertModule(ABC):
    name: str
    
    def __init__(self, runner: SLMRunner | None = None):
        self.runner = runner

    def _should_use_slm(self) -> bool:
        return EXPERT_EXECUTION_MODE in {"slm", "hybrid"} and self.runner is not None

    @abstractmethod
    def assess(self, request: EvaluationRequest) -> ExpertVerdict:
        raise NotImplementedError
