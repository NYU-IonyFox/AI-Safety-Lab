"""
Phase 7 tests — HTML frontend: index, result page, and /submit endpoint.
All tests use EXECUTION_MODE=rules; no LLM is loaded.
"""
from __future__ import annotations

import json
import os

os.environ["EXECUTION_MODE"] = "rules"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. GET / returns 200 and contains "SAFE"
# ---------------------------------------------------------------------------

def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_index_contains_safe(client):
    resp = client.get("/")
    assert "SAFE" in resp.text


# ---------------------------------------------------------------------------
# 2. GET /result returns 200
# ---------------------------------------------------------------------------

def test_result_page_returns_200(client):
    resp = client.get("/result")
    assert resp.status_code == 200


