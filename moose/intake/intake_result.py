"""Result objects for Moose intake."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class DocumentIdentity:
    """Probabilistic file identification result."""

    document_type: str
    confidence: float
    evidence: list[str]
    reasoning: str
    human_review_required: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)


@dataclass
class IntakeResult:
    """Structured output from the Day 2 Moose Intake Layer."""

    file_path: str
    document_identity: dict[str, Any]
    resolved_context: dict[str, Any]
    route: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""
        return asdict(self)
