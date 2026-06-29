"""Source authority checks for Moose verification."""

from __future__ import annotations

from typing import Any


class AuthorityResolver:
    """Determine whether a source is likely authoritative for a claim."""

    def resolve(
        self,
        claim: dict[str, Any],
        mental_model: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Return authority assessment metadata for a claim and source sheet."""
        mental_model = mental_model or {}
        source_location = claim.get("source_location") or {}
        source_sheet = source_location.get("sheet") if isinstance(source_location, dict) else None
        metric = claim.get("metric_or_subject")
        important_sheets = set(mental_model.get("important_sheets") or [])
        authoritative_sources = (
            mental_model.get("likely_authoritative_sources", {}).get(metric, [])
            if isinstance(mental_model.get("likely_authoritative_sources"), dict)
            else []
        )

        if source_sheet in important_sheets:
            return {
                "status": "passed",
                "caveats": [],
                "details": f"{source_sheet} is an important sheet in the mental model.",
            }
        if any(self._sheet_name_matches(source_sheet, source) for source in authoritative_sources):
            return {
                "status": "passed",
                "caveats": [],
                "details": f"{source_sheet} matches an expected authoritative source for {metric}.",
            }

        return {
            "status": "needs_review",
            "caveats": [f"{source_sheet} is not listed as important or authoritative for {metric}."],
            "details": "Source authority is weak in the v0 mental model.",
        }

    def _sheet_name_matches(self, sheet_name: str | None, expected: str) -> bool:
        if not sheet_name:
            return False
        return expected.lower() in sheet_name.lower() or sheet_name.lower() in expected.lower()
