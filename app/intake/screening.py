from __future__ import annotations

from app.safe_schemas import EvidenceBundle, TranslationReport
from app.intake.document_handler import extract_text
from app.intake.submission_service import fetch_github_content


def screen(
    input_type: str,
    raw_input: str | bytes,
    translation_report: TranslationReport | None = None,
    *,
    filename: str = "",
) -> EvidenceBundle:
    if translation_report is None:
        translation_report = TranslationReport(
            translation_applied=False,
            primary_language="en",
            multilingual_jailbreak_suspected=False,
            confidence_warning=False,
        )

    if input_type == "conversation":
        text = raw_input if isinstance(raw_input, str) else raw_input.decode("utf-8", errors="ignore")
        content: dict = {"text": text, "char_count": len(text)}

    elif input_type == "document":
        file_bytes = raw_input if isinstance(raw_input, bytes) else raw_input.encode("utf-8")
        extracted = extract_text(filename, file_bytes)
        content = {
            "filename": filename,
            "extracted_text": extracted,
            "char_count": len(extracted),
        }

    elif input_type == "github":
        url = raw_input if isinstance(raw_input, str) else raw_input.decode("utf-8", errors="ignore")
        github_data = fetch_github_content(url)
        content = {
            "url": github_data.get("url", url),
            "structural_tags": github_data.get("structural_tags", []),
            "key_files": github_data.get("key_files", {}),
            "analyzer_summary": github_data.get("analyzer_summary", ""),
        }

    else:
        content = {}

    return EvidenceBundle(
        input_type=input_type,  # type: ignore[arg-type]
        translation_report=translation_report,
        content=content,
        live_attack_results=None,
    )
