from __future__ import annotations

import json

from scripts import diagnose_local_slm


def test_diagnose_local_slm_json_output(monkeypatch, capsys) -> None:
    class FakeMetadata:
        runner_mode = "rules_fallback"
        configured_backend = "local_hf"
        actual_backend = "rules"
        fallback_reason = "Local HF model did not return a valid JSON object"

    class FakeExpert:
        expert_name = "team1_policy_expert"
        evaluation_status = "degraded"
        metadata = FakeMetadata()
        summary = "diagnostic summary"

    class FakeCouncilResult:
        decision_rule_triggered = "critical_expert_degraded"

    class FakeVersion:
        expert_model_backend = "local_hf"

    class FakeResponse:
        evaluation_id = "eval-123"
        decision = "REVIEW"
        council_result = FakeCouncilResult()
        version = FakeVersion()
        experts = [FakeExpert()]

    class FakeOrchestrator:
        def evaluate(self, _request):
            return FakeResponse()

    monkeypatch.setattr(diagnose_local_slm, "SafetyLabOrchestrator", lambda: FakeOrchestrator())
    monkeypatch.setattr("sys.argv", ["diagnose_local_slm.py", "--as-json"])

    diagnose_local_slm.main()
    output = json.loads(capsys.readouterr().out)

    assert output["decision"] == "REVIEW"
    assert output["experts"][0]["expert_name"] == "team1_policy_expert"
    assert output["experts"][0]["fallback_reason"] == "Local HF model did not return a valid JSON object"
