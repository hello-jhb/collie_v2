"""Claim Extraction Agent contract."""

from __future__ import annotations

from typing import Any


class ClaimExtractor:
    """Extract structured claims from a comprehended document."""

    def extract(self, comprehension: dict[str, Any]) -> list[dict[str, Any]]:
        """Return claims with source evidence, confidence, and extraction reasoning."""
        # TODO(Day 4): Extract claims, not verified facts.
        raise NotImplementedError("Day 4 will implement claim extraction.")
