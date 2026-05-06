"""
Tests for Expert internal E-rules aggregation via compute_overall().
Pure Python — no LLM, deterministic.
"""
from __future__ import annotations

import os

os.environ.setdefault("EXECUTION_MODE", "rules")

from app.experts.base import compute_overall


def _dim(tier: str, level: str) -> dict:
    return {"tier": tier, "level": level}


# ---------------------------------------------------------------------------
# E-Rule 1: Any CORE dimension = HIGH → Expert = HIGH
# ---------------------------------------------------------------------------

def test_e_rule1_core_high_returns_high():
    dims = [_dim("CORE", "HIGH"), _dim("IMPORTANT", "LOW")]
    assert compute_overall(dims) == "HIGH"


def test_e_rule1_single_core_high_is_sufficient():
    dims = [_dim("CORE", "LOW"), _dim("CORE", "HIGH"), _dim("IMPORTANT", "LOW")]
    assert compute_overall(dims) == "HIGH"


# ---------------------------------------------------------------------------
# E-Rule 2: Any CORE dimension = MEDIUM → Expert = MEDIUM (no CORE=HIGH present)
# ---------------------------------------------------------------------------

def test_e_rule2_core_medium_returns_medium():
    dims = [_dim("CORE", "MEDIUM"), _dim("IMPORTANT", "LOW")]
    assert compute_overall(dims) == "MEDIUM"


def test_e_rule2_does_not_fire_when_core_high_present():
    # CORE=HIGH is present — E-Rule 1 should win
    dims = [_dim("CORE", "HIGH"), _dim("CORE", "MEDIUM")]
    assert compute_overall(dims) == "HIGH"


# ---------------------------------------------------------------------------
# E-Rule 3: ≥2 IMPORTANT dimensions = HIGH → Expert = HIGH
# ---------------------------------------------------------------------------

def test_e_rule3_two_important_high_returns_high():
    dims = [_dim("IMPORTANT", "HIGH"), _dim("IMPORTANT", "HIGH"), _dim("CORE", "LOW")]
    assert compute_overall(dims) == "HIGH"


def test_e_rule3_three_important_high_also_returns_high():
    dims = [_dim("IMPORTANT", "HIGH")] * 3
    assert compute_overall(dims) == "HIGH"


def test_e_rule3_does_not_fire_with_only_one_important_high():
    dims = [_dim("IMPORTANT", "HIGH"), _dim("IMPORTANT", "MEDIUM"), _dim("CORE", "LOW")]
    assert compute_overall(dims) == "MEDIUM"  # E-Rule 4 fires instead


# ---------------------------------------------------------------------------
# E-Rule 4: Exactly 1 IMPORTANT dimension = HIGH → Expert = MEDIUM
# ---------------------------------------------------------------------------

def test_e_rule4_one_important_high_returns_medium():
    dims = [_dim("IMPORTANT", "HIGH"), _dim("IMPORTANT", "LOW"), _dim("CORE", "LOW")]
    assert compute_overall(dims) == "MEDIUM"


def test_e_rule4_does_not_fire_when_two_important_high():
    # E-Rule 3 should win
    dims = [_dim("IMPORTANT", "HIGH"), _dim("IMPORTANT", "HIGH")]
    assert compute_overall(dims) == "HIGH"


# ---------------------------------------------------------------------------
# E-Rule 5: None of the above → Expert = LOW
# ---------------------------------------------------------------------------

def test_e_rule5_all_low_returns_low():
    dims = [_dim("CORE", "LOW"), _dim("IMPORTANT", "LOW"), _dim("IMPORTANT", "LOW")]
    assert compute_overall(dims) == "LOW"


def test_e_rule5_empty_dimensions_returns_low():
    assert compute_overall([]) == "LOW"


def test_e_rule5_important_medium_only_returns_low():
    # IMPORTANT=MEDIUM does not trigger any rule → LOW
    dims = [_dim("IMPORTANT", "MEDIUM"), _dim("CORE", "LOW")]
    assert compute_overall(dims) == "LOW"


# ---------------------------------------------------------------------------
# Priority ordering across rules
# ---------------------------------------------------------------------------

def test_e_rule1_beats_e_rule2():
    dims = [_dim("CORE", "HIGH"), _dim("CORE", "MEDIUM")]
    assert compute_overall(dims) == "HIGH"


def test_e_rule1_beats_e_rule3():
    # CORE=HIGH present alongside 2 IMPORTANT=HIGH — Rule 1 wins
    dims = [_dim("CORE", "HIGH"), _dim("IMPORTANT", "HIGH"), _dim("IMPORTANT", "HIGH")]
    assert compute_overall(dims) == "HIGH"


def test_e_rule2_beats_e_rule4():
    # CORE=MEDIUM + 1 IMPORTANT=HIGH — Rule 2 wins (MEDIUM, not via Rule 4 path)
    dims = [_dim("CORE", "MEDIUM"), _dim("IMPORTANT", "HIGH")]
    assert compute_overall(dims) == "MEDIUM"
