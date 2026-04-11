from abc import ABC, abstractmethod
from typing import Any


class SLMRunner(ABC):
    backend_name = "unknown"

    @abstractmethod
    def complete_json(
        self,
        task: str,
        payload: dict[str, Any],
        *,
        system_prompt: str = "",
        response_contract: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def describe(self) -> dict[str, str]:
        return {"backend": self.backend_name}
