"""File Identification Agent contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FileIdentifier:
    """Identify uploaded files in Moose Domain Model terms."""

    def identify(self, file_path: str | Path) -> dict[str, Any]:
        """Return a document identity candidate for an uploaded file."""
        # TODO(Day 2): Implement GPT-assisted identification without production GPT wiring.
        raise NotImplementedError("Day 2 will implement file identification.")
