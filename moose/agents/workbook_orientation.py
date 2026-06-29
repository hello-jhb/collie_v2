"""Workbook Orientation Agent contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class WorkbookOrientationAgent:
    """Understand workbook structure before claim extraction."""

    def orient(self, file_path: str | Path, document_identity: dict[str, Any]) -> dict[str, Any]:
        """Return workbook tabs, schedules, sections, and likely authoritative areas."""
        # TODO(Day 3): Orient workbooks without extracting claims or trusting values.
        raise NotImplementedError("Day 3 will implement workbook orientation.")
