import os

from app.slm.base import SLMRunner
from app.slm.local_hf_runner import LocalHFRunner
from app.slm.local_http_runner import LocalHTTPRunner
from app.slm.mock_runner import MockSLMRunner


HTTP_BACKENDS = {"gamma4", "local-gamma4", "local_http", "local-http"}


def get_slm_runner() -> SLMRunner:
    backend = os.getenv("SLM_BACKEND", "local").strip().lower()
    if backend in HTTP_BACKENDS:
        return LocalHTTPRunner()
    if backend == "local":
        mode = os.getenv("LOCAL_SLM_MODE", "hf").strip().lower()
        if mode in {"hf", "transformers", "open_weight", "open-weight"}:
            return LocalHFRunner()
        return LocalHTTPRunner()
    return MockSLMRunner()
