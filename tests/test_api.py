import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


GITHUB_URL = "https://github.com/example/verimedia-mini"



def _build_demo_repo(repo_dir: Path) -> None:
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text(
        "from flask import Flask, request, session\n"
        "app = Flask(__name__)\n"
        "app.config['SECRET_KEY'] = 'dev-key-for-development'\n"
        "@app.route('/upload', methods=['POST'])\n"
        "def upload():\n"
        "    file = request.files['file']\n"
        "    return 'ok'\n"
        "# gpt-4o whisper openai_api_key\n",
        encoding="utf-8",
    )
    (repo_dir / "requirements.txt").write_text("flask\nopenai\n", encoding="utf-8")



def _assert_report_shape(body: dict) -> None:
    assert body["repository_summary"]["framework"] == "Flask"
    assert "GPT-4o backend usage detected" in body["repository_summary"]["detected_signals"]
    assert body["decision"] in {"REVIEW", "REJECT"}
    assert body["report_path"].endswith(".md")
    assert body["archive_path"].endswith(".json")
    assert len(body["experts"]) == 3
    assert body["council_result"]["consensus_summary"]
    assert body["council_result"]["cross_expert_critique"]
    assert body["council_result"]["recommended_actions"]
    assert body["council_result"]["decision_rule_triggered"]
    assert body["repository_summary"]["evidence_items"]

    report_text = Path(body["report_path"]).read_text(encoding="utf-8")
    assert "AI Safety Lab Stakeholder Evaluation Report" in report_text
    assert "Cross-expert critique" in report_text
    assert "Recommended actions before sign-off" in report_text
    assert "Detected repository signals" in report_text
    assert "Evidence from repository" in report_text



def _post_payload(client: TestClient, submission: dict) -> dict:
    payload = {
        "context": {"agent_name": "VeriMedia", "domain": "Other", "capabilities": [], "high_autonomy": False},
        "submission": submission,
        "metadata": {},
        "selected_policies": ["eu_ai_act", "us_nist", "iso", "unesco"],
        "conversation": [],
    }
    response = client.post("/v1/evaluations", json=payload)
    assert response.status_code == 200, response.text
    return response.json()



def _fake_git_clone_factory(source_repo: Path):
    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool):
        assert cmd == ["git", "clone", "--depth", "1", GITHUB_URL, cmd[-1]]
        clone_target = Path(cmd[-1])
        shutil.copytree(source_repo, clone_target, dirs_exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    return fake_run



def _build_github_submission() -> dict:
    return {
        "source_type": "github_url",
        "github_url": GITHUB_URL,
        "local_path": "",
        "target_name": "VeriMedia",
        "description": "Flask app for toxicity analysis",
    }



def _build_local_submission(repo_dir: Path) -> dict:
    return {
        "source_type": "local_path",
        "local_path": str(repo_dir),
        "target_name": "VeriMedia",
        "description": "Flask app for toxicity analysis",
    }



def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}



def test_root_describes_api_entrypoints() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["docs_url"] == "/docs"
    assert body["smoke_test_url"] == "/smoke-test"
    assert body["evaluation_endpoint"] == "/v1/evaluations"



def test_smoke_test_initializes_all_three_experts() -> None:
    client = TestClient(app)
    response = client.get("/smoke-test")
    assert response.status_code == 200
    body = response.json()
    assert body["smoke_test"] == "pass"
    assert body["llm_backend"] == "rules"
    assert set(body["experts"]) == {
        "policy_and_compliance",
        "adversarial_misuse",
        "system_and_deployment",
    }
    assert all(item["status"] == "ok" for item in body["experts"].values())
    assert body["council_preview"]["decision_rule_triggered"]



def test_local_repo_submission_returns_structured_report(tmp_path: Path) -> None:
    repo_dir = tmp_path / "verimedia-mini"
    _build_demo_repo(repo_dir)

    client = TestClient(app)
    body = _post_payload(client, _build_local_submission(repo_dir))

    _assert_report_shape(body)
    assert body["repository_summary"]["source_type"] == "local_path"
    assert body["submission"]["local_path"] == str(repo_dir)



def test_github_url_submission_returns_structured_report(tmp_path: Path, monkeypatch) -> None:
    source_repo = tmp_path / "github-source"
    _build_demo_repo(source_repo)
    monkeypatch.setattr("app.intake.submission_service.subprocess.run", _fake_git_clone_factory(source_repo))

    client = TestClient(app)
    body = _post_payload(client, _build_github_submission())

    _assert_report_shape(body)
    assert body["repository_summary"]["source_type"] == "github_url"
    assert body["submission"]["github_url"] == GITHUB_URL
    assert body["submission"]["local_path"] == ""
    assert body["repository_summary"]["target_name"] == "VeriMedia"
    assert body["repository_summary"]["description"] == "Flask app for toxicity analysis"
    assert body["repository_summary"]["resolved_path"]
    assert not Path(body["repository_summary"]["resolved_path"]).exists()
