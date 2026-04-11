#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a repeated benchmark JSON payload into markdown.")
    parser.add_argument("--input", required=True, help="Path to the repeated benchmark JSON file.")
    parser.add_argument("--output", default="", help="Optional output markdown path. Defaults to stdout.")
    parser.add_argument("--title", default="Benchmark Validation Summary", help="Markdown title.")
    return parser.parse_args()


def render_markdown_summary(payload: Mapping[str, Any], *, title: str = "Benchmark Validation Summary") -> str:
    repeated = _mapping(payload.get("repeated"))
    metrics = _mapping(payload.get("metrics"))
    worst_case = _mapping(payload.get("worst_case_report"))
    pack = _mapping(repeated.get("pack"))
    overall = _mapping(metrics.get("overall"))

    lines = [f"# {title}", ""]

    if pack:
        lines.extend(
            [
                "## Overview",
                "",
                f"- Benchmark pack: `{pack.get('benchmark_name', 'unknown')}`",
                f"- Version: `{pack.get('version', 'unknown')}`",
                f"- Baseline: `{repeated.get('baseline_id', 'unknown')}`",
                f"- Repeats: `{repeated.get('repeat_count', 0)}`",
                f"- Selected cases: `{len(repeated.get('selected_case_ids', []))}`",
                "",
            ]
        )

    if overall:
        accuracy = _metric_line(overall.get("accuracy"))
        false_approve = _metric_line(overall.get("false_approve_rate"))
        false_reject = _metric_line(overall.get("false_reject_rate"))
        review_rate = _metric_line(overall.get("review_rate"))
        lines.extend(
            [
                "## Overall Metrics",
                "",
                f"- Accuracy: {accuracy}",
                f"- False approve rate: {false_approve}",
                f"- False reject rate: {false_reject}",
                f"- Review rate: {review_rate}",
                "",
            ]
        )

    runs = repeated.get("runs", [])
    if runs:
        lines.extend(["## Repeated Runs", ""])
        for run in runs:
            run_map = _mapping(run)
            lines.append(
                f"- `{run_map.get('run_id', 'unknown')}`: accuracy `{_pct(run_map.get('accuracy'))}`, "
                f"matches `{run_map.get('match_count', 0)}/{run_map.get('case_count', 0)}`, "
                f"seed `{run_map.get('seed', 'n/a')}`"
            )
        lines.append("")

    worst_slices = worst_case.get("worst_slices", [])
    if worst_slices:
        lines.extend(["## Worst-Case Slices", ""])
        for item in worst_slices:
            item_map = _mapping(item)
            lines.append(
                f"- `{item_map.get('slice_label', 'unknown')}`: accuracy `{_pct(item_map.get('accuracy'))}`, "
                f"false approve `{_pct(item_map.get('false_approve_rate'))}`, "
                f"error rate `{_pct(item_map.get('error_rate'))}`"
            )
        lines.append("")

    critical_failures = worst_case.get("critical_failures", [])
    if critical_failures:
        lines.extend(["## Critical Failures", ""])
        for item in critical_failures:
            item_map = _mapping(item)
            lines.append(
                f"- `{item_map.get('case_id', 'unknown')}`: expected `{item_map.get('expected_decision', 'unknown')}`, "
                f"mismatch rate `{_pct(item_map.get('mismatch_rate'))}`, "
                f"false approve count `{item_map.get('false_approve_count', 0)}`, "
                f"likely mode `{item_map.get('likely_failure_mode', 'unknown')}`"
            )
        lines.append("")

    unstable_cases = worst_case.get("most_unstable_cases", [])
    if unstable_cases:
        lines.extend(["## Most Unstable Cases", ""])
        for item in unstable_cases:
            item_map = _mapping(item)
            lines.append(
                f"- `{item_map.get('case_id', 'unknown')}`: instability `{item_map.get('instability_score', 0.0):.2f}`, "
                f"observed decisions `{json.dumps(item_map.get('observed_decisions', {}), ensure_ascii=False)}`"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    markdown = render_markdown_summary(payload, title=args.title)
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
        return
    sys.stdout.write(markdown)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _metric_line(metric: Any) -> str:
    metric_map = _mapping(metric)
    if not metric_map:
        return "n/a"
    estimate = _pct(metric_map.get("estimate"))
    lower = _pct(metric_map.get("lower"))
    upper = _pct(metric_map.get("upper"))
    method = metric_map.get("method", "unknown")
    return f"{estimate} (interval {lower} to {upper}, {method})"


def _pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "n/a"


if __name__ == "__main__":
    main()
