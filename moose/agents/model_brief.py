"""Model Brief Agent contract."""

from __future__ import annotations

from typing import Any


class ModelBriefAgent:
    """Summarize the purpose and structure of an oriented model."""

    def create_brief(self, orientation: dict[str, Any]) -> dict[str, Any]:
        """Return a concise model brief grounded in workbook orientation."""
        # TODO(Day 3): Generate a brief from orientation output only.
        raise NotImplementedError("Day 3 will implement model brief generation.")
