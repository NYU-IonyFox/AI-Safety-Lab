from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.slm.factory import get_slm_runner
from app.slm.local_hf_runner import LocalHFRunner
from app.slm.local_http_runner import LocalHTTPRunner
from app.slm.mock_runner import MockSLMRunner


def test_factory_default_is_local_hf(monkeypatch) -> None:
    monkeypatch.delenv("SLM_BACKEND", raising=False)
    monkeypatch.delenv("LOCAL_SLM_MODE", raising=False)
    assert isinstance(get_slm_runner(), LocalHFRunner)


def test_factory_local_http_mode(monkeypatch) -> None:
    monkeypatch.setenv("SLM_BACKEND", "local")
    monkeypatch.setenv("LOCAL_SLM_MODE", "http")
    assert isinstance(get_slm_runner(), LocalHTTPRunner)


def test_factory_local_hf_mode(monkeypatch) -> None:
    monkeypatch.setenv("SLM_BACKEND", "local")
    monkeypatch.setenv("LOCAL_SLM_MODE", "hf")
    assert isinstance(get_slm_runner(), LocalHFRunner)


def test_factory_explicit_http_backend(monkeypatch) -> None:
    monkeypatch.setenv("SLM_BACKEND", "local_http")
    assert isinstance(get_slm_runner(), LocalHTTPRunner)


def test_local_hf_runner_requires_model_id_at_runtime(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_HF_MODEL_ID", "")
    runner = LocalHFRunner()
    with pytest.raises(RuntimeError, match="LOCAL_HF_MODEL_ID is required"):
        runner.complete_json(task="team1_policy_expert", payload={"foo": "bar"})


def test_local_hf_runner_surfaces_missing_dependency_hint(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_HF_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
    runner = LocalHFRunner()

    def _raise_missing() -> tuple[object, object, object]:
        raise ModuleNotFoundError("No module named 'transformers'")

    monkeypatch.setattr(runner, "_import_dependencies", _raise_missing)
    with pytest.raises(RuntimeError, match='pip install -e "\\.\\[local-hf\\]"'):
        runner.complete_json(task="team2_redteam_expert", payload={"foo": "bar"})


def test_local_hf_runner_parses_and_normalizes_generated_json_without_model_load(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_HF_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
    runner = LocalHFRunner()
    monkeypatch.setattr(runner, "_ensure_runtime", lambda: None)
    monkeypatch.setattr(
        runner,
        "_generate_response_text",
        lambda task, payload, system_prompt="", response_contract=None: """```json
{"risk_score": 0.73, "confidence": 0.66, "critical": false, "risk_tier": "high", "summary": "ok", "findings": ["a"], "evaluation_status": "success"}
```""",
    )

    result = runner.complete_json(task="team3_risk_expert", payload={"foo": "bar"})
    assert result["risk_score"] == 0.73
    assert result["confidence"] == 0.66
    assert result["critical"] is False
    assert result["risk_tier"] == "HIGH"
    assert result["summary"] == "ok"
    assert result["findings"] == ["a"]
    assert result["evaluation_status"] == "success"
    assert result["evidence"]["service"] == "local_hf"


def test_local_hf_runner_warmup_surfaces_runtime_metadata(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_HF_MODEL_ID", "google/gemma-3-270m-it")
    runner = LocalHFRunner()
    monkeypatch.setattr(runner, "_ensure_runtime", lambda: None)
    runner._runtime_device = "cuda"

    assert runner.warmup() == {
        "backend": "local_hf",
        "model_id": "google/gemma-3-270m-it",
        "runtime_device": "cuda",
    }


def test_local_hf_runner_uses_device_map_auto_for_cuda(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_HF_DEVICE_MAP", "auto")
    runner = LocalHFRunner()

    kwargs = runner._resolve_model_load_kwargs(torch_dtype="fp16", runtime_device="cuda")

    assert kwargs == {"torch_dtype": "fp16", "device_map": "auto"}


def test_local_hf_runner_falls_back_to_plain_tokenizer_when_no_chat_template() -> None:
    runner = LocalHFRunner()

    class PlainTokenizer:
        def __call__(self, prompt: str, return_tensors: str, truncation: bool) -> dict[str, str]:
            assert prompt == "user prompt"
            assert return_tensors == "pt"
            assert truncation is True
            return {"input_ids": "ok"}

    result = runner._tokenize_prompt(PlainTokenizer(), "system prompt", "user prompt")
    assert result == {"input_ids": "ok"}


def test_local_hf_runner_prefers_chat_template_when_available() -> None:
    runner = LocalHFRunner()

    class ChatTokenizer:
        def apply_chat_template(
            self,
            messages,
            tokenize: bool,
            add_generation_prompt: bool,
            return_tensors: str,
            truncation: bool,
        ) -> dict[str, object]:
            assert messages == [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ]
            assert tokenize is True
            assert add_generation_prompt is True
            assert return_tensors == "pt"
            assert truncation is True
            return {"input_ids": [1, 2, 3]}

    result = runner._tokenize_prompt(ChatTokenizer(), "system prompt", "user prompt")
    assert result == {"input_ids": [1, 2, 3]}


def test_local_hf_runner_clears_sampling_flags_for_greedy_decode(monkeypatch) -> None:
    runner = LocalHFRunner()
    runner.temperature = 0.0
    runner.top_p = 1.0

    class FakeTensor:
        def __init__(self, values):
            self.values = values

        def to(self, _device: str):
            return self

        def __getitem__(self, item):
            return self.values[item]

        @property
        def shape(self):
            if isinstance(self.values, list) and self.values and isinstance(self.values[0], list):
                return (len(self.values), len(self.values[0]))
            return (len(self.values),)

    class FakeTokenizer:
        eos_token_id = 1
        pad_token_id = 1

        def __call__(self, prompt: str, return_tensors: str, truncation: bool):
            return {"input_ids": FakeTensor([[10, 11]]), "attention_mask": FakeTensor([[1, 1]])}

        def decode(self, _ids, skip_special_tokens: bool) -> str:
            return '{"risk_score": 0.5, "confidence": 0.5, "critical": false, "risk_tier": "LOW", "summary": "ok", "findings": [], "evaluation_status": "success"}'

    captured: dict[str, object] = {}

    class FakeModel:
        def __init__(self) -> None:
            self.generation_config = SimpleNamespace(temperature=0.7, top_p=0.9, top_k=50)

        def generate(self, **kwargs):
            captured.update(kwargs)
            return [FakeTensor([10, 11, 12, 13])]

    class NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    runner._tokenizer = FakeTokenizer()
    runner._model = FakeModel()
    runner._torch = SimpleNamespace(no_grad=lambda: NoGrad())
    runner._runtime_device = "cpu"
    runner._runtime_ready = True

    runner.complete_json(task="team1_policy_expert", payload={"foo": "bar"})

    generation_config = captured["generation_config"]
    assert captured["do_sample"] is False
    assert generation_config.temperature is None
    assert generation_config.top_p is None
    assert generation_config.top_k is None
