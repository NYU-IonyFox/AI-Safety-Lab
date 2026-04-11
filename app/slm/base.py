from abc import ABC, abstractmethod
from typing import Any


class SLMRunner(ABC):
    @abstractmethod
    def complete_json(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

