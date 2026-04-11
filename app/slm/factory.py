import os

from app.slm.base import SLMRunner
from app.slm.local_http_runner import LocalHTTPRunner
from app.slm.mock_runner import MockSLMRunner


LOCAL_BACKENDS = {"local", "gamma4", "local-gamma4", "local_http", "local-http"}


def get_slm_runner() -> SLMRunner:
    backend = os.getenv("SLM_BACKEND", "mock").strip().lower()
    if backend in LOCAL_BACKENDS:
        return LocalHTTPRunner()
    return MockSLMRunner()
