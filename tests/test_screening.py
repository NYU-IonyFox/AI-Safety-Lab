"""Phase 3 — L2 Screening layer tests."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.safe_schemas import EvidenceBundle, TranslationReport
from app.intake.screening import screen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tr(**kwargs) -> TranslationReport:
    defaults: dict = {
        "translation_applied": False,
        "primary_language": "en",
        "multilingual_jailbreak_suspected": False,
        "confidence_warning": False,
    }
    defaults.update(kwargs)
    return TranslationReport(**defaults)


GITHUB_MOCK = {
    "url": "https://github.com/test/repo",
    "key_files": {"README.md": "# Test Repo\n"},
    "analyzer_summary": "test-repo is a FastAPI repository.",
    "structural_tags": ["framework:FastAPI", "dep:fastapi"],
}


# ---------------------------------------------------------------------------
# Test 1 — conversation input returns EvidenceBundle with correct input_type
# ---------------------------------------------------------------------------

def test_conversation_returns_evidence_bundle():
    result = screen("conversation", "Hello, how are you?")
    assert isinstance(result, EvidenceBundle)
    assert result.input_type == "conversation"


# ---------------------------------------------------------------------------
# Test 2 — document input (mock bytes) returns EvidenceBundle
# ---------------------------------------------------------------------------

def test_document_returns_evidence_bundle():
    result = screen("document", b"This is a test document.", filename="test.txt")
    assert isinstance(result, EvidenceBundle)
    assert result.input_type == "document"


# ---------------------------------------------------------------------------
# Test 3 — github input (mocked fetch) returns EvidenceBundle
# ---------------------------------------------------------------------------

def test_github_returns_evidence_bundle():
    with patch("app.intake.screening.fetch_github_content", return_value=GITHUB_MOCK):
        result = screen("github", "https://github.com/test/repo")
    assert isinstance(result, EvidenceBundle)
    assert result.input_type == "github"


# ---------------------------------------------------------------------------
# Test 4 — live_attack_results is None for all input types
# ---------------------------------------------------------------------------

def test_conversation_live_attack_results_none():
    result = screen("conversation", "test", _tr())
    assert result.live_attack_results is None


def test_document_live_attack_results_none():
    result = screen("document", b"test content", _tr(), filename="doc.txt")
    assert result.live_attack_results is None


def test_github_live_attack_results_none():
    with patch("app.intake.screening.fetch_github_content", return_value=GITHUB_MOCK):
        result = screen("github", "https://github.com/test/repo", _tr())
    assert result.live_attack_results is None


# ---------------------------------------------------------------------------
# Test 5 — EvidenceBundle.content contains expected keys per type
# ---------------------------------------------------------------------------

def test_conversation_content_keys():
    result = screen("conversation", "Hello world")
    assert "text" in result.content
    assert "char_count" in result.content
    assert result.content["text"] == "Hello world"
    assert result.content["char_count"] == 11


def test_document_content_keys():
    result = screen("document", b"Sample document content", filename="sample.txt")
    assert "filename" in result.content
    assert "extracted_text" in result.content
    assert "char_count" in result.content
    assert result.content["filename"] == "sample.txt"
    assert result.content["extracted_text"] == "Sample document content"


def test_github_content_keys():
    with patch("app.intake.screening.fetch_github_content", return_value=GITHUB_MOCK):
        result = screen("github", "https://github.com/test/repo")
    assert "url" in result.content
    assert "structural_tags" in result.content
    assert "key_files" in result.content
    assert "analyzer_summary" in result.content


def test_github_content_values():
    with patch("app.intake.screening.fetch_github_content", return_value=GITHUB_MOCK):
        result = screen("github", "https://github.com/test/repo")
    assert result.content["url"] == "https://github.com/test/repo"
    assert "framework:FastAPI" in result.content["structural_tags"]
    assert "README.md" in result.content["key_files"]


# ---------------------------------------------------------------------------
# Extra — translation_report passthrough and default
# ---------------------------------------------------------------------------

def test_translation_report_passthrough():
    tr = _tr(primary_language="zh", translation_applied=True)
    result = screen("conversation", "你好世界", tr)
    assert result.translation_report.primary_language == "zh"
    assert result.translation_report.translation_applied is True


def test_default_translation_report_when_none():
    result = screen("conversation", "Hello")
    assert result.translation_report is not None
    assert result.translation_report.primary_language == "en"
    assert result.translation_report.translation_applied is False


def test_document_txt_extraction():
    payload = b"Line one\nLine two\n"
    result = screen("document", payload, filename="notes.txt")
    assert result.content["extracted_text"] == "Line one\nLine two\n"
    assert result.content["char_count"] == len("Line one\nLine two\n")


def test_document_unknown_extension_returns_empty():
    result = screen("document", b"\x00\x01\x02", filename="binary.bin")
    assert result.content["extracted_text"] == ""
    assert result.content["char_count"] == 0
