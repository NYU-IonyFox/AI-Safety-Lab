from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("AI_SAFETY_LAB_DATA_DIR", str(BASE_DIR / "data")))
REPORT_DIR = Path(os.getenv("AI_SAFETY_LAB_REPORT_DIR", str(DATA_DIR / "reports")))
AUDIT_LOG = Path(os.getenv("AI_SAFETY_LAB_AUDIT_LOG", str(DATA_DIR / "audit_log.jsonl")))

FAIL_CLOSED_CRITICAL_THRESHOLD = 0.85
HUMAN_REVIEW_MIN_CONFIDENCE = 0.55
COUNCIL_DECISION_RULE_VERSION = os.getenv("COUNCIL_DECISION_RULE_VERSION", "matrix-v2").strip() or "matrix-v2"
COUNCIL_BLOCK_THRESHOLD = float(os.getenv("COUNCIL_BLOCK_THRESHOLD", "0.72"))
COUNCIL_REVIEW_THRESHOLD = float(os.getenv("COUNCIL_REVIEW_THRESHOLD", "0.45"))
COUNCIL_STRONG_SIGNAL_THRESHOLD = float(os.getenv("COUNCIL_STRONG_SIGNAL_THRESHOLD", "0.80"))

# rules | slm | hybrid
EXPERT_EXECUTION_MODE = os.getenv("EXPERT_EXECUTION_MODE", "rules").strip().lower()

TEAM3_REQUIRE_LOCAL_SLM = os.getenv("TEAM3_REQUIRE_LOCAL_SLM", "false").strip().lower() in {"1", "true", "yes", "on"}

TARGET_TIMEOUT_SEC = int(os.getenv("TARGET_TIMEOUT_SEC", "60"))
TARGET_MAX_PROMPTS = int(os.getenv("TARGET_MAX_PROMPTS", "6"))
