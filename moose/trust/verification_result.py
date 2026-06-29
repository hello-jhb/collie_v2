"""Result objects for Moose Trust Engine verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class VerifiedFact:
    """A claim after code-based Trust Engine verification."""

    fact_id: str
    claim_id: str
    metric_or_subject: str
    verified_value: Any
    unit: str | None
    source: str
    extraction_method: str | None
    fact_origin: str
    verification_status: str
    checks: list[dict[str, Any]]
    caveats: list[str] = field(default_factory=list)
    notes: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationRunResult:
    """Batch Trust Engine output."""

    verified_facts: list[dict[str, Any]]
    summary: dict[str, int]
    caveats: list[str]
    rejected_claims: list[dict[str, Any]]
    reconciliation_notes: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
