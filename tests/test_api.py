from app.main import evaluate, health, root


def test_health() -> None:
    assert health() == {"status": "ok"}


def test_root_describes_api_entrypoints() -> None:
    body = root()
    assert body["status"] == "ok"
    assert body["docs_url"] == "/docs"
    assert body["smoke_test_url"] == "/smoke-test"
    assert body["evaluation_endpoint"] == "/v1/evaluations"
    assert "runtime_preflight_status" in body
    assert "startup_warning" in body
