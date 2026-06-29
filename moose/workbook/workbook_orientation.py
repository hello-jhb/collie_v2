"""Orient financial model workbooks from inspection and intake context."""

from __future__ import annotations

from typing import Any

from moose.intake import IntakeResult

from .workbook_result import WorkbookInspectionResult, WorkbookOrientationResult


MODEL_TYPE_RULES = {
    "acquisition_underwriting_model": {
        "sections": {"capital_structure", "operating_forecast", "debt", "returns", "exit"},
        "purpose": "Evaluate projected investment returns for an acquisition.",
    },
    "asset_management_forecast_model": {
        "sections": {"operating_forecast", "debt", "returns"},
        "purpose": "Monitor and update asset-level forecast performance during ownership.",
    },
    "fund_model": {
        "sections": {"returns", "capital_structure"},
        "purpose": "Evaluate fund-level returns, cash flows, and capital activity.",
    },
}


class WorkbookOrientationBuilder:
    """Classify workbook purpose and important structural areas."""

    def orient(
        self,
        intake_result: IntakeResult,
        inspection: WorkbookInspectionResult,
    ) -> WorkbookOrientationResult:
        """Return workbook orientation metadata without extracting metrics."""
        context = intake_result.resolved_context
        sections = inspection.possible_model_sections
        workbook_type = self._classify_workbook_type(context, sections)
        likely_purpose = MODEL_TYPE_RULES.get(workbook_type, {}).get(
            "purpose",
            "Understand a financial model workbook for later claim extraction.",
        )
        important_sheets = inspection.likely_important_sheets or inspection.visible_sheets[:5]
        ignored_sheets = [
            sheet for sheet in inspection.sheet_names
            if sheet not in important_sheets and sheet in inspection.hidden_sheets
        ]
        projection_period_guess = self._projection_period_guess(inspection.projection_period_candidates)
        confidence = self._confidence(intake_result, inspection, sections)

        return WorkbookOrientationResult(
            workbook_type=workbook_type,
            likely_purpose=likely_purpose,
            important_sheets=important_sheets,
            ignored_sheets=ignored_sheets,
            likely_sections=sections,
            projection_period_guess=projection_period_guess,
            confidence=confidence,
            human_review_required=confidence < 0.55 or intake_result.route.get("human_review_required", False),
            reasoning=self._reasoning(workbook_type, sections, important_sheets, projection_period_guess),
        )

    def _classify_workbook_type(self, context: dict[str, Any], sections: list[str]) -> str:
        section_set = set(sections)
        lifecycle = context.get("lifecycle_stage") or []
        functional_work = context.get("functional_work") or []

        if "fund_management" in functional_work:
            return "fund_model"
        if "acquisition" in lifecycle and MODEL_TYPE_RULES["acquisition_underwriting_model"]["sections"] & section_set:
            return "acquisition_underwriting_model"
        if {"operating_forecast", "returns"} & section_set:
            return "asset_management_forecast_model"
        return "financial_model_workbook"

    def _projection_period_guess(self, candidates: list[str]) -> str | None:
        if len(candidates) < 2:
            return None
        return f"{candidates[0]}-{candidates[-1]}"

    def _confidence(
        self,
        intake_result: IntakeResult,
        inspection: WorkbookInspectionResult,
        sections: list[str],
    ) -> float:
        confidence = 0.25
        confidence += min(float(intake_result.document_identity.get("confidence", 0)) * 0.35, 0.35)
        if inspection.likely_important_sheets:
            confidence += 0.18
        if sections:
            confidence += min(len(sections) * 0.04, 0.18)
        if inspection.projection_period_candidates:
            confidence += 0.04
        return round(min(confidence, 0.9), 2)

    def _reasoning(
        self,
        workbook_type: str,
        sections: list[str],
        important_sheets: list[str],
        projection_period_guess: str | None,
    ) -> str:
        pieces = [
            f"Workbook structure is most consistent with {workbook_type}.",
            f"Likely sections: {', '.join(sections) if sections else 'not enough structure detected'}.",
            f"Important sheets: {', '.join(important_sheets) if important_sheets else 'not enough sheet evidence'}.",
        ]
        if projection_period_guess:
            pieces.append(f"Detected possible projection period headers around {projection_period_guess}.")
        return " ".join(pieces)
