from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: add frontend/ to path and stub streamlit + ui_styles before
# result_views is imported (it runs module-level import of both).
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

# Stub streamlit so the module can be imported without a running Streamlit server.
_st_stub = types.ModuleType("streamlit")
for _attr in ("warning", "info", "markdown", "columns", "button", "rerun", "session_state"):
    setattr(_st_stub, _attr, MagicMock())
sys.modules.setdefault("streamlit", _st_stub)

# Stub ui_styles so the fallback branch in result_views is not needed.
_ui_stub = types.ModuleType("ui_styles")
_ui_stub.render_metric_card = MagicMock()  # type: ignore[attr-defined]
_ui_stub.tone_for_decision = MagicMock(return_value="tone-green")  # type: ignore[attr-defined]
_ui_stub.tone_for_risk = MagicMock(return_value="tone-green")  # type: ignore[attr-defined]
_ui_stub.risk_class = MagicMock(return_value="risk-low")  # type: ignore[attr-defined]
_ui_stub.inject_styles = MagicMock()  # type: ignore[attr-defined]
sys.modules.setdefault("ui_styles", _ui_stub)

import result_views  # noqa: E402  (must come after stubs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    translation_confidence: float,
    primary_language: str,
    uncertainty_flag: bool = False,
) -> dict:
    """Build a minimal result dict that exercises _render_overview()."""
    return {
        "behavior_summary": {
            "translation_confidence": translation_confidence,
            "primary_language": primary_language,
            "uncertainty_flag": uncertainty_flag,
            "evaluation_mode": "behavior_only",
            "transcript_present": True,
            "detected_languages": [primary_language] if primary_language != "unknown" else [],
            "content_markers": [],
            "key_signals": [],
            "risk_notes": [],
        },
        "repository_summary": {},
        "submission": {},
        "expert_input": {},
    }


def _call_render_overview(result: dict) -> None:
    """Call _render_overview with st.columns stubbed to a usable context manager."""
    col_mock = MagicMock()
    col_mock.__enter__ = MagicMock(return_value=col_mock)
    col_mock.__exit__ = MagicMock(return_value=False)
    with patch.object(result_views.st, "columns", return_value=(col_mock, col_mock)):
        result_views._render_overview(result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRenderOverviewTranslationBadge:
    def test_warning_when_confidence_below_0_50(self) -> None:
        result = _make_result(translation_confidence=0.30, primary_language="fr")
        with (
            patch.object(result_views.st, "warning") as mock_warning,
            patch.object(result_views.st, "info") as mock_info,
        ):
            _call_render_overview(result)

        mock_warning.assert_called_once()
        call_msg: str = mock_warning.call_args[0][0]
        assert "0.30" in call_msg
        assert "reviewed by a human" in call_msg
        mock_info.assert_not_called()

    def test_info_when_confidence_between_0_50_and_0_80(self) -> None:
        result = _make_result(translation_confidence=0.65, primary_language="es")
        with (
            patch.object(result_views.st, "warning") as mock_warning,
            patch.object(result_views.st, "info") as mock_info,
        ):
            _call_render_overview(result)

        mock_info.assert_called_once()
        call_msg: str = mock_info.call_args[0][0]
        assert "0.65" in call_msg
        assert "provisional" in call_msg
        mock_warning.assert_not_called()

    def test_no_badge_when_confidence_at_or_above_0_80(self) -> None:
        result = _make_result(translation_confidence=0.90, primary_language="de")
        with (
            patch.object(result_views.st, "warning") as mock_warning,
            patch.object(result_views.st, "info") as mock_info,
        ):
            _call_render_overview(result)

        mock_warning.assert_not_called()
        mock_info.assert_not_called()

    def test_no_badge_when_primary_language_is_unknown(self) -> None:
        result = _make_result(
            translation_confidence=0.20,  # would normally trigger warning
            primary_language="unknown",
        )
        with (
            patch.object(result_views.st, "warning") as mock_warning,
            patch.object(result_views.st, "info") as mock_info,
        ):
            _call_render_overview(result)

        mock_warning.assert_not_called()
        mock_info.assert_not_called()
