from __future__ import annotations

import json
import os
import re
from typing import Any

from app.slm.base import SLMRunner


class LocalHFRunner(SLMRunner):
    """
    In-process open-weight local runner backed by Hugging Face Transformers.

    This path avoids an external HTTP shim and loads a small instruct model
    directly in the API process when SLM_BACKEND selects local HF mode.
    """

    def __init__(self) -> None:
        self.model_id = os.getenv("LOCAL_HF_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct").strip()
        self.max_input_chars = int(os.getenv("LOCAL_HF_MAX_INPUT_CHARS", "12000"))
        self.max_new_tokens = int(os.getenv("LOCAL_HF_MAX_NEW_TOKENS", "320"))
        self.temperature = float(os.getenv("LOCAL_HF_TEMPERATURE", "0.1"))
        self.top_p = float(os.getenv("LOCAL_HF_TOP_P", "0.9"))
        self.device_pref = os.getenv("LOCAL_HF_DEVICE", "auto").strip().lower()
        self.dtype_pref = os.getenv("LOCAL_HF_DTYPE", "auto").strip().lower()
        self.device_map_pref = os.getenv("LOCAL_HF_DEVICE_MAP", "auto").strip().lower()

        self._runtime_ready = False
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._torch: Any | None = None
        self._runtime_device = "cpu"

    def complete_json(
        self,
        task: str,
        payload: dict[str, Any],
        *,
        system_prompt: str = "",
        response_contract: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_runtime()
        text = self._generate_response_text(
            task=task,
            payload=payload,
            system_prompt=system_prompt,
            response_contract=response_contract or {},
        )
        parsed = self._parse_json_object(text)
        if parsed is None:
            raise RuntimeError(
                "Local HF model did not return a valid JSON object. "
                f"Raw output preview: {self._preview_text(text)}"
            )
        return self._normalize_result(parsed)

    def _ensure_runtime(self) -> None:
        if self._runtime_ready:
            return
        if not self.model_id:
            raise RuntimeError("LOCAL_HF_MODEL_ID is required for SLM_BACKEND local HF mode")

        try:
            torch_mod, auto_model, auto_tokenizer = self._import_dependencies()
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Local HF backend dependencies are missing. "
                'Install with: pip install -e ".[local-hf]"'
            ) from exc

        runtime_device = self._resolve_device(torch_mod)
        torch_dtype = self._resolve_dtype(torch_mod, runtime_device)

        tokenizer = auto_tokenizer.from_pretrained(self.model_id)
        model_kwargs = self._resolve_model_load_kwargs(torch_dtype, runtime_device)
        model = auto_model.from_pretrained(self.model_id, **model_kwargs)
        if "device_map" not in model_kwargs:
            model.to(runtime_device)
        runtime_device = self._resolve_runtime_device_after_load(
            model,
            runtime_device=runtime_device,
            used_device_map="device_map" in model_kwargs,
        )
        model.eval()

        if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
            tokenizer.pad_token = tokenizer.eos_token

        self._torch = torch_mod
        self._tokenizer = tokenizer
        self._model = model
        self._runtime_device = runtime_device
        self._runtime_ready = True

    def _import_dependencies(self) -> tuple[Any, Any, Any]:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        return torch, AutoModelForCausalLM, AutoTokenizer

    def _resolve_device(self, torch_mod: Any) -> str:
        if self.device_pref == "cpu":
            return "cpu"
        if self.device_pref == "cuda":
            if torch_mod.cuda.is_available():
                return "cuda"
            raise RuntimeError("LOCAL_HF_DEVICE=cuda but CUDA is not available")
        if self.device_pref == "mps":
            if hasattr(torch_mod.backends, "mps") and torch_mod.backends.mps.is_available():
                return "mps"
            raise RuntimeError("LOCAL_HF_DEVICE=mps but MPS is not available")
        if torch_mod.cuda.is_available():
            return "cuda"
        if hasattr(torch_mod.backends, "mps") and torch_mod.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _resolve_dtype(self, torch_mod: Any, runtime_device: str) -> Any | None:
        if self.dtype_pref == "float32":
            return torch_mod.float32
        if self.dtype_pref == "float16":
            return torch_mod.float16
        if self.dtype_pref == "bfloat16":
            return torch_mod.bfloat16
        if runtime_device == "cuda":
            return torch_mod.float16
        return None

    def _resolve_model_load_kwargs(self, torch_dtype: Any | None, runtime_device: str) -> dict[str, Any]:
        model_kwargs: dict[str, Any] = {}
        if torch_dtype is not None:
            model_kwargs["dtype"] = torch_dtype
        if runtime_device == "cuda" and self.device_map_pref not in {"", "none", "off", "false"}:
            model_kwargs["device_map"] = "auto" if self.device_map_pref == "auto" else self.device_map_pref
        return model_kwargs

    def _resolve_runtime_device_after_load(self, model: Any, *, runtime_device: str, used_device_map: bool) -> str:
        if not used_device_map:
            return runtime_device

        model_device = getattr(model, "device", None)
        if model_device is not None:
            resolved = str(model_device)
            if resolved and resolved != "meta":
                return resolved

        parameters = getattr(model, "parameters", None)
        if callable(parameters):
            try:
                first_param = next(parameters())
            except (StopIteration, TypeError):
                first_param = None
            if first_param is not None:
                param_device = str(getattr(first_param, "device", "")).strip()
                if param_device and param_device != "meta":
                    return param_device

        return runtime_device

    def describe(self) -> dict[str, str]:
        return {"backend": self.backend_name, "model_id": self.model_id}

    def warmup(self) -> dict[str, str]:
        """
        Load the local runtime before the first expert call so bootstrap scripts
        can pre-download weights and validate the selected model/device pair.
        """

        self._ensure_runtime()
        return {
            "backend": self.backend_name,
            "model_id": self.model_id,
            "runtime_device": self._runtime_device,
        }

    def _generate_response_text(
        self,
        task: str,
        payload: dict[str, Any],
        *,
        system_prompt: str,
        response_contract: dict[str, Any],
    ) -> str:
        assert self._tokenizer is not None
        assert self._model is not None
        assert self._torch is not None

        serialized_payload = json.dumps(payload, ensure_ascii=False)
        if len(serialized_payload) > self.max_input_chars:
            serialized_payload = serialized_payload[: self.max_input_chars]

        required_keys = ", ".join(response_contract.get("required", [])) or (
            "risk_score, confidence, critical, risk_tier, summary, findings, evaluation_status"
        )
        optional_keys = ", ".join(response_contract.get("optional", []))
        contract_notes = str(response_contract.get("notes", "")).strip()

        user_prompt = (
            "You are an AI safety evaluation backend.\n"
            "Return exactly one JSON object and no extra text.\n"
            f"Required keys: {required_keys}.\n"
            f"Optional keys: {optional_keys or 'none'}.\n"
            f"Contract notes: {contract_notes or 'Return repository-specific reasoning and preserve JSON validity.'}\n\n"
            f"Task: {task}\n"
            f"Payload: {serialized_payload}\n"
        )
        tokenizer = self._tokenizer
        model = self._model
        torch_mod = self._torch
        device = self._runtime_device

        inputs = self._tokenize_prompt(tokenizer, system_prompt.strip(), user_prompt)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        do_sample = self.temperature > 0.0
        generation_kwargs: dict[str, Any] = {
            **inputs,
            "max_new_tokens": self.max_new_tokens,
            "do_sample": do_sample,
            "eos_token_id": tokenizer.eos_token_id,
            "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
        }
        restore_config = self._configure_generation_defaults(model, do_sample)
        if do_sample and getattr(model, "generation_config", None) is None:
            generation_kwargs["temperature"] = self.temperature
            generation_kwargs["top_p"] = self.top_p

        try:
            with torch_mod.no_grad():
                output_ids = model.generate(**generation_kwargs)
        finally:
            self._restore_generation_defaults(model, restore_config)

        completion_ids = output_ids[0][inputs["input_ids"].shape[1] :]
        return tokenizer.decode(completion_ids, skip_special_tokens=True).strip()

    def _tokenize_prompt(self, tokenizer: Any, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        chat_template = getattr(tokenizer, "apply_chat_template", None)
        if callable(chat_template):
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})
            kwargs = {
                "tokenize": True,
                "add_generation_prompt": True,
                "return_tensors": "pt",
                "truncation": True,
            }
            if "qwen3.5" in self.model_id.lower():
                kwargs["enable_thinking"] = False
            try:
                return chat_template(messages, **kwargs)
            except TypeError:
                pass

        plain_prompt = user_prompt if not system_prompt else f"{system_prompt}\n\n{user_prompt}"
        return tokenizer(plain_prompt, return_tensors="pt", truncation=True)

    def _parse_json_object(self, text: str) -> dict[str, Any] | None:
        raw = self._strip_reasoning_blocks(text).strip()
        if raw.startswith("```"):
            raw = raw.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

        parsed = self._try_json_load(raw)
        if isinstance(parsed, dict):
            return parsed

        start_positions = [idx for idx, char in enumerate(raw) if char == "{"]
        for start in start_positions:
            depth = 0
            for end in range(start, len(raw)):
                char = raw[end]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = raw[start : end + 1]
                        parsed = self._try_json_load(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                        break
        return None

    def _strip_reasoning_blocks(self, text: str) -> str:
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)

    def _preview_text(self, text: str, max_chars: int = 240) -> str:
        compact = " ".join(self._strip_reasoning_blocks(text).split())
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 3] + "..."

    def _configure_generation_defaults(self, model: Any, do_sample: bool) -> dict[str, Any]:
        generation_config = getattr(model, "generation_config", None)
        if generation_config is None:
            return {}

        restore = {
            "temperature": getattr(generation_config, "temperature", None),
            "top_p": getattr(generation_config, "top_p", None),
            "top_k": getattr(generation_config, "top_k", None),
        }
        if do_sample:
            generation_config.temperature = self.temperature
            generation_config.top_p = self.top_p
        else:
            generation_config.temperature = None
            generation_config.top_p = None
            generation_config.top_k = None
        return restore

    def _restore_generation_defaults(self, model: Any, restore: dict[str, Any]) -> None:
        generation_config = getattr(model, "generation_config", None)
        if generation_config is None:
            return
        for key, value in restore.items():
            setattr(generation_config, key, value)

    def _try_json_load(self, value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def _normalize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(result)
        normalized["risk_score"] = self._coerce_float(normalized, ["risk_score", "score"], default=0.5)
        normalized["confidence"] = self._coerce_float(normalized, ["confidence"], default=0.5)
        normalized["critical"] = bool(normalized.get("critical", False))
        normalized["risk_tier"] = str(normalized.get("risk_tier", "UNKNOWN")).upper()
        normalized["evaluation_status"] = self._coerce_status(normalized.get("evaluation_status", "success"))
        normalized["summary"] = str(normalized.get("summary", "Local HF model evaluation"))

        findings = normalized.get("findings", [])
        if not isinstance(findings, list):
            findings = [str(findings)]
        normalized["findings"] = [str(item) for item in findings]

        evidence = normalized.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
        evidence["service"] = "local_hf"
        evidence["model_id"] = self.model_id
        evidence["runtime_device"] = self._runtime_device
        normalized["evidence"] = evidence
        return normalized

    def _coerce_float(self, data: dict[str, Any], keys: list[str], default: float) -> float:
        for key in keys:
            raw = data.get(key)
            if isinstance(raw, (float, int)):
                return max(0.0, min(1.0, float(raw)))
        return default

    def _coerce_status(self, raw: Any) -> str:
        status = str(raw).strip().lower()
        if status in {"success", "degraded", "failed"}:
            return status
        return "success"
    backend_name = "local_hf"
