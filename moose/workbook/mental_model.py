"""Build a workbook mental model from Day 3 comprehension outputs."""

from __future__ import annotations

from typing import Any

from moose.intake import IntakeResult

from .workbook_result import (
    ModelBriefResult,
    WorkbookInspectionResult,
    WorkbookMentalModelResult,
    WorkbookOrientationResult,
)


SECTION_TO_FAMILY = {
    "assumptions": ["investment_basis"],
    "capital_structure": ["investment_basis", "capital_structure"],
    "operating_forecast": ["operating_performance"],
    "debt": ["debt", "capital_structure"],
    "returns": ["returns"],
    "exit": ["exit"],
    "rent_roll": ["operating_performance"],
}

AUTHORITATIVE_SOURCE_HINTS = {
    "purchase_price": ["Summary", "Sources & Uses", "Assumptions"],
    "total_project_cost": ["Summary", "Sources & Uses", "Assumptions"],
    "debt_amount": ["Debt", "Sources & Uses", "Summary"],
    "equity_required": ["Sources & Uses", "Summary"],
    "loan_to_value": ["Debt", "Summary"],
    "interest_rate": ["Debt", "Assumptions"],
    "levered_irr": ["Returns", "Summary"],
    "unlevered_irr": ["Returns", "Summary"],
    "equity_multiple": ["Returns", "Summary"],
    "stabilized_noi": ["Cash Flow", "Summary"],
    "exit_cap_rate": ["Exit", "Assumptions", "Summary"],
    "sale_value": ["Exit", "Cash Flow", "Summary"],
    "hold_period": ["Summary", "Assumptions"],
}


class WorkbookMentalModelBuilder:
    """Create the professional frame that guides workbook claim extraction."""

    def build(
        self,
        intake_result: IntakeResult,
        inspection: WorkbookInspectionResult,
        orientation: WorkbookOrientationResult,
        model_brief: ModelBriefResult,
    ) -> WorkbookMentalModelResult:
        """Return a mental model, not extracted facts."""
        context = intake_result.resolved_context
        sections = orientation.likely_sections or inspection.possible_model_sections
        metric_families = self._metric_families(sections)
        initiatives = context.get("related_initiatives") or []

        return WorkbookMentalModelResult(
            document_type=str(intake_result.document_identity.get("document_type", "unknown")),
            workbook_type=orientation.workbook_type,
            business_purpose=orientation.likely_purpose,
            decision_supported=model_brief.likely_decision_supported,
            lifecycle_stage=self._as_list(context.get("lifecycle_stage")),
            decision_layer=self._as_list(context.get("decision_layer")),
            functional_work=self._as_list(context.get("functional_work")),
            initiative=initiatives,
            important_sheets=orientation.important_sheets,
            ignored_sheets=orientation.ignored_sheets,
            expected_sections=sections,
            expected_metric_families=metric_families,
            extraction_priorities=self._priorities(metric_families),
            likely_authoritative_sources=self._authoritative_sources(metric_families),
            caveats=self._caveats(inspection, orientation, model_brief),
            confidence=round(min(orientation.confidence, 0.9), 2),
        )

    def _metric_families(self, sections: list[str]) -> list[str]:
        families: list[str] = []
        for section in sections:
            families.extend(SECTION_TO_FAMILY.get(section, []))
        return list(dict.fromkeys(families))

    def _priorities(self, metric_families: list[str]) -> list[str]:
        priorities = []
        if "investment_basis" in metric_families or "capital_structure" in metric_families:
            priorities.append("extract investment basis and capital structure first")
        if "returns" in metric_families:
            priorities.append("extract return metrics second")
        if "operating_performance" in metric_families or "exit" in metric_families:
            priorities.append("extract operating forecast and exit assumptions third")
        if "debt" in metric_families:
            priorities.append("extract debt terms with source sheet and cell references")
        return priorities or ["confirm workbook structure before extracting claims"]

    def _authoritative_sources(self, metric_families: list[str]) -> dict[str, list[str]]:
        allowed = {
            "investment_basis": {"purchase_price", "total_project_cost"},
            "capital_structure": {"debt_amount", "equity_required", "loan_to_value"},
            "debt": {"debt_amount", "loan_to_value", "interest_rate"},
            "returns": {"levered_irr", "unlevered_irr", "equity_multiple"},
            "operating_performance": {"stabilized_noi"},
            "exit": {"exit_cap_rate", "sale_value", "hold_period"},
        }
        metrics: set[str] = set()
        for family in metric_families:
            metrics.update(allowed.get(family, set()))
        return {
            metric: AUTHORITATIVE_SOURCE_HINTS[metric]
            for metric in AUTHORITATIVE_SOURCE_HINTS
            if metric in metrics
        }

    def _caveats(
        self,
        inspection: WorkbookInspectionResult,
        orientation: WorkbookOrientationResult,
        model_brief: ModelBriefResult,
    ) -> list[str]:
        caveats = list(model_brief.caveats)
        if inspection.hidden_sheets:
            caveats.append("Some workbook sheets are hidden and may contain supporting calculations.")
        if orientation.human_review_required:
            caveats.append("Mental model inherits low-confidence workbook orientation.")
        caveats.append("Mental model is extraction guidance, not verified fact.")
        return list(dict.fromkeys(caveats))

    def _as_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]
