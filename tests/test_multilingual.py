"""
Tests for app/multilingual/nllb_translator.py and orchestrator translation integration.
No NLLB model is ever loaded — all model calls are mocked.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.multilingual.nllb_translator import translate_to_english
from app.schemas import AgentContext, ConversationTurn, EvaluationRequest


# ---------------------------------------------------------------------------
# Part A/B: nllb_translator unit tests
# ---------------------------------------------------------------------------


def test_english_input_returns_immediately_no_model_load():
    """English input must short-circuit before touching _load_nllb."""
    with patch("app.multilingual.nllb_translator._load_nllb") as mock_load:
        result_text, confidence = translate_to_english("hello", "en")

    assert result_text == "hello"
    assert confidence == 1.0
    mock_load.assert_not_called()


def test_english_eng_latn_returns_immediately_no_model_load():
    with patch("app.multilingual.nllb_translator._load_nllb") as mock_load:
        result_text, confidence = translate_to_english("hello", "eng_Latn")

    assert result_text == "hello"
    assert confidence == 1.0
    mock_load.assert_not_called()


def test_model_load_failure_returns_original_text_and_zero_confidence():
    """When _load_nllb returns False, translate_to_english must return (text, 0.0)."""
    with patch("app.multilingual.nllb_translator._load_nllb", return_value=False):
        result_text, confidence = translate_to_english("Bonjour le monde", "fra_Latn")

    assert result_text == "Bonjour le monde"
    assert confidence == 0.0


def test_translation_failure_returns_original_text_and_zero_confidence():
    """When model is loaded but generate() raises, return (text, 0.0) — no exception."""
    with patch("app.multilingual.nllb_translator._load_nllb", return_value=True):
        with patch("app.multilingual.nllb_translator._nllb_tokenizer") as mock_tok:
            with patch("app.multilingual.nllb_translator._nllb_model") as mock_model:
                mock_tok.return_value = MagicMock()
                mock_model.device = "cpu"
                mock_model.generate.side_effect = RuntimeError("generate failed")

                result_text, confidence = translate_to_english("Hola mundo", "spa_Latn")

    assert result_text == "Hola mundo"
    assert confidence == 0.0


# ---------------------------------------------------------------------------
# Orchestrator integration tests (no NLLB loaded)
# ---------------------------------------------------------------------------


def _make_orchestrator(monkeypatch):
    """Build a SafetyLabOrchestrator with SLM_BACKEND=mock."""
    monkeypatch.setenv("SLM_BACKEND", "mock")
    from app.orchestrator import SafetyLabOrchestrator
    return SafetyLabOrchestrator()


def _make_request(primary_language: str = "en", content: str = "Hello") -> EvaluationRequest:
    return EvaluationRequest(
        context=AgentContext(agent_name="test-agent", domain="Other"),
        conversation=[ConversationTurn(role="user", content=content)],
        metadata={"primary_language": primary_language},
    )


def _run_evaluate(orch, request, tmp_path: Path):
    """Run evaluate() with all heavy I/O mocked out."""
    fake_report_path = tmp_path / "report.md"
    fake_report_path.write_text("# report", encoding="utf-8")
    fake_archive_path = tmp_path / "archive.json"

    with (
        patch("app.orchestrator.resolve_submission", return_value=None),
        patch("app.orchestrator.cleanup_submission"),
        patch(
            "app.orchestrator.persist_evaluation",
            return_value=("eval-001", fake_report_path, fake_archive_path),
        ),
        patch("app.orchestrator.build_markdown_report", return_value="# report"),
    ):
        return orch.evaluate(request)


def test_orchestrator_writes_translation_confidence_and_primary_language(monkeypatch, tmp_path):
    """evaluate() must write translation_confidence and primary_language into behavior_summary."""
    orch = _make_orchestrator(monkeypatch)
    request = _make_request(primary_language="en")

    response = _run_evaluate(orch, request, tmp_path)

    bs = response.behavior_summary
    assert bs is not None
    assert hasattr(bs, "translation_confidence")
    assert hasattr(bs, "primary_language")
    # English: confidence stays 1.0, primary_language = "en"
    assert bs.translation_confidence == 1.0
    assert bs.primary_language == "en"


def test_orchestrator_multilingual_warning_when_confidence_below_threshold(monkeypatch, tmp_path):
    """multilingual_warning=True when translation_confidence < 0.80 for non-English input."""
    orch = _make_orchestrator(monkeypatch)
    request = _make_request(primary_language="fra_Latn", content="Bonjour le monde")

    # NLLB returns low confidence
    with patch(
        "app.orchestrator.translate_to_english",
        return_value=("Hello world", 0.65),
    ):
        response = _run_evaluate(orch, request, tmp_path)

    bs = response.behavior_summary
    assert bs is not None
    assert bs.multilingual_warning is True
    assert bs.translation_confidence == 0.65
    assert bs.primary_language == "fra_Latn"


def test_orchestrator_no_flag_when_confidence_high(monkeypatch, tmp_path):
    """No multilingual_warning when translation_confidence >= 0.80."""
    orch = _make_orchestrator(monkeypatch)
    request = _make_request(primary_language="fra_Latn", content="Bonjour le monde")

    with patch(
        "app.orchestrator.translate_to_english",
        return_value=("Hello world", 0.92),
    ):
        response = _run_evaluate(orch, request, tmp_path)

    bs = response.behavior_summary
    assert bs is not None
    assert bs.multilingual_warning is False
    assert bs.translation_confidence == 0.92


def test_orchestrator_uncertainty_flag_when_primary_language_unknown(monkeypatch, tmp_path):
    """uncertainty_flag=True when primary_language='unknown'."""
    orch = _make_orchestrator(monkeypatch)
    request = _make_request(primary_language="unknown")

    response = _run_evaluate(orch, request, tmp_path)

    bs = response.behavior_summary
    assert bs is not None
    assert bs.uncertainty_flag is True
    assert bs.primary_language == "unknown"
