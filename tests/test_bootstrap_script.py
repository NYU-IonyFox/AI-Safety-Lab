from __future__ import annotations

from pathlib import Path


def test_bootstrap_script_defaults_to_qwen35_and_lists_only_larger_presets() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_local_slm.sh").read_text(
        encoding="utf-8"
    )

    assert 'MODEL_PRESET="${MODEL_PRESET:-qwen3.5-4b}"' in script
    assert "qwen2.5-3b" in script
    assert "qwen3.5-4b" in script
    assert "gemma3-4b-fp16" in script
    assert "Qwen/Qwen2.5-3B-Instruct" in script
    assert "Qwen/Qwen3.5-4B" in script
    assert "Qwen/Qwen2.5-1.5B-Instruct" not in script
    assert "gemma3-270m-it" not in script
