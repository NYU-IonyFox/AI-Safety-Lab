from __future__ import annotations

import json

from app.slm.local_hf_runner import LocalHFRunner


def main() -> None:
    runner = LocalHFRunner()
    print(json.dumps(runner.warmup(), indent=2))


if __name__ == "__main__":
    main()
