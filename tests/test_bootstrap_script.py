from __future__ import annotations

from pathlib import Path


def test_bootstrap_script_defaults_to_qwen_and_lists_public_presets() -> None:
    script = Path("scripts/bootstrap_local_slm.sh").read_text(encoding="utf-8")

    assert 'MODEL_PRESET="${MODEL_PRESET:-qwen2.5-1.5b}"' in script
    assert "qwen2.5-1.5b" in script
    assert "qwen2.5-3b" in script
    assert "Qwen/Qwen2.5-1.5B-Instruct" in script
    assert "Qwen/Qwen2.5-3B-Instruct" in script
