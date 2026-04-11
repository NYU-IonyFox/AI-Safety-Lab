from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_renderer_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "render_benchmark_summary.py"
    spec = importlib.util.spec_from_file_location("render_benchmark_summary", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_benchmark_summary_includes_overview_metrics_and_worst_cases() -> None:
    module = _load_renderer_module()
    payload = {
        "repeated": {
            "pack": {"benchmark_name": "validation-pack", "version": "2.0.0"},
            "baseline_id": "current",
            "repeat_count": 3,
            "selected_case_ids": ["case-a", "case-b"],
            "runs": [
                {"run_id": "run-1", "accuracy": 0.5, "match_count": 1, "case_count": 2, "seed": 11},
                {"run_id": "run-2", "accuracy": 1.0, "match_count": 2, "case_count": 2, "seed": 12},
            ],
        },
        "metrics": {
            "overall": {
                "accuracy": {"estimate": 0.75, "lower": 0.5, "upper": 1.0, "method": "bootstrap"},
                "false_approve_rate": {"estimate": 0.25, "lower": 0.0, "upper": 0.5, "method": "bootstrap"},
                "false_reject_rate": {"estimate": 0.0, "lower": 0.0, "upper": 0.0, "method": "bootstrap"},
                "review_rate": {"estimate": 0.25, "lower": 0.0, "upper": 0.5, "method": "bootstrap"},
            }
        },
        "worst_case_report": {
            "worst_slices": [
                {"slice_label": "behavior_only", "accuracy": 0.5, "false_approve_rate": 0.5, "error_rate": 0.0}
            ],
            "critical_failures": [
                {
                    "case_id": "case-a",
                    "expected_decision": "REJECT",
                    "mismatch_rate": 0.5,
                    "false_approve_count": 1,
                    "likely_failure_mode": "unsafe_false_approve",
                }
            ],
            "most_unstable_cases": [
                {"case_id": "case-b", "instability_score": 0.5, "observed_decisions": {"APPROVE": 1, "REVIEW": 1}}
            ],
        },
    }

    markdown = module.render_markdown_summary(payload, title="Validation Harness Summary")

    assert "# Validation Harness Summary" in markdown
    assert "## Overview" in markdown
    assert "validation-pack" in markdown
    assert "## Overall Metrics" in markdown
    assert "75.00%" in markdown
    assert "## Worst-Case Slices" in markdown
    assert "behavior_only" in markdown
    assert "## Critical Failures" in markdown
    assert "unsafe_false_approve" in markdown
    assert "## Most Unstable Cases" in markdown
    assert "case-b" in markdown


def test_summary_renderer_cli_contract_is_visible() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "render_benchmark_summary.py").read_text(
        encoding="utf-8"
    )
    assert "--input" in script
    assert "--output" in script
    assert "--title" in script
    assert "render_markdown_summary" in script
