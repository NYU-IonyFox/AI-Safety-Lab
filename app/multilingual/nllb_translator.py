"""
app/multilingual/nllb_translator.py
Local NLLB-200-distilled-600M translation with lazy loading.

GLOBAL CONSTRAINTS:
- No external API calls. All inference is local (HuggingFace cache only).
- Fail-closed: any load or translation failure returns (original_text, 0.0).
- Non-discrimination: language codes are technical identifiers only.

# NLLB does not support mixed-language input. If the input contains
# multiple languages, translation quality may be degraded.
"""
from __future__ import annotations

import logging
import math
import os

log = logging.getLogger(__name__)

NLLB_MODEL_ID = "facebook/nllb-200-distilled-600M"
_LOCAL_DEV: bool = os.getenv("LOCAL_DEV", "true").lower() in ("true", "1", "yes")

_ENGLISH_CODES = frozenset({"en", "english", "eng_latn", "eng"})

_nllb_tokenizer = None
_nllb_model = None


def _load_nllb() -> bool:
    """Load NLLB tokenizer and model lazily. Returns True on success, False on failure."""
    global _nllb_tokenizer, _nllb_model  # noqa: PLW0603

    if _nllb_model is not None:
        return True

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, NllbTokenizer

        _nllb_tokenizer = NllbTokenizer.from_pretrained(NLLB_MODEL_ID)

        if _LOCAL_DEV:
            _nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
                NLLB_MODEL_ID,
                torch_dtype=torch.float32,
            )
            _nllb_model = _nllb_model.to("cpu")
        else:
            _nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
                NLLB_MODEL_ID,
                torch_dtype=torch.float16,
                device_map="auto",
            )
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("NLLB model load failed: %s", e)
        return False


def translate_to_english(text: str, source_lang: str) -> tuple[str, float]:
    """
    Returns (translated_text, confidence).
    - English input: returns (text, 1.0) immediately, no model call.
    - Non-English: loads NLLB model (lazy, loaded once), translates,
      returns (translated_text, confidence_score).
    - Model load failure: returns (text, 0.0), logs warning, does NOT raise.
    - Translation failure: returns (text, 0.0), logs warning, does NOT raise.
    """
    if source_lang.lower() in _ENGLISH_CODES:
        return text, 1.0

    if not _load_nllb():
        return text, 0.0

    try:
        import torch

        inputs = _nllb_tokenizer(
            text,
            return_tensors="pt",
            src_lang=source_lang,
            truncation=True,
            max_length=512,
        ).to(_nllb_model.device)

        # Use convert_tokens_to_ids — do NOT use tokenizer.lang_code_to_id
        # (that method does not exist on the NLLB tokenizer and raises AttributeError)
        forced_bos_token_id = _nllb_tokenizer.convert_tokens_to_ids("eng_Latn")

        with torch.no_grad():
            output = _nllb_model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_length=512,
                return_dict_in_generate=True,
                output_scores=True,
            )

        token_log_probs: list[float] = []
        if output.scores:
            for step_idx, step_scores in enumerate(output.scores):
                chosen_id = output.sequences[0][step_idx + 1]
                log_prob = torch.log_softmax(step_scores[0], dim=-1)[chosen_id].item()
                token_log_probs.append(log_prob)

        if token_log_probs:
            mean_log_prob = sum(token_log_probs) / len(token_log_probs)
            confidence = round(min(max(math.exp(mean_log_prob), 0.0), 1.0), 4)
        else:
            confidence = 0.75

        translated = _nllb_tokenizer.batch_decode(
            output.sequences, skip_special_tokens=True
        )[0]
        return translated, confidence

    except Exception as e:  # noqa: BLE001
        log.warning("NLLB translation failed for lang=%s: %s", source_lang, e)
        return text, 0.0
