from __future__ import annotations

from pathlib import Path


def test_bootstrap_script_defaults_to_qwen_and_lists_public_presets() -> None:
    script = Path("scripts/bootstrap_local_slm.sh").read_text(encoding="utf-8")

    assert 'MODEL_PRESET="${MODEL_PRESET:-qwen2.5-0.5b}"' in script
    assert "qwen2.5-0.5b" in script
    assert "smollm2-1.7b" in script
    assert "Qwen/Qwen2.5-0.5B-Instruct" in script
    assert "HuggingFaceTB/SmolLM2-1.7B-Instruct" in script
