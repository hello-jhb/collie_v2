"""Result objects for Moose workbook comprehension."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class WorkbookInspectionResult:
    """Lightweight structural read of a workbook."""

    file_name: str
    sheet_names: list[str]
    visible_sheets: list[str]
    hidden_sheets: list[str]
    dimensions: dict[str, dict[str, int]]
    sample_non_empty_cells: dict[str, list[dict[str, Any]]]
    likely_important_sheets: list[str]
    possible_model_sections: list[str]
    projection_period_candidates: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkbookOrientationResult:
    """High-level classification of workbook purpose and structure."""

    workbook_type: str
    likely_purpose: str
    important_sheets: list[str]
    ignored_sheets: list[str]
    likely_sections: list[str]
    projection_period_guess: str | None
    confidence: float
    human_review_required: bool
    reasoning: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelBriefResult:
    """Human-readable brief of what Moose thinks the workbook is."""

    brief_summary: str
    model_purpose: str
    business_context: dict[str, Any]
    key_sheets: list[str]
    likely_decision_supported: str
    expected_metric_families: list[str]
    extraction_plan_for_day4: list[str]
    caveats: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkbookMentalModelResult:
    """Professional frame that guides claim extraction without being facts."""

    document_type: str
    workbook_type: str
    business_purpose: str
    decision_supported: str
    lifecycle_stage: list[str]
    decision_layer: list[str]
    functional_work: list[str]
    initiative: list[str]
    important_sheets: list[str]
    ignored_sheets: list[str]
    expected_sections: list[str]
    expected_metric_families: list[str]
    extraction_priorities: list[str]
    likely_authoritative_sources: dict[str, list[str]]
    caveats: list[str]
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkbookEvidencePackResult:
    """Bounded workbook context sent to claim discovery."""

    important_sheet_names: list[str]
    sampled_cells: dict[str, list[dict[str, Any]]]
    section_header_blocks: dict[str, list[dict[str, Any]]]
    candidate_neighborhoods: list[dict[str, Any]]
    caveats: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimGroundingResult:
    """Grounding validation output for discovered claims."""

    grounded_claims: list[dict[str, Any]]
    rejected_claims: list[dict[str, Any]]
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkbookComprehensionResult:
    """Day 3 output: intake, inspection, orientation, and model brief."""

    intake_result: dict[str, Any]
    workbook_inspection: dict[str, Any]
    workbook_orientation: dict[str, Any]
    model_brief: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkbookClaimExtractionResult:
    """Day 4 output: mental model plus unverified claims."""

    intake_result: dict[str, Any]
    workbook_inspection: dict[str, Any]
    workbook_orientation: dict[str, Any]
    model_brief: dict[str, Any]
    mental_model: dict[str, Any]
    evidence_pack: dict[str, Any]
    claims: list[dict[str, Any]]
    rejected_claims: list[dict[str, Any]]
    extraction_mode: str
    diagnostics: dict[str, Any] | None = None
    discovery_comparison: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
