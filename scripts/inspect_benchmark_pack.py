#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_assets.benchmark_cases.loader import default_pack_path, load_benchmark_pack, pack_summary  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect the public benchmark pack.")
    parser.add_argument("--pack", default=str(default_pack_path()), help="Path to the benchmark pack JSON file.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of text.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pack = load_benchmark_pack(args.pack)
    summary = pack_summary(pack)
    payload = {
        "pack": summary,
        "cases": [
            {
                "case_id": case.case_id,
                "title": case.title,
                "repo_url": case.repo_url,
                "expected_decision": case.expected_decision,
                "category": case.category,
                "tags": case.benchmark_tags,
            }
            for case in pack.cases
        ],
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"Benchmark pack: {summary['benchmark_name']} ({summary['version']})")
    print(f"Cases: {summary['case_count']}")
    print(f"Decision counts: {summary['decision_counts']}")
    print(f"Categories: {', '.join(summary['categories'])}")
    for case in payload["cases"]:
        print(f"- {case['case_id']}: {case['expected_decision']} | {case['title']} | {case['repo_url']}")


if __name__ == "__main__":
    main()
