"""
anchor_loader.py
================
Pure utility: looks up regulatory anchor citations from framework_anchors_v2.json.

Usage (in Expert rules engines)
---------------------------------
    from app.anchors.anchor_loader import get_anchors

    # team1 example — attach to a violation dict after it is created
    violation["evidence_anchors"] = get_anchors("team1_policy_expert", "upload_surface_no_auth")

    # team2 example — attach to a dimension finding
    finding["evidence_anchors"] = get_anchors("team2_redteam_expert", "harmfulness")

    # team3 example — attach to a protocol result
    result["evidence_anchors"] = get_anchors("team3_risk_expert", "bias")

    # team3 domain tier example
    finding["evidence_anchors"] = get_anchors("team3_risk_expert", "TIER_3")

Design notes
------------
- Returns [] (never raises) when expert_name or signal_key is not found.
- JSON is loaded once at module import and cached in _ANCHORS_CACHE.
- All lookups are case-insensitive on the signal_key side.
- team3_risk_expert supports three lookup namespaces:
    * protocol_id   (e.g. "bias", "redteam", "evasion")
    * tier_key      (e.g. "TIER_1", "TIER_2", "TIER_3", "TIER_4")
    * signal_key    (e.g. "flask_upload_system_risk")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ANCHOR_FILE = Path(__file__).parent / "framework_anchors_v2.json"
_ANCHORS_CACHE: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    """Load and cache the anchor JSON file. Returns {} on any error."""
    global _ANCHORS_CACHE  # noqa: PLW0603
    if _ANCHORS_CACHE is not None:
        return _ANCHORS_CACHE
    try:
        with open(_ANCHOR_FILE, encoding="utf-8") as fh:
            _ANCHORS_CACHE = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.warning("anchor_loader: could not load %s — %s", _ANCHOR_FILE, exc)
        _ANCHORS_CACHE = {}
    return _ANCHORS_CACHE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_anchors(expert_name: str, signal_key: str) -> list[dict[str, str]]:
    """Return the list of anchor dicts for a given expert and signal key.

    Parameters
    ----------
    expert_name:
        One of ``"team1_policy_expert"``, ``"team2_redteam_expert"``,
        ``"team3_risk_expert"``.
    signal_key:
        For team1: a violation signal key (e.g. ``"upload_surface_no_auth"``).
        For team2: a dimension key (e.g. ``"harmfulness"``).
        For team3: a protocol id (e.g. ``"bias"``), a tier key
            (e.g. ``"TIER_3"``), or a deployment signal key
            (e.g. ``"flask_upload_system_risk"``).

    Returns
    -------
    list[dict]
        Each dict has keys ``"framework"``, ``"section"``, ``"provision"``.
        Returns ``[]`` when the expert or signal is not found — never raises.
    """
    data = _load()
    expert_block: dict[str, Any] = data.get(expert_name, {})
    if not expert_block:
        return []

    key_lower = signal_key.strip().lower()

    if expert_name == "team1_policy_expert":
        return _search_list(
            expert_block.get("violation_anchors", []),
            "signal_key",
            key_lower,
        )

    if expert_name == "team2_redteam_expert":
        return _search_list(
            expert_block.get("dimension_anchors", []),
            "dimension_key",
            key_lower,
        )

    if expert_name == "team3_risk_expert":
        # Try all three namespaces in order: protocol → tier → deployment signal
        result = _search_list(
            expert_block.get("protocol_anchors", []),
            "protocol_id",
            key_lower,
        )
        if result:
            return result
        result = _search_list(
            expert_block.get("domain_tier_anchors", []),
            "tier_key",
            signal_key.strip().upper(),  # tier keys are uppercase: TIER_1 etc.
        )
        if result:
            return result
        return _search_list(
            expert_block.get("deployment_signal_anchors", []),
            "signal_key",
            key_lower,
        )

    return []


def get_all_signal_keys(expert_name: str) -> list[str]:
    """Return all valid signal keys for a given expert.

    Useful for validation, testing, or building UI dropdowns.
    """
    data = _load()
    expert_block: dict[str, Any] = data.get(expert_name, {})
    if not expert_block:
        return []

    if expert_name == "team1_policy_expert":
        return [item.get("signal_key", "") for item in expert_block.get("violation_anchors", [])]

    if expert_name == "team2_redteam_expert":
        return [item.get("dimension_key", "") for item in expert_block.get("dimension_anchors", [])]

    if expert_name == "team3_risk_expert":
        keys: list[str] = []
        keys += [item.get("protocol_id", "") for item in expert_block.get("protocol_anchors", [])]
        keys += [item.get("tier_key", "") for item in expert_block.get("domain_tier_anchors", [])]
        keys += [item.get("signal_key", "") for item in expert_block.get("deployment_signal_anchors", [])]
        return [k for k in keys if k]

    return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _search_list(
    items: list[dict[str, Any]],
    key_field: str,
    target: str,
) -> list[dict[str, str]]:
    """Linear scan of an anchor list; returns anchors for the first match."""
    for item in items:
        if str(item.get(key_field, "")).strip().lower() == target.lower():
            return list(item.get("anchors", []))
    return []
