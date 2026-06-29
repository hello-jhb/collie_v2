"""Build a structured model brief from workbook orientation."""

from __future__ import annotations

from typing import Any

from moose.intake import IntakeResult

from .workbook_result import ModelBriefResult, WorkbookOrientationResult


METRIC_FAMILIES_BY_SECTION = {
    "assumptions": ["growth assumptions", "vacancy assumptions", "operating assumptions"],
    "capital_structure": ["sources and uses", "debt terms", "equity requirements"],
    "operating_forecast": ["revenue", "operating expenses", "NOI", "cash flow"],
    "debt": ["loan terms", "debt service", "coverage metrics"],
    "returns": ["IRR", "equity multiple", "cash yield"],
    "exit": ["exit value", "exit cap rate", "sale proceeds"],
    "rent_roll": ["tenant roster", "lease expirations", "in-place rent"],
}


class ModelBriefBuilder:
    """Describe what Moose thinks it is looking at, without extracting values."""

    def build(
        self,
        intake_result: IntakeResult,
        orientation: WorkbookOrientationResult,
    ) -> ModelBriefResult:
        """Return a structured, human-readable model brief."""
        context = intake_result.resolved_context
        metric_families = self._expected_metric_families(orientation.likely_sections)
        decision_supported = self._decision_supported(context, orientation.workbook_type)

        return ModelBriefResult(
            brief_summary=(
                f"Moose identified this workbook as a {orientation.workbook_type} with "
                f"{orientation.confidence:.0%} orientation confidence."
            ),
            model_purpose=orientation.likely_purpose,
            business_context={
                "document_type": intake_result.document_identity.get("document_type"),
                "lifecycle_stage": context.get("lifecycle_stage"),
                "decision_layer": context.get("decision_layer"),
                "functional_work": context.get("functional_work"),
                "related_initiatives": context.get("related_initiatives"),
            },
            key_sheets=orientation.important_sheets,
            likely_decision_supported=decision_supported,
            expected_metric_families=metric_families,
            extraction_plan_for_day4=self._day4_plan(orientation.likely_sections),
            caveats=self._caveats(intake_result, orientation),
        )

    def _expected_metric_families(self, sections: list[str]) -> list[str]:
        families: list[str] = []
        for section in sections:
            families.extend(METRIC_FAMILIES_BY_SECTION.get(section, []))
        return list(dict.fromkeys(families))

    def _decision_supported(self, context: dict[str, Any], workbook_type: str) -> str:
        layers = context.get("decision_layer") or []
        initiatives = context.get("related_initiatives") or []
        if "acquisition" in (context.get("lifecycle_stage") or []):
            return "Acquisition underwriting and investment decision support."
        if "refinancing" in initiatives:
            return "Asset-level refinancing and lender analysis support."
        if "asset" in layers:
            return "Asset-level forecast, valuation, or business-plan decision support."
        if "fund" in layers or workbook_type == "fund_model":
            return "Fund-level performance, NAV, or investor reporting support."
        return "Financial model review and later claim extraction planning."

    def _day4_plan(self, sections: list[str]) -> list[str]:
        if not sections:
            return ["Have a human confirm the workbook structure before claim extraction."]
        return [
            f"Locate candidate claim evidence in {section.replace('_', ' ')} sections."
            for section in sections
        ] + [
            "Extract claims with source cells and sheet references.",
            "Send claims to the code Trust Engine for verification.",
        ]

    def _caveats(
        self,
        intake_result: IntakeResult,
        orientation: WorkbookOrientationResult,
    ) -> list[str]:
        caveats: list[str] = []
        if intake_result.route.get("human_review_required"):
            caveats.append("Intake required human review before workbook comprehension.")
        if orientation.human_review_required:
            caveats.append("Workbook orientation confidence is low enough to require review.")
        caveats.append("No investment metrics or claims were extracted in Day 3.")
        caveats.append("No Trust Engine verification has been run yet.")
        return caveats
