import os
import shutil
import subprocess
from pathlib import Path

import app.intake.submission_service as submission_service

from app.main import evaluate, health, root, smoke_test
from app.schemas import EvaluationRequest


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
    (repo_dir / "finetune_model_id.txt").write_text("ft:gpt-4o-mini:verimedia:toxicity:2026-04-11\n", encoding="utf-8")



def _assert_report_shape(body: dict) -> None:
    assert body["repository_summary"]["framework"] == "Flask"
    assert "GPT-4o backend usage detected" in body["repository_summary"]["detected_signals"]
    assert "Committed fine-tuned model identifier detected" in body["repository_summary"]["detected_signals"]
    assert "tracked_fine_tuned_model_id" in body["repository_summary"]["secret_signals"]
    assert body["decision"] in {"REVIEW", "REJECT"}
    assert body["report_path"].endswith(".md")
    assert body["archive_path"].endswith(".json")
    assert len(body["experts"]) == 3
    assert body["council_result"]["consensus_summary"]
    assert body["council_result"]["cross_expert_critique"]
    assert body["council_result"]["deliberation_enabled"] is True
    assert body["council_result"]["deliberation_trace"]
    assert body["council_result"]["recommended_actions"]
    assert body["council_result"]["decision_rule_triggered"]
    assert body["repository_summary"]["evidence_items"]
    assert all(expert["metadata"]["runner_mode"] in {"slm", "rules_fallback", "rules"} for expert in body["experts"])
    assert all(expert["metadata"]["configured_backend"] for expert in body["experts"])
    assert any(
        item["signal"] == "Tracked fine-tuned model identifier detected"
        for item in body["repository_summary"]["evidence_items"]
    )

    report_text = Path(body["report_path"]).read_text(encoding="utf-8")
    assert "AI Safety Lab Stakeholder Evaluation Report" in report_text
    assert "What happens next" in report_text
    assert "Plain-language deliberation summary" in report_text
    assert "Cross-expert critique" in report_text
    assert "Deliberation trail" in report_text
    assert "Expert-specific evidence" in report_text
    assert "Recommended actions before sign-off" in report_text
    assert "Detected repository signals" in report_text
    assert "Evidence from repository" in report_text



def _post_payload(_: object, submission: dict) -> dict:
    payload = {
        "context": {"agent_name": "VeriMedia", "domain": "Other", "capabilities": [], "high_autonomy": False},
        "submission": submission,
        "metadata": {},
        "selected_policies": ["eu_ai_act", "us_nist", "iso", "unesco"],
        "conversation": [],
    }
    response = evaluate(EvaluationRequest.model_validate(payload))
    return response.model_dump()



def _fake_git_clone_factory(source_repo: Path):
    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool, cwd: str | None = None):
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
    assert health() == {"status": "ok"}



def test_root_describes_api_entrypoints() -> None:
    body = root()
    assert body["status"] == "ok"
    assert body["docs_url"] == "/docs"
    assert body["smoke_test_url"] == "/smoke-test"
    assert body["evaluation_endpoint"] == "/v1/evaluations"



def test_smoke_test_initializes_all_three_experts() -> None:
    body = smoke_test()
    assert body["smoke_test"] == "pass"
    assert body["llm_backend"] == "local_hf"
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

    body = _post_payload(None, _build_local_submission(repo_dir))

    _assert_report_shape(body)
    assert body["repository_summary"]["source_type"] == "local_path"
    assert body["submission"]["local_path"] == str(repo_dir)



def test_github_url_submission_returns_structured_report(tmp_path: Path, monkeypatch) -> None:
    source_repo = tmp_path / "github-source"
    _build_demo_repo(source_repo)
    monkeypatch.setattr("app.intake.submission_service.subprocess.run", _fake_git_clone_factory(source_repo))

    body = _post_payload(None, _build_github_submission())

    _assert_report_shape(body)
    assert body["repository_summary"]["source_type"] == "github_url"
    assert body["submission"]["github_url"] == GITHUB_URL
    assert body["submission"]["local_path"] == ""
    assert body["repository_summary"]["target_name"] == "VeriMedia"
    assert body["repository_summary"]["description"] == "Flask app for toxicity analysis"
    assert body["repository_summary"]["resolved_path"]
    assert not Path(body["repository_summary"]["resolved_path"]).exists()


def test_github_url_submission_survives_deleted_process_cwd(tmp_path: Path, monkeypatch) -> None:
    source_repo = tmp_path / "github-source-deleted-cwd"
    _build_demo_repo(source_repo)
    original_run = submission_service.subprocess.run

    def fake_run(cmd: list[str], check: bool, capture_output: bool, text: bool, cwd: str | None = None):
        # This reproduces the old bug: if cwd is omitted while the parent process cwd is deleted,
        # spawning even a trivial subprocess fails before the clone work can start.
        original_run(["pwd"], check=True, capture_output=True, text=True, cwd=cwd)
        assert cmd == ["git", "clone", "--depth", "1", GITHUB_URL, cmd[-1]]
        clone_target = Path(cmd[-1])
        shutil.copytree(source_repo, clone_target, dirs_exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("app.intake.submission_service.subprocess.run", fake_run)

    vanished_cwd = tmp_path / "vanished-cwd"
    vanished_cwd.mkdir()
    previous_cwd = os.getcwd()
    try:
        os.chdir(vanished_cwd)
        shutil.rmtree(vanished_cwd)
        body = _post_payload(None, _build_github_submission())
    finally:
        os.chdir(previous_cwd)

    _assert_report_shape(body)
    assert body["submission"]["github_url"] == GITHUB_URL
