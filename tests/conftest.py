import os
from pathlib import Path


def pytest_runtest_setup():
    pass


def configure_test_paths(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    report_dir = data_dir / "reports"
    audit_log = data_dir / "audit_log.jsonl"
    os.environ["AI_SAFETY_LAB_DATA_DIR"] = str(data_dir)
    os.environ["AI_SAFETY_LAB_REPORT_DIR"] = str(report_dir)
    os.environ["AI_SAFETY_LAB_AUDIT_LOG"] = str(audit_log)
