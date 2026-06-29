"""GPT-first workbook claim discovery interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from moose.llm import LLMClient, LLMUnavailable

from .workbook_result import WorkbookEvidencePackResult, WorkbookMentalModelResult


class WorkbookClaimDiscoveryUnavailable(RuntimeError):
    """Raised when GPT claim discovery is unavailable."""


class WorkbookClaimDiscoveryAgent:
    """Discover claims from a mental model and bounded workbook evidence."""

    MAX_PROMPT_SHEETS = 10
    MAX_SAMPLED_CELLS_PER_SHEET = 25
    MAX_SECTION_BLOCKS_PER_SHEET = 8
    MAX_CANDIDATE_NEIGHBORHOODS = 50
    MAX_ROW_CONTEXT_CELLS = 12
    MAX_STRING_LENGTH = 140

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def discover(
        self,
        mental_model: WorkbookMentalModelResult,
        evidence_pack: WorkbookEvidencePackResult,
        source_document: str | None = None,
    ) -> list[dict[str, Any]]:
        """Ask GPT to discover grounded claims from bounded evidence."""
        prompt = self._prompt(mental_model, evidence_pack, source_document)
        schema = self._schema()
        try:
            response = self.llm_client.complete_json(
                system_prompt=(
                    "You are the Moose Claim Discovery Agent. Agents interpret context; "
                    "code verifies evidence. Return only grounded workbook claims as JSON."
                ),
                user_payload=json.loads(prompt),
                schema=schema,
            )
        except LLMUnavailable as exc:
            raise WorkbookClaimDiscoveryUnavailable(str(exc)) from exc

        claims = response.get("claims", [])
        if not isinstance(claims, list):
            raise WorkbookClaimDiscoveryUnavailable("LLM claim discovery response did not include a claims list.")
        return [self._normalize_claim(claim, source_document) for claim in claims if isinstance(claim, dict)]

    def _prompt(
        self,
        mental_model: WorkbookMentalModelResult,
        evidence_pack: WorkbookEvidencePackResult,
        source_document: str | None,
    ) -> str:
        payload = {
            "instruction": (
                "Discover structured claims from bounded workbook evidence. "
                "Use the mental model and evidence to decide what matters, but do not "
                "match a fixed metric list. Every claim must cite a real source sheet "
                "and cell from the evidence pack. Do not verify claims, reconcile "
                "claims, produce final facts, or make investment recommendations. "
                "If a claim cannot cite sheet/cell evidence, omit it."
            ),
            "output_contract": {
                "root": "Return a JSON object with one key: claims.",
                "claim_schema": "Each item must satisfy moose/schemas/claim.schema.json.",
                "source_document": source_document,
                "source_location": "Use object form with sheet, cell, nearby_label, and table_or_section when available.",
                "extraction_method": "Use gpt_workbook_claim_discovery_v1.",
            },
            "mental_model": self._compact_mental_model(mental_model),
            "important_sheets": evidence_pack.important_sheet_names,
            "evidence_pack_snippets": self._compact_evidence_pack(evidence_pack),
        }
        return json.dumps(payload, indent=2, default=str)

    def _schema(self) -> dict[str, Any]:
        claim_schema = self._claim_schema()
        return {
            "type": "object",
            "required": ["claims"],
            "additionalProperties": False,
            "properties": {
                "claims": {
                    "type": "array",
                    "items": claim_schema,
                    "maxItems": 20,
                }
            },
        }

    def _claim_schema(self) -> dict[str, Any]:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "claim.schema.json"
        with schema_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _compact_mental_model(self, mental_model: WorkbookMentalModelResult) -> dict[str, Any]:
        return {
            "document_type": mental_model.document_type,
            "workbook_type": mental_model.workbook_type,
            "business_purpose": mental_model.business_purpose,
            "decision_supported": mental_model.decision_supported,
            "important_sheets": mental_model.important_sheets,
            "expected_sections": mental_model.expected_sections,
            "expected_metric_families": mental_model.expected_metric_families,
            "extraction_priorities": mental_model.extraction_priorities,
            "likely_authoritative_sources": mental_model.likely_authoritative_sources,
            "caveats": mental_model.caveats,
        }

    def _compact_evidence_pack(self, evidence_pack: WorkbookEvidencePackResult) -> dict[str, Any]:
        prompt_sheets = evidence_pack.important_sheet_names[:self.MAX_PROMPT_SHEETS]
        sampled_cells = {
            sheet: [self._compact_cell(cell) for cell in evidence_pack.sampled_cells.get(sheet, [])[:self.MAX_SAMPLED_CELLS_PER_SHEET]]
            for sheet in prompt_sheets
        }
        section_header_blocks = {
            sheet: [self._compact_block(block) for block in evidence_pack.section_header_blocks.get(sheet, [])[:self.MAX_SECTION_BLOCKS_PER_SHEET]]
            for sheet in prompt_sheets
        }
        candidate_neighborhoods = [
            self._compact_neighborhood(neighborhood)
            for neighborhood in evidence_pack.candidate_neighborhoods
            if neighborhood.get("sheet") in prompt_sheets
        ][:self.MAX_CANDIDATE_NEIGHBORHOODS]
        return {
            "sampled_cells": sampled_cells,
            "section_header_blocks": section_header_blocks,
            "candidate_neighborhoods": candidate_neighborhoods,
            "caveats": evidence_pack.caveats,
        }

    def _compact_cell(self, cell: dict[str, Any]) -> dict[str, Any]:
        return {
            "cell": cell.get("cell"),
            "row": cell.get("row"),
            "column": cell.get("column"),
            "value": self._compact_value(cell.get("value")),
        }

    def _compact_block(self, block: dict[str, Any]) -> dict[str, Any]:
        return {
            "sheet": block.get("sheet"),
            "row": block.get("row"),
            "text": self._compact_value(block.get("text")),
        }

    def _compact_neighborhood(self, neighborhood: dict[str, Any]) -> dict[str, Any]:
        return {
            "sheet": neighborhood.get("sheet"),
            "label_cell": neighborhood.get("label_cell"),
            "label": self._compact_value(neighborhood.get("label")),
            "nearby_values": [
                {
                    "cell": item.get("cell"),
                    "value": self._compact_value(item.get("value")),
                }
                for item in neighborhood.get("nearby_values", [])
            ],
            "row_context": [
                {
                    "cell": item.get("cell"),
                    "value": self._compact_value(item.get("value")),
                }
                for item in (neighborhood.get("row_context") or [])[:self.MAX_ROW_CONTEXT_CELLS]
            ],
        }

    def _compact_value(self, value: Any) -> Any:
        if isinstance(value, str):
            clean = " ".join(value.split())
            if len(clean) > self.MAX_STRING_LENGTH:
                return clean[: self.MAX_STRING_LENGTH - 3] + "..."
            return clean
        return value

    def _normalize_claim(self, claim: dict[str, Any], source_document: str | None) -> dict[str, Any]:
        normalized = dict(claim)
        normalized.setdefault("claim_id", f"claim:gpt:{uuid4().hex[:8]}")
        normalized.setdefault("extraction_method", "gpt_workbook_claim_discovery_v1")
        normalized.setdefault("confidence", 0.5)
        if source_document:
            normalized["source_document"] = source_document
        source_location = normalized.get("source_location")
        if isinstance(source_location, str) and "!" in source_location:
            sheet, cell = source_location.split("!", 1)
            normalized["source_location"] = {"sheet": sheet, "cell": cell}
        return normalized
