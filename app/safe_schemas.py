from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    name: str
    display_name: str
    tier: Literal["CORE", "IMPORTANT"]
    level: Literal["HIGH", "MEDIUM", "LOW"]
    evidence_quality: Literal["Strong", "Partial", "Weak"]
    regulatory_anchor: str
    reason: str


class ExpertOutput(BaseModel):
    id: Literal[
        "expert_adversarial_security",
        "expert_content_safety",
        "expert_governance_un",
    ]
    overall: Literal["HIGH", "MEDIUM", "LOW"]
    triggered_dimensions: list[DimensionScore] = Field(default_factory=list)


class TranslationReport(BaseModel):
    translation_applied: bool
    primary_language: str
    # LLM-mode fields
    confidence_qualitative: Optional[Literal["High", "Medium", "Low"]] = None
    confidence_note: Optional[str] = None
    language_segments: Optional[list[dict[str, Any]]] = None
    # NLLB-mode fields
    confidence_numeric: Optional[float] = None
    confidence_warning: bool = False
    multilingual_jailbreak_suspected: bool = False


class EvidenceBundle(BaseModel):
    input_type: Literal["github", "conversation", "document"]
    translation_report: TranslationReport
    content: dict[str, Any] = Field(default_factory=dict)
    api_key: str = ""          # routing only — never serialised into evidence content
    live_attack_results: None = None


class ArbitrationResult(BaseModel):
    verdict: Literal["REJECT", "HOLD", "APPROVE"]
    primary_reason: dict[str, Any] = Field(default_factory=dict)
    additional_findings: list[str] = Field(default_factory=list)
    convergent_risk_note: str = ""


class SAFEEvaluationResponse(BaseModel):
    evaluation_id: str
    timestamp: str
    safe_version: str
    verdict: Literal["REJECT", "HOLD", "APPROVE"]
    primary_reason: dict[str, Any] = Field(default_factory=dict)
    additional_findings: list[str] = Field(default_factory=list)
    submission_context: dict[str, Any] = Field(default_factory=dict)
    experts: list[ExpertOutput] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    translation_report: TranslationReport
    report_path: str = ""
