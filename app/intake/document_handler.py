from __future__ import annotations

import io
from pathlib import Path


def extract_text(filename: str, file_bytes: bytes) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_bytes)

    if suffix in {".md", ".txt"}:
        return file_bytes.decode("utf-8", errors="ignore")

    return ""


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        import pypdf  # type: ignore[import]

        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts)
    except ImportError:
        pass

    try:
        import pdfplumber  # type: ignore[import]

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            parts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
            return "\n".join(parts)
    except ImportError:
        pass

    return ""
